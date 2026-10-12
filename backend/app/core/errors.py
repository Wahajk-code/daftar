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
    # Access and identity
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    REAUTH_FAILED = "REAUTH_FAILED"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    INVITE_PENDING = "INVITE_PENDING"
    SELF_CHANGE_FORBIDDEN = "SELF_CHANGE_FORBIDDEN"
    LAST_ADMIN_PROTECTED = "LAST_ADMIN_PROTECTED"
    # Master data
    ACCOUNT_NOT_POSTABLE = "ACCOUNT_NOT_POSTABLE"
    DUPLICATE_VALUE = "DUPLICATE_VALUE"
    TAX_RULE_OVERLAP = "TAX_RULE_OVERLAP"
    PERIOD_OVERLAP = "PERIOD_OVERLAP"
    # Status machine
    INVALID_TRANSITION = "INVALID_TRANSITION"
    SELF_APPROVAL_FORBIDDEN = "SELF_APPROVAL_FORBIDDEN"
    DOCUMENT_INCOMPLETE = "DOCUMENT_INCOMPLETE"
    VOUCHER_UNBALANCED = "VOUCHER_UNBALANCED"
    COMMENT_REQUIRED = "COMMENT_REQUIRED"
    REASON_REQUIRED = "REASON_REQUIRED"
    PERIOD_CLOSED = "PERIOD_CLOSED"
    REVERSAL_NOT_VOIDABLE = "REVERSAL_NOT_VOIDABLE"
    # Documents and attachments
    DOCUMENT_LOCKED = "DOCUMENT_LOCKED"
    ALLOCATION_MISMATCH = "ALLOCATION_MISMATCH"
    INACTIVE_REFERENCE = "INACTIVE_REFERENCE"
    TAX_RULE_MISSING = "TAX_RULE_MISSING"
    PAYABLE_NEGATIVE = "PAYABLE_NEGATIVE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    ATTACHMENT_LIMIT = "ATTACHMENT_LIMIT"
    # Server
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.TOKEN_INVALID: 400,
    ErrorCode.TOKEN_EXPIRED: 400,
    ErrorCode.TOKEN_REVOKED: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.REAUTH_FAILED: 403,
    ErrorCode.SELF_CHANGE_FORBIDDEN: 403,
    ErrorCode.SELF_APPROVAL_FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.CONFLICT: 409,
    ErrorCode.EMAIL_TAKEN: 409,
    ErrorCode.INVITE_PENDING: 409,
    ErrorCode.LAST_ADMIN_PROTECTED: 409,
    ErrorCode.DUPLICATE_VALUE: 409,
    ErrorCode.TAX_RULE_OVERLAP: 409,
    ErrorCode.PERIOD_OVERLAP: 409,
    ErrorCode.VERSION_CONFLICT: 409,
    ErrorCode.INVALID_TRANSITION: 409,
    ErrorCode.PERIOD_CLOSED: 409,
    ErrorCode.REVERSAL_NOT_VOIDABLE: 409,
    ErrorCode.DOCUMENT_LOCKED: 409,
    ErrorCode.ATTACHMENT_LIMIT: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.ALLOCATION_MISMATCH: 422,
    ErrorCode.INACTIVE_REFERENCE: 422,
    ErrorCode.TAX_RULE_MISSING: 422,
    ErrorCode.PAYABLE_NEGATIVE: 422,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 422,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.DOCUMENT_INCOMPLETE: 422,
    ErrorCode.VOUCHER_UNBALANCED: 422,
    ErrorCode.ACCOUNT_NOT_POSTABLE: 422,
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
    ErrorCode.DOCUMENT_LOCKED: "Only a draft can be changed",
    ErrorCode.ALLOCATION_MISMATCH: "The allocation does not add up",
    ErrorCode.INACTIVE_REFERENCE: "That record is no longer in use",
    ErrorCode.TAX_RULE_MISSING: "No withholding rate applies",
    ErrorCode.PAYABLE_NEGATIVE: "The amount payable would be negative",
    ErrorCode.UNSUPPORTED_FILE_TYPE: "That file type is not accepted",
    ErrorCode.ATTACHMENT_LIMIT: "This document has the most attachments it can hold",
    ErrorCode.INVALID_CREDENTIALS: "The email or password is incorrect",
    ErrorCode.REAUTH_FAILED: "The password you entered is incorrect",
    ErrorCode.TOKEN_INVALID: "This link is not valid",
    ErrorCode.TOKEN_EXPIRED: "This link has expired",
    ErrorCode.TOKEN_REVOKED: "This link was cancelled",
    ErrorCode.EMAIL_TAKEN: "That email already has an account",
    ErrorCode.INVITE_PENDING: "An invitation is already waiting for that email",
    ErrorCode.SELF_CHANGE_FORBIDDEN: "You cannot make that change to your own account",
    ErrorCode.LAST_ADMIN_PROTECTED: "The last active Admin cannot be removed",
    ErrorCode.ACCOUNT_NOT_POSTABLE: "That account cannot be posted to",
    ErrorCode.DUPLICATE_VALUE: "That value is already in use",
    ErrorCode.TAX_RULE_OVERLAP: "Another tax rule already covers those dates",
    ErrorCode.PERIOD_OVERLAP: "That period overlaps a closed period",
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


class ReauthFailedError(DomainError):
    code = ErrorCode.REAUTH_FAILED
