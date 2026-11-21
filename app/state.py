"""Singleton LiquidHandler and resource registry."""

import importlib
import logging
from pathlib import Path
from typing import Any

import ot_api
import yaml
from fastapi import HTTPException

from pylabrobot.liquid_handling import LiquidHandler
from app.ot2_backend import OpentronsOT2Backend
from pylabrobot.resources import Resource
from pylabrobot.resources.opentrons import OTDeck
from pylabrobot.resources.volume_tracker import set_volume_tracking
from pylabrobot.resources.opentrons.load import (
    load_ot_tip_rack,
    load_ot_tube_rack
)
from pylabrobot.resources.tube import Tube

logger = logging.getLogger(__name__)

# Timeouts, poll rate limit, command-status logging and the dispense_in_place fix.
import app.ot_api_patches  # noqa: F401,E402

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_lh: LiquidHandler | None = None
_host: str | None = None
_resources: dict[str, Resource] = {}  # name → resource
# What the current session was built from; a connect asking for anything else rebuilds it.
_session_key: tuple | None = None

# Run statuses after which the OT-2 robot-server no longer accepts commands for that run.
_DEAD_RUN_STATUSES = {"stop-requested", "stopped", "finishing", "failed", "succeeded"}


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
    return load_ot_tip_rack(ot_name, name)


def create_plate(resource_type: str, name: str) -> Any:
    module = importlib.import_module("pylabrobot.resources")
    try:
        cls = getattr(module, resource_type)
    except AttributeError:
        raise HTTPException(status_code=400, detail=f"Unknown plate type: {resource_type}")
    return cls(name=name)


def create_tube_rack(ot_name: str, name: str) -> Any:
    rack = load_ot_tube_rack(ot_name, name)
    for holder in rack.children:
        tube = Tube(
            name=f"{name}_{holder.name}",
            size_x=holder.get_size_x(),
            size_y=holder.get_size_y(),
            size_z=holder.get_size_z(),
            max_volume=holder.get_size_x() * holder.get_size_y() * holder.get_size_z(),
            material_z_thickness=1.0,
        )
        holder.assign_child_resource(tube)
    return rack


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------

def _deck_config_stamp(path: str | Path | None) -> tuple | None:
    """Path and mtime of the deck config, so an edited file triggers a rebuild."""
    if path is None:
        return None
    try:
        return (str(path), Path(path).stat().st_mtime)
    except OSError:
        return (str(path), None)


def _session_problem() -> str | None:
    """Why the current OT-2 run can no longer take commands, or None if it still can.

    Catches the OT-2 rebooting or its robot-server restarting (run gone), and the run being
    cancelled or replaced from elsewhere (not current / terminal status).
    """
    run_id = ot_api.run_id
    if not run_id:
        return "no run id"
    try:
        run = ot_api.runs.get_run(run_id)
    except Exception as e:  # 404 after a reboot, unreachable robot, ...
        return f"run {run_id} unreadable: {e}"
    status = run.get("status")
    if status in _DEAD_RUN_STATUSES:
        return f"run {run_id} is {status}"
    if run.get("current") is False:
        return f"run {run_id} is no longer the current run"
    return None


async def _teardown() -> None:
    """Drop the current session; a stop that fails (robot gone) still clears local state."""
    global _lh, _host, _session_key
    lh, _lh, _host, _session_key = _lh, None, None, None
    _resources.clear()
    if lh is not None:
        try:
            await lh.stop()
        except Exception as e:
            logger.warning("Stopping the old OT-2 session failed (ignored): %s", e)


async def connect(
    host: str,
    port: int = 31950,
    traversal_height: float = 120.0,
    deck_config_path: str | Path | None = None,
) -> bool:
    """Make sure a working session to the OT-2 exists. Returns True if the existing one was kept.

    Idempotent, so callers can connect before every protocol instead of disconnecting after
    each: a healthy session with the same settings is kept as is (no new run, no homing, and
    the pipette's tip state is preserved). A dead session, or one built from different
    settings or an edited deck config, is torn down and rebuilt.
    """
    global _lh, _host, _session_key

    key = (host, port, traversal_height, _deck_config_stamp(deck_config_path))
    if _lh is not None:
        if key != _session_key:
            problem = "connect settings or deck config changed"
        else:
            problem = _session_problem()
        if problem is None:
            logger.info("Already connected to OT-2 at %s:%s — reusing session (run %s)",
                        host, port, ot_api.run_id)
            return True
        logger.warning("Rebuilding OT-2 session: %s", problem)
        await _teardown()

    deck = OTDeck()
    backend = OpentronsOT2Backend(host=host, port=port)
    # PLR hardcodes traversal_height = 120 in __init__; override it.
    backend.traversal_height = traversal_height
    lh = LiquidHandler(backend=backend, deck=deck)

    # Load deck config before setup so resources are on the deck
    if deck_config_path is not None:
        _load_deck_config(lh, Path(deck_config_path))

    try:
        await lh.setup()  # new OT-2 run + home
    except Exception:
        _resources.clear()
        raise
    _lh = lh
    _host = host
    _session_key = key
    logger.info("Connected to OT-2 at %s:%s (run %s)", host, port, ot_api.run_id)
    return False


async def disconnect() -> None:
    """Cancel the OT-2 run (frees the robot for the Opentrons App) and clear state."""
    get_lh()  # 503 if not connected
    await _teardown()
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
