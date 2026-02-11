from fastapi import APIRouter, HTTPException

from app import state
from app.models import PlateRequest, SlotInfo, TipRackRequest, TubeRackRequest

router = APIRouter(prefix="/deck", tags=["deck"])


def _get_deck():
    lh = state.get_lh()
    return lh.deck


@router.get("", response_model=list[SlotInfo])
async def list_deck():
    deck = _get_deck()
    slots: list[SlotInfo] = []
    for i in range(1, 13):
        child = deck.slots[i - 1]
        if child is not None:
            slots.append(SlotInfo(
                slot=i,
                resource_name=child.name,
                resource_type=type(child).__name__,
            ))
        else:
            slots.append(SlotInfo(slot=i))
    return slots


@router.post("/slots/{slot_id}/tip-rack")
async def assign_tip_rack(slot_id: int, body: TipRackRequest):
    deck = _get_deck()
    _validate_slot(slot_id)

    resource = state.create_tip_rack(body.ot_name, body.name)
    deck.assign_child_at_slot(resource, slot_id)
    state.register_resource(body.name, resource)
    return {"status": "ok", "slot": slot_id, "name": body.name}


@router.post("/slots/{slot_id}/plate")
async def assign_plate(slot_id: int, body: PlateRequest):
    deck = _get_deck()
    _validate_slot(slot_id)

    resource = state.create_plate(body.resource_type, body.name)
    deck.assign_child_at_slot(resource, slot_id)
    state.register_resource(body.name, resource)
    return {"status": "ok", "slot": slot_id, "name": body.name}


@router.post("/slots/{slot_id}/tube-rack")
async def assign_tube_rack(slot_id: int, body: TubeRackRequest):
    deck = _get_deck()
    _validate_slot(slot_id)

    resource = state.create_tube_rack(body.ot_name, body.name)
    deck.assign_child_at_slot(resource, slot_id)
    state.register_resource(body.name, resource)
    return {"status": "ok", "slot": slot_id, "name": body.name}


@router.delete("/slots/{slot_id}")
async def remove_slot(slot_id: int):
    deck = _get_deck()
    _validate_slot(slot_id)

    child = deck.slots[slot_id - 1]
    if child is None:
        raise HTTPException(status_code=400, detail=f"Slot {slot_id} is empty")

    state.unregister_resource(child.name)
    child.unassign()
    return {"status": "ok", "slot": slot_id}


def _validate_slot(slot_id: int) -> None:
    if not 1 <= slot_id <= 12:
        raise HTTPException(status_code=400, detail="Slot must be between 1 and 12")
