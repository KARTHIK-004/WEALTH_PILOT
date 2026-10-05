"""Phase 15 — RFC 7807 problem-details errors.

Extends Phase 0's `_problem_response` helper (previously inline in
`api/main.py`) with a proper `type`/`instance` and a small set of named
domain exceptions, so a route raises a meaningful Python exception
(`CustomerNotFoundError`, `ComplianceRejectedForApiError`, ...) instead of
constructing an HTTP response inline — the mapping from domain outcome to
HTTP status lives in exactly one place (`register_exception_handlers`),
per section 20's "map appropriately" / "do not convert known domain
outcomes into generic 500 errors."

Never includes a stack trace, a database URL, an API key, an environment
variable, a prompt, or chain-of-thought in any response body (section
18/49) — every problem body is built from a short, fixed `title`/`detail`
string the raising code supplies, never from `repr(exc)`/`traceback`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for a known domain outcome that should become an RFC
    7807 response with a specific status code — never a generic 500."""

    status_code: int = 500
    title: str = "Internal server error"

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class CustomerNotFoundError(ApiError):
    status_code = 404
    title = "Customer not found"


class AnalysisNotFoundError(ApiError):
    status_code = 404
    title = "Analysis not found"


class InvalidRequestError(ApiError):
    status_code = 400
    title = "Invalid request"


class HouseholdNotFoundError(ApiError):
    status_code = 404
    title = "Household not found"


class HouseholdMemberNotFoundError(ApiError):
    status_code = 404
    title = "Household member not found"


class HouseholdRecordNotFoundError(ApiError):
    """A household financial record (income, expense, asset, liability) that
    does not exist in THIS household (Phase 33). A record belonging to another
    household is reported the same way, so its existence is never revealed."""

    status_code = 404
    title = "Household record not found"


class IdentityRequiredError(ApiError):
    """A household route was called without a usable `X-Customer-Id`
    (Phase 32). The prototype has no server session, so the client's
    associated customer is the only identity there is; without it there is
    nothing to authorize against."""

    status_code = 401
    title = "Customer identity required"


class AccessDeniedError(ApiError):
    status_code = 403
    title = "Access denied"


class ConflictError(ApiError):
    """The request is well-formed but conflicts with the current state
    (a duplicate membership, a second primary, removing the primary)."""

    status_code = 409
    title = "Conflict"


class ServiceUnavailableError(ApiError):
    """A required backend component (a model artifact, the configured
    Gemini key) is missing or not ready -- section 20: 'missing
    model/service -> 503'."""

    status_code = 503
    title = "Service unavailable"


def problem_response(status_code: int, title: str, detail: str, *, type_: str = "about:blank", instance: str | None = None) -> JSONResponse:
    body = {"type": type_, "title": title, "status": status_code, "detail": detail}
    if instance is not None:
        body["instance"] = instance
    return JSONResponse(status_code=status_code, media_type="application/problem+json", content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return problem_response(exc.status_code, title=exc.title, detail=exc.detail, instance=str(request.url.path))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(exc.status_code, title=exc.detail or "HTTP error", detail=str(exc.detail), instance=str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # `exc.errors()` is Pydantic's own structured validation error list
        # (field locations + messages) -- never a raw stack trace.
        return problem_response(422, title="Validation error", detail=str(exc.errors()), instance=str(request.url.path))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Logged server-side only (never in the response body) -- and even
        # server-side, this is the exception message/type, never secrets:
        # nothing in this codebase logs an API key, a database URL, or a
        # Gemini prompt (section 38).
        logger.exception("Unhandled exception", extra={"path": str(request.url.path)})
        return problem_response(500, title="Internal server error", detail="An unexpected error occurred.", instance=str(request.url.path))
