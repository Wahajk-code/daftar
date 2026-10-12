"""The one error vocabulary. Every failure the API reports is a DomainError carrying a code from ErrorCode."""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    # Request shape and access
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    CONFLICT = "CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    # Status machine
    INVALID_TRANSITION = "INVALID_TRANSITION"
    SELF_APPROVAL_FORBIDDEN = "SELF_APPROVAL_FORBIDDEN"
    DOCUMENT_INCOMPLETE = "DOCUMENT_INCOMPLETE"
    VOUCHER_UNBALANCED = "VOUCHER_UNBALANCED"
    COMMENT_REQUIRED = "COMMENT_REQUIRED"
    REASON_REQUIRED = "REASON_REQUIRED"
    PERIOD_CLOSED = "PERIOD_CLOSED"
    REVERSAL_NOT_VOIDABLE = "REVERSAL_NOT_VOIDABLE"
    # Server
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.SELF_APPROVAL_FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.CONFLICT: 409,
    ErrorCode.VERSION_CONFLICT: 409,
    ErrorCode.INVALID_TRANSITION: 409,
    ErrorCode.PERIOD_CLOSED: 409,
    ErrorCode.REVERSAL_NOT_VOIDABLE: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.DOCUMENT_INCOMPLETE: 422,
    ErrorCode.VOUCHER_UNBALANCED: 422,
    ErrorCode.COMMENT_REQUIRED: 422,
    ErrorCode.REASON_REQUIRED: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
}

TITLE_BY_CODE: dict[ErrorCode, str] = {
    ErrorCode.BAD_REQUEST: "The request could not be understood",
    ErrorCode.VALIDATION_ERROR: "The request has invalid fields",
    ErrorCode.UNAUTHENTICATED: "Sign in required",
    ErrorCode.FORBIDDEN: "Not allowed",
    ErrorCode.NOT_FOUND: "Not found",
    ErrorCode.METHOD_NOT_ALLOWED: "Method not allowed",
    ErrorCode.PAYLOAD_TOO_LARGE: "The request is too large",
    ErrorCode.RATE_LIMITED: "Too many requests",
    ErrorCode.CONFLICT: "Conflict",
    ErrorCode.VERSION_CONFLICT: "The record changed since it was loaded",
    ErrorCode.INVALID_TRANSITION: "That status change is not allowed",
    ErrorCode.SELF_APPROVAL_FORBIDDEN: "You cannot approve a document you created",
    ErrorCode.DOCUMENT_INCOMPLETE: "The document is incomplete",
    ErrorCode.VOUCHER_UNBALANCED: "Debits and credits do not match",
    ErrorCode.COMMENT_REQUIRED: "A comment is required",
    ErrorCode.REASON_REQUIRED: "A reason is required",
    ErrorCode.PERIOD_CLOSED: "The accounting period is closed",
    ErrorCode.REVERSAL_NOT_VOIDABLE: "A reversal cannot be voided",
    ErrorCode.INTERNAL_ERROR: "Something went wrong on our side",
    ErrorCode.SERVICE_UNAVAILABLE: "The service is not ready",
}


@dataclass(frozen=True)
class FieldError:
    """One field-level problem, with a path such as ``lines.2.debit``."""

    field: str
    message: str
    code: str | None = None


class DomainError(Exception):
    """Base for every error the API reports on purpose. Subclasses fix the code; the handler fixes the status."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        detail: str,
        *,
        code: ErrorCode | None = None,
        errors: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        if code is not None:
            self.code = code
        self.detail = detail
        self.errors = errors or []
        self.headers = headers or {}

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE[self.code]


class BadRequestError(DomainError):
    code = ErrorCode.BAD_REQUEST


class ValidationFailedError(DomainError):
    code = ErrorCode.VALIDATION_ERROR


class UnauthenticatedError(DomainError):
    code = ErrorCode.UNAUTHENTICATED


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT


class VersionConflictError(DomainError):
    code = ErrorCode.VERSION_CONFLICT


class InvalidTransitionError(DomainError):
    code = ErrorCode.INVALID_TRANSITION


class GuardFailedError(DomainError):
    """A transition guard refused. The code names the guard."""


class ServiceUnavailableError(DomainError):
    code = ErrorCode.SERVICE_UNAVAILABLE


class RateLimitedError(DomainError):
    code = ErrorCode.RATE_LIMITED

    def __init__(self, detail: str, *, retry_after_seconds: int) -> None:
        super().__init__(detail, headers={"Retry-After": str(max(1, retry_after_seconds))})
        self.retry_after_seconds = max(1, retry_after_seconds)
