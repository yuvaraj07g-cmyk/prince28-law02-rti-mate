"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from rti_mate.api.errors import problem_response
from rti_mate.api.middleware import RequestMiddleware
from rti_mate.api.routes import documents, health
from rti_mate.config import Settings, get_settings
from rti_mate.db.session import make_engine, make_sessionmaker
from rti_mate.logging_setup import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings)
        app.state.engine = engine
        app.state.session_factory = make_sessionmaker(engine)

        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="RTI Mate",
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return problem_response(
            request,
            exc.status_code,
            "Not Found" if exc.status_code == 404 else "HTTP Error",
            str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]

        return problem_response(
            request,
            422,
            "Unprocessable Entity",
            "Request validation failed",
            errors,
        )

    app.add_middleware(RequestMiddleware)
    app.include_router(health.router)
    app.include_router(documents.router)

    return app
