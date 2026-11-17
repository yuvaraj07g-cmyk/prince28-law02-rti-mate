"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request):
    store = request.app.state.store

    if not store.records:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "checks": {"records_loaded": False}},
        )

    return {
        "status": "ready",
        "checks": {"records_loaded": True},
    }
