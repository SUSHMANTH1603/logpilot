"""Global error hierarchy and standardized exception handlers conforming to D06 § 4.1."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error producing standardized error envelopes."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = 500,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class BadRequestError(AppError):
    def __init__(
        self,
        message: str = "Bad request.",
        code: str = "BAD_REQUEST",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=400, details=details)


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "The requested resource was not found.",
        code: str = "RESOURCE_NOT_FOUND",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=404, details=details)


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Request validation failed.",
        code: str = "VALIDATION_ERROR",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=422, details=details)


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "Authentication required or credentials invalid.",
        code: str = "UNAUTHORIZED",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=401, details=details)


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        code: str = "FORBIDDEN",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=403, details=details)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Resource state conflict.",
        code: str = "CONFLICT",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class ServiceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "A required service dependency is currently unavailable.",
        code: str = "SERVICE_UNAVAILABLE",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=503, details=details)


class RateLimitedError(AppError):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry later.",
        code: str = "RATE_LIMITED",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=429, details=details)


def format_error_response(
    code: str,
    message: str,
    request_id: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Format canonical D06 error JSON envelope."""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or [],
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform error handlers with FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        return format_error_response(
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        details = []
        for error in exc.errors():
            loc = ".".join(str(item) for item in error.get("loc", []) if item != "body")
            details.append(
                {
                    "field": loc or "request",
                    "issue": error.get("msg", "Invalid value"),
                }
            )
        return format_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=request_id,
            status_code=422,
            details=details,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "RESOURCE_NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
            503: "SERVICE_UNAVAILABLE",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        message = str(exc.detail) if exc.detail else "An HTTP error occurred."
        return format_error_response(
            code=code,
            message=message,
            request_id=request_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        # In strict adherence to D06 § 4.1 & D11: zero stack trace or internal database leakage
        return format_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
            request_id=request_id,
            status_code=500,
        )
