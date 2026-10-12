"""Turns every failure into one RFC 7807 response. The only place that sees FastAPI's own exceptions."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
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


# Rules the database enforces, mapped to the error a person should see. A service that lets one fire needs no
# try/except of its own: the constraint name is enough.
CONSTRAINT_ERRORS: dict[str, tuple[ErrorCode, str, str | None]] = {
    "uq_users_email": (ErrorCode.EMAIL_TAKEN, "That email already has an account.", "email"),
    "uq_auth_tokens_pending_invite_email": (
        ErrorCode.INVITE_PENDING,
        "An invitation is already waiting for that email.",
        "email",
    ),
    "uq_vendors_name_lower": (ErrorCode.DUPLICATE_VALUE, "A vendor with this name already exists.", "name"),
    "uq_accounts_code": (ErrorCode.DUPLICATE_VALUE, "An account with this code already exists.", "code"),
    "uq_cost_centers_code": (ErrorCode.DUPLICATE_VALUE, "A cost centre with this code already exists.", "code"),
    "uq_projects_code": (ErrorCode.DUPLICATE_VALUE, "A project or product with this code already exists.", "code"),
    "uq_categories_name_lower": (ErrorCode.DUPLICATE_VALUE, "A category with this name already exists.", "name"),
    "accounts_parent_not_postable": (
        ErrorCode.ACCOUNT_NOT_POSTABLE,
        "A parent account cannot be posted to, and a postable account cannot have children.",
        None,
    ),
    "users_keep_an_active_admin": (
        ErrorCode.LAST_ADMIN_PROTECTED,
        "This is the last active Admin. Make someone else an Admin first.",
        None,
    ),
    "no_overlapping_rules": (
        ErrorCode.TAX_RULE_OVERLAP,
        "Another rule for the same kind of supplier already covers some of those dates.",
        "effective_from",
    ),
    "no_overlapping_closed_ranges": (
        ErrorCode.PERIOD_OVERLAP,
        "Those dates overlap a period that is already closed.",
        "start_date",
    ),
    "expense_allocations_consistent": (
        ErrorCode.ALLOCATION_MISMATCH,
        "The allocation does not add up to the expense.",
        "allocation",
    ),
    "document_is_not_a_draft": (ErrorCode.DOCUMENT_LOCKED, "Only a draft can be changed.", None),
    "ck_expenses_amount_positive": (ErrorCode.VALIDATION_ERROR, "The amount must be more than zero.", "amount"),
    "ck_expenses_tax_within_amount": (
        ErrorCode.VALIDATION_ERROR,
        "The tax cannot be more than the amount.",
        "tax_amount",
    ),
    "ck_expenses_direct_has_attribution_indirect_has_none": (
        ErrorCode.VALIDATION_ERROR,
        "A direct expense needs a project, product or cost centre; an indirect one has none.",
        "project_id",
    ),
    "ck_purchases_payable_not_negative": (
        ErrorCode.PAYABLE_NEGATIVE,
        "The withholdings come to more than the amount.",
        "lines",
    ),
    "ck_purchase_lines_payable_not_negative": (
        ErrorCode.PAYABLE_NEGATIVE,
        "The withholdings come to more than the amount.",
        "lines",
    ),
    "ck_purchases_tax_invoice_has_a_number": (
        ErrorCode.VALIDATION_ERROR,
        "A tax invoice needs its number.",
        "invoice_number",
    ),
    "voucher_balanced": (
        ErrorCode.VOUCHER_UNBALANCED,
        "Total debits must equal total credits.",
        "lines",
    ),
    "voucher_line_account_postable": (
        ErrorCode.ACCOUNT_NOT_POSTABLE,
        "A parent account cannot be posted to. Choose one of its sub-accounts.",
        "lines",
    ),
    "account_has_postings": (
        ErrorCode.ACCOUNT_HAS_POSTINGS,
        "That account already has postings, so it cannot become a parent.",
        None,
    ),
    "uq_vouchers_expense_id": (ErrorCode.ALREADY_GENERATED, "A voucher was already generated from this expense.", None),
    "uq_vouchers_purchase_id": (
        ErrorCode.ALREADY_GENERATED,
        "A voucher was already generated from this purchase.",
        None,
    ),
    "uq_vouchers_post_key": (ErrorCode.IDEMPOTENCY_KEY_REUSED, "That Idempotency-Key was used for another post.", None),
    "uq_vouchers_void_key": (ErrorCode.IDEMPOTENCY_KEY_REUSED, "That Idempotency-Key was used for another void.", None),
    "uq_vouchers_reversal_of_id": (ErrorCode.CONFLICT, "That voucher already has a reversal.", None),
    "ck_vendors_registered_has_ntn_and_strn": (
        ErrorCode.VALIDATION_ERROR,
        "A sales-tax-registered vendor needs both an NTN and an STRN.",
        "ntn",
    ),
}


async def handle_integrity_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IntegrityError)
    diag = getattr(exc.orig, "diag", None)
    known = CONSTRAINT_ERRORS.get(getattr(diag, "constraint_name", None) or "")
    if known is None:
        return await handle_unexpected(request, exc)
    code, detail, field = known
    errors = [FieldError(field, detail, "constraint")] if field else None
    return problem_response(request, code, detail, errors=errors)


async def handle_stale_data(request: Request, exc: Exception) -> JSONResponse:
    return problem_response(
        request, ErrorCode.VERSION_CONFLICT, "Someone else changed this record. Reload it and try again."
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(StaleDataError, handle_stale_data)
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected)
