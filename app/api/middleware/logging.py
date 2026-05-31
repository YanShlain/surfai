import json
import logging
import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        body_bytes = await request.body()
        body_log: dict | str | None
        try:
            body_log = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            body_log = f"<non-json {len(body_bytes)} bytes>"

        logger.info(
            "HTTP request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
                "body": body_log,
            },
        )

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request = Request(request.scope, receive)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        response_log: dict | str | None
        try:
            response_log = json.loads(response_body) if response_body else None
        except json.JSONDecodeError:
            response_log = f"<non-json {len(response_body)} bytes>"

        logger.info(
            "HTTP response",
            extra={
                "status_code": response.status_code,
                "request_id": request_id,
                "duration_ms": duration_ms,
                "body": response_log,
            },
        )

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers={**dict(response.headers), "X-Request-ID": request_id},
            media_type=response.media_type,
        )
