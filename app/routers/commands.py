import logging

from fastapi import APIRouter, HTTPException

from pylabrobot.resources import Coordinate as PLRCoordinate

from app import state
from app.models import (
    AspirateRequest,
    Coordinate,
    DispenseRequest,
    DropTipsRequest,
    PickUpTipsRequest,
    ReturnTipsRequest,
)

router = APIRouter(prefix="/commands", tags=["commands"])
logger = logging.getLogger(__name__)


def _to_plr_offsets(offsets: list[Coordinate] | None) -> list[PLRCoordinate] | None:
    if offsets is None:
        return None
    return [PLRCoordinate(x=o.x, y=o.y, z=o.z) for o in offsets]


def _get_children(resource_name: str, well_indices: list[int]):
    """Resolve well/tip-spot children by integer index."""
    resource = state.get_resource(resource_name)
    children = resource.children
    try:
        return [children[i] for i in well_indices]
    except IndexError:
        raise HTTPException(
            status_code=400,
            detail=f"Well index out of range for resource {resource_name!r} "
            f"(has {len(children)} children)",
        )


@router.post("/pick-up-tips")
async def pick_up_tips(body: PickUpTipsRequest):
    lh = state.get_lh()
    tip_spots = _get_children(body.resource_name, body.well_indices)
    offsets = _to_plr_offsets(body.offsets)

    await lh.pick_up_tips(tip_spots, offsets=offsets)
    return {"status": "ok"}


@router.post("/drop-tips")
async def drop_tips(body: DropTipsRequest):
    lh = state.get_lh()
    offsets = _to_plr_offsets(body.offsets)

    if body.resource_name is None:
        # Drop to trash
        trash = lh.deck.get_trash_area()
        await lh.drop_tips(trash, offsets=offsets)
    else:
        tip_spots = _get_children(body.resource_name, body.well_indices or [])
        await lh.drop_tips(tip_spots, offsets=offsets)
    return {"status": "ok"}


@router.post("/return-tips")
async def return_tips(body: ReturnTipsRequest | None = None):
    lh = state.get_lh()
    body = body or ReturnTipsRequest()
    offsets = _to_plr_offsets(body.offsets)

    await lh.return_tips(offsets=offsets)
    return {"status": "ok"}


@router.post("/aspirate")
async def aspirate(body: AspirateRequest):
    lh = state.get_lh()
    wells = _get_children(body.resource_name, body.well_indices)
    offsets = _to_plr_offsets(body.offsets)

    kwargs: dict = {}
    if body.flow_rates is not None:
        kwargs["flow_rates"] = body.flow_rates

    await lh.aspirate(wells, vols=body.volumes, offsets=offsets, **kwargs)
    return {"status": "ok"}


@router.post("/dispense")
async def dispense(body: DispenseRequest):
    lh = state.get_lh()
    wells = _get_children(body.resource_name, body.well_indices)
    offsets = _to_plr_offsets(body.offsets)

    kwargs: dict = {}
    if body.flow_rates is not None:
        kwargs["flow_rates"] = body.flow_rates

    await lh.dispense(wells, vols=body.volumes, offsets=offsets, **kwargs)
    return {"status": "ok"}
