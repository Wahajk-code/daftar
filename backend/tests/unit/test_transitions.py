import itertools
from dataclasses import replace

import pytest

from app.core.enums import DocumentStatus, DocumentType, Role
from app.core.errors import DomainError, ErrorCode, ForbiddenError, GuardFailedError, InvalidTransitionError
from app.core.transitions import (
    TRANSITIONS,
    TransitionContext,
    apply_transition,
    check_transition,
    find_transition,
)

S = DocumentStatus
T = DocumentType
ALL_ROLES = list(Role)

# The expected machine, written out independently of the table in the code: who may make each move.
AUTHORS = {Role.ADMIN, Role.ACCOUNTANT, Role.STAFF}
BOOKKEEPERS = {Role.ADMIN, Role.ACCOUNTANT}
REVIEWERS = {Role.ADMIN, Role.APPROVER}


def expected_moves(document_type: DocumentType) -> dict[tuple[DocumentStatus, DocumentStatus], set[Role]]:
    authors = AUTHORS if document_type is T.EXPENSE else BOOKKEEPERS
    moves = {
        (S.DRAFT, S.SUBMITTED): authors,
        (S.SUBMITTED, S.APPROVED): REVIEWERS,
        (S.SUBMITTED, S.REJECTED): REVIEWERS,
        (S.REJECTED, S.DRAFT): authors,
        (S.APPROVED, S.POSTED): BOOKKEEPERS,
    }
    if document_type is T.VOUCHER:
        moves[(S.POSTED, S.VOID)] = {Role.ADMIN}
    return moves


def context(role: Role, *, source: DocumentStatus, target: DocumentStatus) -> TransitionContext:
    """A context in which every guard passes, so only the pair and the role decide the outcome."""
    actor_id = 2
    # Reopening is for the author alone; every other move needs a different person than the author.
    creator_id = actor_id if (source, target) == (S.REJECTED, S.DRAFT) else 1
    return TransitionContext(
        actor_id=actor_id,
        actor_role=role,
        creator_id=creator_id,
        comment="Looks wrong",
        reason="Entered twice",
    )


class Document:
    def __init__(self, status: DocumentStatus) -> None:
        self.status = status


# The matrix: every entity, every ordered pair of statuses, every role -------------------------------------------


@pytest.mark.parametrize("document_type", list(T))
def test_f1_matrix_over_every_pair_and_role(document_type: DocumentType) -> None:
    expected = expected_moves(document_type)
    for source, target in itertools.product(S, S):
        for role in ALL_ROLES:
            ctx = context(role, source=source, target=target)
            where = f"{document_type.value} {source.value}->{target.value} as {role.value}"
            if (source, target) not in expected:
                with pytest.raises(InvalidTransitionError) as invalid:
                    check_transition(document_type, source, target, ctx)
                assert invalid.value.code is ErrorCode.INVALID_TRANSITION, where
                assert invalid.value.status_code == 409, where
            elif role not in expected[(source, target)]:
                with pytest.raises(ForbiddenError) as forbidden:
                    check_transition(document_type, source, target, ctx)
                assert forbidden.value.status_code == 403, where
            else:
                assert check_transition(document_type, source, target, ctx).target is target, where


def test_f1_the_table_has_exactly_the_expected_rows() -> None:
    for document_type in T:
        in_table = {(t.source, t.target) for t in TRANSITIONS if t.document_type is document_type}
        assert in_table == set(expected_moves(document_type))


def test_f1_the_table_has_no_duplicate_rows() -> None:
    keys = [(t.document_type, t.source, t.target) for t in TRANSITIONS]
    assert len(keys) == len(set(keys))


def test_only_vouchers_can_be_voided() -> None:
    assert find_transition(T.VOUCHER, S.POSTED, S.VOID) is not None
    assert find_transition(T.EXPENSE, S.POSTED, S.VOID) is None
    assert find_transition(T.PURCHASE, S.POSTED, S.VOID) is None


# Guards --------------------------------------------------------------------------------------------------------------


def guard_error(
    document_type: DocumentType,
    source: DocumentStatus,
    target: DocumentStatus,
    role: Role,
    **overrides: object,
) -> DomainError:
    ctx = replace(context(role, source=source, target=target), **overrides)  # type: ignore[arg-type]
    with pytest.raises(DomainError) as caught:
        check_transition(document_type, source, target, ctx)
    return caught.value


@pytest.mark.parametrize("document_type", list(T))
def test_a4_nobody_approves_their_own_document(document_type: DocumentType) -> None:
    for role in (Role.ADMIN, Role.APPROVER):
        error = guard_error(document_type, S.SUBMITTED, S.APPROVED, role, creator_id=2)
        assert error.code is ErrorCode.SELF_APPROVAL_FORBIDDEN
        assert error.status_code == 403


@pytest.mark.parametrize("comment", [None, "", "   \n"])
def test_rejecting_needs_a_comment(comment: str | None) -> None:
    error = guard_error(T.EXPENSE, S.SUBMITTED, S.REJECTED, Role.APPROVER, comment=comment)
    assert error.code is ErrorCode.COMMENT_REQUIRED
    assert error.status_code == 422


def test_only_the_author_reopens_a_rejected_document() -> None:
    error = guard_error(T.PURCHASE, S.REJECTED, S.DRAFT, Role.ADMIN, creator_id=1)
    assert error.code is ErrorCode.FORBIDDEN


@pytest.mark.parametrize("document_type", list(T))
def test_submitting_an_incomplete_document_is_refused(document_type: DocumentType) -> None:
    error = guard_error(document_type, S.DRAFT, S.SUBMITTED, Role.ADMIN, is_complete=False)
    assert error.code is ErrorCode.DOCUMENT_INCOMPLETE
    assert error.status_code == 422


def test_an_unbalanced_voucher_cannot_be_submitted_or_posted() -> None:
    submit = guard_error(T.VOUCHER, S.DRAFT, S.SUBMITTED, Role.ACCOUNTANT, is_balanced=False)
    post = guard_error(T.VOUCHER, S.APPROVED, S.POSTED, Role.ACCOUNTANT, is_balanced=False)
    assert submit.code is post.code is ErrorCode.VOUCHER_UNBALANCED


def test_posting_into_a_closed_period_is_a_conflict() -> None:
    error = guard_error(T.VOUCHER, S.APPROVED, S.POSTED, Role.ACCOUNTANT, period_open=False)
    assert error.code is ErrorCode.PERIOD_CLOSED
    assert error.status_code == 409


def test_voiding_needs_a_reason_and_an_open_period_and_a_voucher_that_is_not_a_reversal() -> None:
    assert guard_error(T.VOUCHER, S.POSTED, S.VOID, Role.ADMIN, reason=" ").code is ErrorCode.REASON_REQUIRED
    assert guard_error(T.VOUCHER, S.POSTED, S.VOID, Role.ADMIN, is_reversal=True).code is (
        ErrorCode.REVERSAL_NOT_VOIDABLE
    )
    assert guard_error(T.VOUCHER, S.POSTED, S.VOID, Role.ADMIN, period_open=False).code is ErrorCode.PERIOD_CLOSED


def test_the_role_is_checked_before_the_guards() -> None:
    # A Staff user approving their own, unbalanced, comment-less document is told about the role first.
    ctx = TransitionContext(actor_id=1, actor_role=Role.STAFF, creator_id=1, is_complete=False)
    with pytest.raises(ForbiddenError):
        check_transition(T.EXPENSE, S.SUBMITTED, S.APPROVED, ctx)


# Applying ------------------------------------------------------------------------------------------------------------


def test_apply_changes_the_status_only_when_allowed() -> None:
    document = Document(S.DRAFT)
    ctx = context(Role.STAFF, source=S.DRAFT, target=S.SUBMITTED)
    apply_transition(document, T.EXPENSE, S.SUBMITTED, ctx)
    assert document.status is S.SUBMITTED

    with pytest.raises(InvalidTransitionError):
        apply_transition(document, T.EXPENSE, S.POSTED, ctx)
    assert document.status is S.SUBMITTED

    incomplete = TransitionContext(actor_id=2, actor_role=Role.STAFF, creator_id=1, is_complete=False)
    draft = Document(S.DRAFT)
    with pytest.raises(GuardFailedError):
        apply_transition(draft, T.EXPENSE, S.SUBMITTED, incomplete)
    assert draft.status is S.DRAFT
