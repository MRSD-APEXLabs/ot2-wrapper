from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Coordinate(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    traversal_height: float | None = None
    deck_config_path: str | None = None


class StatusResponse(BaseModel):
    connected: bool
    host: str | None = None


# ---------------------------------------------------------------------------
# Deck – Tip Rack
# ---------------------------------------------------------------------------

class TipRackRequest(BaseModel):
    ot_name: str  # e.g. "opentrons_96_filtertiprack_20ul"
    name: str


# ---------------------------------------------------------------------------
# Deck – Plate
# ---------------------------------------------------------------------------

class PlateRequest(BaseModel):
    resource_type: str  # PLR class name, e.g. "agilent_96_wellplate_150uL_Ub"
    name: str


# ---------------------------------------------------------------------------
# Deck – Tube Rack
# ---------------------------------------------------------------------------

class TubeDefinition(BaseModel):
    position: int
    tube_type: str
    name: str


class TubeRackRequest(BaseModel):
    ot_name: str
    name: str
    tubes: list[TubeDefinition] | None = None


# ---------------------------------------------------------------------------
# Deck – generic slot info
# ---------------------------------------------------------------------------

class SlotInfo(BaseModel):
    slot: int
    resource_name: str | None = None
    resource_type: str | None = None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class PickUpTipsRequest(BaseModel):
    resource_name: str
    well_indices: list[int]
    offsets: list[Coordinate] | None = None


class DropTipsRequest(BaseModel):
    resource_name: str | None = None  # None → trash
    well_indices: list[int] | None = None
    offsets: list[Coordinate] | None = None


class ReturnTipsRequest(BaseModel):
    offsets: list[Coordinate] | None = None


class AspirateRequest(BaseModel):
    resource_name: str
    well_indices: list[int]
    volumes: list[float]
    flow_rates: list[float] | None = None
    offsets: list[Coordinate] | None = None


class DispenseRequest(BaseModel):
    resource_name: str
    well_indices: list[int]
    volumes: list[float]
    flow_rates: list[float] | None = None
    offsets: list[Coordinate] | None = None
