import io
import json
import logging
import sys

import pytest
from drip.core.logging import SafeJSONFormatter, setup_logging
from fastapi import HTTPException
from pydantic import BaseModel, field_validator


@pytest.mark.parametrize(
    "method,path,status,code",
    [
        ("GET", "/missing", 404, "NOT_FOUND"),
        ("POST", "/", 405, "METHOD_NOT_ALLOWED"),
    ],
)
async def test_http_error_envelope(client, method, path, status, code):
    response = await client.request(method, path)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert set(response.json()) == {"code", "message", "details", "timestamp"}
    if status == 405:
        assert "GET" in response.headers["allow"]


async def test_http_exception_headers_and_internal_details(app, client):
    @app.get("/throttled")
    def throttled():
        raise HTTPException(429, "sensitive-internal-detail", headers={"Retry-After": "30"})

    response = await client.get("/throttled")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert response.json()["code"] == "HTTP_429"
    assert "sensitive-internal-detail" not in response.text


async def test_validation_and_unhandled_errors_do_not_log_sensitive_inputs(app, client):
    secret = "synthetic-sensitive-password"

    class Payload(BaseModel):
        password: str

        @field_validator("password")
        @classmethod
        def invalid(cls, value):
            raise ValueError(f"Rejected password: {value}")

    @app.post("/validation")
    def validation(payload: Payload):
        return {}

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError(secret)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SafeJSONFormatter())
    logger = logging.getLogger("drip.errors")
    logger.addHandler(handler)
    try:
        invalid = await client.post("/validation", json={"password": secret})
        failed = await client.get("/unexpected")
    finally:
        logger.removeHandler(handler)
    assert invalid.status_code == 422
    assert failed.status_code == 500
    assert failed.json()["code"] == "INTERNAL_SERVER_ERROR"
    assert secret not in stream.getvalue()
    assert secret not in invalid.text + failed.text


def test_structured_redaction_including_validation_inputs():
    record = logging.LogRecord("test", logging.ERROR, "", 0, "Static message", (), None)
    record.props = {"nested": [{"password": "hidden", "input": "hidden", "ctx": "hidden"}]}
    output = SafeJSONFormatter().format(record)
    assert "hidden" not in output
    assert json.loads(output)["props"]["nested"][0]["password"] == "[REDACTED]"


def test_formatter_omits_exception_text():
    try:
        raise ValueError("sensitive-exception-value")
    except ValueError:
        record = logging.LogRecord(
            "test", logging.ERROR, "", 0, "Static message", (), sys.exc_info()
        )
    output = SafeJSONFormatter().format(record)
    assert "sensitive-exception-value" not in output
    assert json.loads(output)["exception_type"] == "ValueError"


def test_uvicorn_exception_logging_uses_redacting_formatter(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    # Simulate Uvicorn's own handler, which would otherwise print raw tracebacks.
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "handlers", [logging.StreamHandler(stream)])
        monkeypatch.setattr(logger, "propagate", False)
        monkeypatch.setattr(logger, "level", logging.INFO)
    setup_logging()
    try:
        raise RuntimeError("synthetic-server-password")
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert "synthetic-server-password" not in lines[0]
    assert json.loads(lines[0])["exception_type"] == "RuntimeError"
