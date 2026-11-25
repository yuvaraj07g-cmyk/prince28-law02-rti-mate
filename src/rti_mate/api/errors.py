"""RFC 9457 problem details."""

from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
    errors: list[dict[str, str]] | None = None,
):
    content = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if errors is not None:
        content["errors"] = errors

    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=content,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        return problem_response(
            request,
            exc.status_code,
            HTTPStatus(exc.status_code).phrase,
            str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
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

    @app.exception_handler(Exception)
    async def internal_error_handler(
        request: Request,
        exc: Exception,
    ):
        return problem_response(
            request,
            500,
            "Internal Server Error",
            "Internal server error",
        )
