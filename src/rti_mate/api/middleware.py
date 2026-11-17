"""Request ID and request timing middleware."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        start = time.perf_counter()

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                extra={"request_id": request_id, "duration_ms": elapsed},
            )
