"""Purpose-bound, expiring cursor for stateless one-card discovery."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID

from drip.core.config import settings

MAX_CURSOR_CHARS = 24 * 1024
MAX_SEEN = 200
TTL_SECONDS = 15 * 60
_PURPOSE = b"drip:public-discovery:cursor:v1"


@dataclass(frozen=True)
class DiscoveryCursor:
    filters: dict[str, object]
    seen_ids: tuple[UUID, ...]
    last_id: UUID | None
    mode: str
    anchor_id: UUID | None
    expires_at: int


def _key() -> bytes:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), _PURPOSE, hashlib.sha256).digest()


def encode_discovery_cursor(
    filters: dict[str, object],
    seen_ids: list[UUID],
    last_id: UUID | None,
    *,
    mode: str = "next",
    anchor_id: UUID | None = None,
) -> str:
    if len(seen_ids) > MAX_SEEN or len(set(seen_ids)) != len(seen_ids):
        raise ValueError("Discovery cursor state is invalid.")
    if mode not in {"next", "similar", "different_brand"}:
        raise ValueError("Discovery cursor state is invalid.")
    if (mode == "next") != (anchor_id is None) or (anchor_id is not None and anchor_id not in seen_ids):
        raise ValueError("Discovery cursor state is invalid.")
    payload = {
        "v": 1,
        "filters": filters,
        "seen": [str(value) for value in seen_ids],
        "last": str(last_id) if last_id else None,
        "mode": mode,
        "anchor": str(anchor_id) if anchor_id else None,
        "exp": int(time.time()) + TTL_SECONDS,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_key(), body, hashlib.sha256).digest()
    token = f"{_b64(body)}.{_b64(signature)}"
    if len(token) > MAX_CURSOR_CHARS:
        raise ValueError("Discovery cursor exceeds its supported size.")
    return token


def decode_discovery_cursor(token: str, expected_filters: dict[str, object] | None = None) -> DiscoveryCursor:
    try:
        if len(token) > MAX_CURSOR_CHARS or token.count(".") != 1:
            raise ValueError
        body_text, signature_text = token.split(".", maxsplit=1)
        body = _unb64(body_text)
        signature = _unb64(signature_text)
        if _b64(body) != body_text or _b64(signature) != signature_text:
            raise ValueError
        if not hmac.compare_digest(signature, hmac.new(_key(), body, hashlib.sha256).digest()):
            raise ValueError
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {"v", "filters", "seen", "last", "mode", "anchor", "exp"}:
            raise ValueError
        if payload["v"] != 1 or not isinstance(payload["filters"], dict):
            raise ValueError
        if expected_filters is not None and payload["filters"] != expected_filters:
            raise ValueError
        if not isinstance(payload["seen"], list) or len(payload["seen"]) > MAX_SEEN:
            raise ValueError
        seen = tuple(UUID(value) for value in payload["seen"])
        if len(set(seen)) != len(seen):
            raise ValueError
        last = UUID(payload["last"]) if payload["last"] is not None else None
        mode = payload["mode"]
        anchor = UUID(payload["anchor"]) if payload["anchor"] is not None else None
        if mode not in {"next", "similar", "different_brand"}:
            raise ValueError
        if (mode == "next") != (anchor is None) or (anchor is not None and anchor not in seen):
            raise ValueError
        expires = payload["exp"]
        if not isinstance(expires, int) or isinstance(expires, bool):
            raise ValueError
        if expires <= int(time.time()):
            raise TimeoutError
        return DiscoveryCursor(payload["filters"], seen, last, mode, anchor, expires)
    except TimeoutError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Invalid discovery cursor.") from None


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
        raise ValueError
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
