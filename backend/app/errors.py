"""Turns every failure into one RFC 7807 response. The only place that sees FastAPI's own exceptions."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import STATUS_BY_CODE, TITLE_BY_CODE, DomainError, ErrorCode, FieldError
from app.core.logging import correlation_id_var
from app.middleware import HEADER, new_correlation_id
from app.schemas.problem import ProblemDetail, ProblemFieldError

logger = logging.getLogger("app.errors")

PROBLEM_MEDIA_TYPE = "application/problem+json"

_CODE_BY_STATUS: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}

_DOCUMENTED = (400, 401, 403, 404, 409, 413, 422, 429)

# Attached to the versioned router so the OpenAPI file lists every error status and the full code enum.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ProblemDetail, "description": TITLE_BY_CODE[code]}
    for status, code in [(s, _CODE_BY_STATUS[s]) for s in _DOCUMENTED] + [(500, ErrorCode.INTERNAL_ERROR)]
}


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", None) or correlation_id_var.get() or new_correlation_id())


def problem_response(
    request: Request,
    code: ErrorCode,
    detail: str,
    *,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    correlation_id = _correlation_id(request)
    status = STATUS_BY_CODE[code]
    body = ProblemDetail(
        type=f"urn:daftar:error:{code.value}",
        title=TITLE_BY_CODE[code],
        status=status,
        detail=detail,
        code=code,
        correlation_id=correlation_id,
        errors=[ProblemFieldError(field=e.field, message=e.message, code=e.code) for e in errors or []],
    )
    return JSONResponse(
        body.model_dump(mode="json"),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers={**(headers or {}), HEADER: correlation_id},
    )


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return problem_response(request, exc.code, exc.detail, errors=exc.errors, headers=exc.headers)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        FieldError(
            field=".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
            message=str(item["msg"]),
            code=str(item["type"]),
        )
        for item in exc.errors()
    ]
    return problem_response(request, ErrorCode.VALIDATION_ERROR, "One or more fields are invalid.", errors=errors)


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _CODE_BY_STATUS.get(exc.status_code)
    if code is None:
        code = ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.BAD_REQUEST
    detail = {
        ErrorCode.NOT_FOUND: "There is nothing at this address.",
        ErrorCode.METHOD_NOT_ALLOWED: "This address does not accept that method.",
    }.get(code, TITLE_BY_CODE[code])
    headers = dict(exc.headers) if exc.headers else None
    return problem_response(request, code, detail, headers=headers)


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = _correlation_id(request)
    token = correlation_id_var.set(correlation_id)
    try:
        logger.error("unhandled error", exc_info=exc)
    finally:
        correlation_id_var.reset(token)
    return problem_response(
        request,
        ErrorCode.INTERNAL_ERROR,
        "Something went wrong. Quote the correlation id if you contact support.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected)
