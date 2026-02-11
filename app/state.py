"""Singleton LiquidHandler and resource registry."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

import opentrons_shared_data.labware
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.liquid_handling.backends.opentrons_backend import OpentronsBackend
from pylabrobot.resources import Resource
from pylabrobot.resources.opentrons import OTDeck
from pylabrobot.resources.opentrons.load import (
    load_shared_opentrons_resource,
    ot_definition_to_resource,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_lh: LiquidHandler | None = None
_host: str | None = None
_resources: dict[str, Resource] = {}  # name → resource


def get_lh() -> LiquidHandler:
    """Return the current LiquidHandler or raise 503."""
    if _lh is None:
        raise HTTPException(status_code=503, detail="Robot not connected")
    return _lh


def is_connected() -> bool:
    return _lh is not None


def current_host() -> str | None:
    return _host


# ---------------------------------------------------------------------------
# Resource registry helpers
# ---------------------------------------------------------------------------

def register_resource(name: str, resource: Resource) -> None:
    _resources[name] = resource


def get_resource(name: str) -> Resource:
    try:
        return _resources[name]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown resource: {name}")


def list_resources() -> dict[str, Resource]:
    return dict(_resources)


def unregister_resource(name: str) -> None:
    _resources.pop(name, None)


# ---------------------------------------------------------------------------
# Resource creation helpers
# ---------------------------------------------------------------------------

def create_tip_rack(ot_name: str, name: str) -> Any:
    return load_shared_opentrons_resource(ot_name, name)


def create_plate(resource_type: str, name: str) -> Any:
    return load_shared_opentrons_resource(resource_type, name)


def create_tube_rack(ot_name: str, name: str) -> Any:
    """Load an aluminum-block / tube-rack definition as a well plate.

    Opentrons categorises these as 'aluminumBlock' or 'tubeRack', which
    ``ot_definition_to_resource`` does not handle natively.  We patch the
    display category to 'wellPlate' so the existing converter creates a
    Plate with Wells that work for liquid handling operations.
    """
    data = opentrons_shared_data.labware.load_definition(ot_name, version=1)
    # The converter only supports wellPlate/tipRack.  Tube racks and
    # aluminum blocks are structurally identical to well plates.
    data = copy.deepcopy(data)
    data["metadata"]["displayCategory"] = "wellPlate"
    return ot_definition_to_resource(data, name)


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------

async def connect(
    host: str,
    port: int = 31950,
    traversal_height: float = 120.0,
    deck_config_path: str | Path | None = None,
) -> None:
    global _lh, _host

    if _lh is not None:
        raise HTTPException(status_code=400, detail="Already connected")

    deck = OTDeck()
    backend = OpentronsBackend(host=host, port=port)
    lh = LiquidHandler(backend=backend, deck=deck)

    # Load deck config before setup so resources are on the deck
    if deck_config_path is not None:
        _load_deck_config(lh, Path(deck_config_path))

    await lh.setup()
    _lh = lh
    _host = host
    logger.info("Connected to OT-2 at %s:%s", host, port)


async def disconnect() -> None:
    global _lh, _host
    lh = get_lh()
    await lh.stop()
    _lh = None
    _host = None
    _resources.clear()
    logger.info("Disconnected from OT-2")


# ---------------------------------------------------------------------------
# Deck config loading
# ---------------------------------------------------------------------------

def _load_deck_config(lh: LiquidHandler, path: Path) -> None:
    """Load YAML deck config and assign resources to the deck."""
    with open(path) as f:
        cfg = yaml.safe_load(f)

    for item in cfg.get("deck", []):
        slot = item["slot"]
        rtype = item["type"]
        name = item["name"]
        ot_name = item.get("ot_name", "")

        if rtype == "tip_rack":
            resource = create_tip_rack(ot_name, name)
        elif rtype == "plate":
            resource = create_plate(ot_name, name)
        elif rtype == "tube_rack":
            resource = create_tube_rack(ot_name, name)
        else:
            logger.warning("Unknown resource type %r in deck config, skipping", rtype)
            continue

        lh.deck.assign_child_at_slot(resource, slot)
        register_resource(name, resource)
        logger.info("Assigned %s %r to slot %d", rtype, name, slot)
