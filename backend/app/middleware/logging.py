import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("hireminds.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one line per request: method, path, status, duration, and the
    authenticated user id when available (set on request.state by the auth
    dependency — see app/auth/users.py). Never logs bodies/headers, so
    passwords and tokens never reach the log.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": getattr(request.state, "user_id", None),
            },
        )
        return response
