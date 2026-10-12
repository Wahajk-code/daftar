from app.core.errors import (
    STATUS_BY_CODE,
    TITLE_BY_CODE,
    DomainError,
    ErrorCode,
    NotFoundError,
    RateLimitedError,
)


def test_every_code_has_a_status_and_a_title() -> None:
    assert set(STATUS_BY_CODE) == set(ErrorCode)
    assert set(TITLE_BY_CODE) == set(ErrorCode)


def test_statuses_follow_the_api_contract() -> None:
    assert STATUS_BY_CODE[ErrorCode.INVALID_TRANSITION] == 409
    assert STATUS_BY_CODE[ErrorCode.VERSION_CONFLICT] == 409
    assert STATUS_BY_CODE[ErrorCode.SELF_APPROVAL_FORBIDDEN] == 403
    assert STATUS_BY_CODE[ErrorCode.VOUCHER_UNBALANCED] == 422
    assert STATUS_BY_CODE[ErrorCode.PERIOD_CLOSED] == 409  # domain-rules.md section 4
    assert STATUS_BY_CODE[ErrorCode.RATE_LIMITED] == 429
    assert STATUS_BY_CODE[ErrorCode.INTERNAL_ERROR] == 500


def test_a_subclass_fixes_the_code_and_the_status_follows() -> None:
    error = NotFoundError("No such vendor.")
    assert error.code is ErrorCode.NOT_FOUND
    assert error.status_code == 404
    assert isinstance(error, DomainError)


def test_a_code_may_be_chosen_per_instance() -> None:
    assert DomainError("Closed.", code=ErrorCode.PERIOD_CLOSED).status_code == 409


def test_rate_limited_carries_retry_after_of_at_least_one_second() -> None:
    assert RateLimitedError("Slow down.", retry_after_seconds=42).headers == {"Retry-After": "42"}
    assert RateLimitedError("Slow down.", retry_after_seconds=0).headers == {"Retry-After": "1"}
