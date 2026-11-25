"""Strict body limits for the public discovery JSON endpoint."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DISCOVERY_PATH = "/api/v1/discover"
MAX_DISCOVERY_BODY_BYTES = 32 * 1024


class DiscoveryRequestLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != DISCOVERY_PATH or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [(key, value) for key, value in headers if key.lower() != b"cache-control"]
                headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        raw_headers = [(key.lower(), value) for key, value in scope.get("headers", [])]
        content_types = [value for key, value in raw_headers if key == b"content-type"]
        content_lengths = [value for key, value in raw_headers if key == b"content-length"]
        if len(content_types) != 1 or len(content_lengths) > 1:
            await self._reject(send_no_store, 400, "INVALID_HEADERS", "Discovery request headers are malformed.")
            return
        content_type = content_types[0].split(b";", 1)[0].strip().lower()
        if content_type != b"application/json":
            await self._reject(send_no_store, 415, "UNSUPPORTED_MEDIA_TYPE", "Discovery requests require JSON.")
            return
        raw_length = content_lengths[0] if content_lengths else None
        if raw_length is not None:
            try:
                if int(raw_length) > MAX_DISCOVERY_BODY_BYTES:
                    await self._reject(send_no_store, 413, "REQUEST_TOO_LARGE", "Discovery request exceeds the supported size.")
                    return
            except ValueError:
                await self._reject(send_no_store, 400, "INVALID_CONTENT_LENGTH", "Discovery request is malformed.")
                return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_DISCOVERY_BODY_BYTES:
                await self._reject(send_no_store, 413, "REQUEST_TOO_LARGE", "Discovery request exceeds the supported size.")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send_no_store)

    @staticmethod
    async def _reject(send: Send, status: int, code: str, message: str) -> None:
        body = json.dumps({
            "code": code,
            "message": message,
            "details": [],
            "timestamp": datetime.now(UTC).isoformat(),
        }).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})
