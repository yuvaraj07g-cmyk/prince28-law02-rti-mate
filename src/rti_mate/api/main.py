"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rti_mate.api.middleware import RequestMiddleware
from rti_mate.api.routes import documents, health
from rti_mate.config import Settings, get_settings
from rti_mate.logging_setup import setup_logging
from rti_mate.store import RecordStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = RecordStore(settings.data_file)

        try:
            store.load()
        except (OSError, ValueError):
            logging.getLogger(__name__).exception("could not load records")

        app.state.store = store
        yield

    app = FastAPI(
        title="RTI Mate",
        lifespan=lifespan,
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content={
                "type": "about:blank",
                "title": "Not Found" if exc.status_code == 404 else "HTTP Error",
                "status": exc.status_code,
                "detail": str(exc.detail),
                "instance": request.url.path,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        errors = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            media_type="application/problem+json",
            content={
                "type": "about:blank",
                "title": "Unprocessable Entity",
                "status": 422,
                "detail": "Request validation failed",
                "instance": request.url.path,
                "errors": errors,
            },
        )

    app.add_middleware(RequestMiddleware)
    app.include_router(health.router)
    app.include_router(documents.router)

    return app
