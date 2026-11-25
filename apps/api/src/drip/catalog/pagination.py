"""Tamper-evident, public keyset cursor helpers for catalog discovery."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from uuid import UUID

from drip.core.config import settings


def filter_fingerprint(filters: dict[str, str | None]) -> str:
    encoded = json.dumps(filters, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def encode_cursor(last_id: UUID, fingerprint: str) -> str:
    body = json.dumps(
        {"v": 1, "last_id": str(last_id), "filters": fingerprint},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), body, hashlib.sha256).digest()
    return f"{_encode(body)}.{_encode(signature)}"


def decode_cursor(token: str, expected_fingerprint: str) -> UUID:
    try:
        if len(token) > 512 or token.count(".") != 1:
            raise ValueError
        body_part, signature_part = token.split(".", maxsplit=1)
        body = _decode(body_part)
        signature = _decode(signature_part)
        if _encode(body) != body_part or _encode(signature) != signature_part:
            raise ValueError
        expected_signature = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), body, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError
        payload = json.loads(body)
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or payload.get("filters") != expected_fingerprint
            or not isinstance(payload.get("last_id"), str)
        ):
            raise ValueError
        return UUID(payload["last_id"])
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Invalid catalog cursor.") from None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)

