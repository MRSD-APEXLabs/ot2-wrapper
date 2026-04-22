import logging

import ot_api
import ot_api.requestor as requestor
from fastapi import APIRouter, HTTPException

from app import state

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger(__name__)


@router.get("/ot2-commands")
async def ot2_commands(limit: int = 20):
    """Return recent OT-2 run commands with their status and error info."""
    if not state.is_connected():
        raise HTTPException(status_code=503, detail="Robot not connected")

    run_id = ot_api.run_id
    if run_id is None:
        raise HTTPException(status_code=503, detail="No active OT-2 run")

    data = requestor.get(f"/runs/{run_id}/commands?pageLength={limit}&sort=createdAt:desc")
    commands = data.get("data", [])

    return {
        "run_id": run_id,
        "commands": [
            {
                "id": cmd["id"],
                "type": cmd.get("commandType"),
                "status": cmd.get("status"),
                "params": cmd.get("params"),
                "error": cmd.get("error"),
                "createdAt": cmd.get("createdAt"),
                "completedAt": cmd.get("completedAt"),
            }
            for cmd in commands
        ],
    }


@router.get("/ot2-tip-state")
async def ot2_tip_state():
    """Return current tip state from PLR head trackers."""
    lh = state.get_lh()
    result = {}
    for channel, tracker in lh.head.items():
        tip_info: dict = {"has_tip": tracker.has_tip}
        if tracker.has_tip:
            try:
                tip = tracker.get_tip()
                tip_info["tip_volume"] = tip.tracker.get_used_volume()
                tip_info["tip_max_volume"] = tip.maximal_volume
            except Exception as e:
                tip_info["error"] = str(e)
        result[str(channel)] = tip_info
    return result
