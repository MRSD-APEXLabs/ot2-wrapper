import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers import commands, connection, deck

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="OT-2 REST Wrapper", version="0.1.0")

app.include_router(connection.router)
app.include_router(deck.router)
app.include_router(commands.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {exc}"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
