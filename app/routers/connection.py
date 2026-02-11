from fastapi import APIRouter

from app.config import settings
from app.models import ConnectRequest, StatusResponse
from app import state

router = APIRouter(prefix="/robot", tags=["robot"])


@router.post("/connect")
async def connect(body: ConnectRequest | None = None):
    body = body or ConnectRequest()
    host = body.host or settings.ot2_host
    port = body.port or settings.ot2_port
    traversal_height = body.traversal_height or settings.ot2_traversal_height
    deck_config = body.deck_config_path or (
        str(settings.deck_config_path) if settings.deck_config_path else None
    )

    await state.connect(
        host=host,
        port=port,
        traversal_height=traversal_height,
        deck_config_path=deck_config,
    )
    return {"status": "connected", "host": host}


@router.post("/disconnect")
async def disconnect():
    await state.disconnect()
    return {"status": "disconnected"}


@router.post("/home")
async def home():
    lh = state.get_lh()
    await lh.home()
    return {"status": "homed"}


@router.get("/status", response_model=StatusResponse)
async def status():
    return StatusResponse(
        connected=state.is_connected(),
        host=state.current_host(),
    )
