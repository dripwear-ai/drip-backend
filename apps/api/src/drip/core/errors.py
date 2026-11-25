import logging
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger("drip.errors")


class DripException(Exception):
    """Base exception for all DRIP domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class NotFoundException(DripException):
    def __init__(self, message: str, code: str = "NOT_FOUND"):
        super().__init__(message, code=code, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(DripException):
    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(message, code=code, status_code=status.HTTP_409_CONFLICT)


class ServiceUnavailableException(DripException):
    def __init__(self, message: str, code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(message, code=code, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def setup_error_handlers(app: FastAPI) -> None:
    """Register uniform exception handlers adhering to the DRIP error contract."""

    @app.exception_handler(DripException)
    async def handle_drip_exception(request: Request, exc: DripException) -> JSONResponse:
        logger.warning("Domain request rejected", extra={"props": {"status_code": exc.status_code}})
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Error inputs, custom validator messages, paths and contexts can contain secrets.
        logger.warning(
            "Request validation failed", extra={"props": {"error_count": len(exc.errors())}}
        )
        formatted_details = [
            {"loc": err.get("loc", []), "msg": "Invalid value", "type": err.get("type", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "The request payload failed schema validation.",
                "details": formatted_details,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "HTTP request failed"
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, f"HTTP_{exc.status_code}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "code": code,
                "message": message,
                "details": [],
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request exception", extra={"props": {"exception_type": type(exc).__name__}}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred. Please try again later.",
                "details": [],
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
