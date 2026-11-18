"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        database = True
    except Exception:
        database = False

    if not database:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "checks": {"database": False}},
        )

    return {"status": "ready", "checks": {"database": True}}
