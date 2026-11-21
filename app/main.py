import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers import commands, connection, deck, debug

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="OT-2 REST Wrapper", version="0.1.0")

app.include_router(connection.router)
app.include_router(deck.router)
app.include_router(commands.router)
app.include_router(debug.router)


@app.middleware("http")
async def log_timing(request: Request, call_next):
    """Log each request on arrival and on completion, so a hung handler shows up."""
    start = time.monotonic()
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("← %s %s %d in %.1fs", request.method, request.url.path,
                response.status_code, time.monotonic() - start)
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("%s %s failed", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {exc}"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
