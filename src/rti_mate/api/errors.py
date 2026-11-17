"""RFC 9457 problem details."""

from fastapi import Request
from fastapi.responses import JSONResponse


def problem_response(request: Request, status: int, title: str, detail: str):
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": request.url.path,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
