"""Correlation id and one request log line. Pure ASGI, so an unhandled error still reaches the 500 handler."""

import logging
import re
import time
import uuid
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import correlation_id_var

HEADER = "X-Correlation-ID"
_ACCEPTABLE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

logger = logging.getLogger("app.request")


def new_correlation_id() -> str:
    return uuid.uuid4().hex


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = next((v.decode("latin-1") for k, v in scope["headers"] if k == HEADER.lower().encode()), "")
        correlation_id = incoming if _ACCEPTABLE.match(incoming) else new_correlation_id()
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        token = correlation_id_var.set(correlation_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_header(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[HEADER] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            extra: dict[str, Any] = {
                "method": scope["method"],
                "path": scope["path"],
                "status": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            }
            logger.info("request", extra=extra)
            correlation_id_var.reset(token)
