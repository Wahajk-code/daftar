"""The one status machine. Expenses, purchases and vouchers all change status here and nowhere else.

Each row of TRANSITIONS names the document type, the two statuses, the roles allowed and the guards, in order. The check
runs: is the pair in the table (409 INVALID_TRANSITION), is the role allowed (403 FORBIDDEN), then each guard in turn.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.core.enums import DocumentStatus, DocumentType, Role
from app.core.errors import (
    ErrorCode,
    ForbiddenError,
    GuardFailedError,
    InvalidTransitionError,
)

S = DocumentStatus
T = DocumentType


class Statused(Protocol):
    """Anything with a status: an expense, a purchase or a voucher."""

    status: DocumentStatus


@dataclass(frozen=True)
class TransitionContext:
    """The facts a guard may look at. The service fills them from the document and the request."""

    actor_id: int
    actor_role: Role
    creator_id: int
    comment: str | None = None
    reason: str | None = None
    is_complete: bool = True
    is_balanced: bool = True
    period_open: bool = True
    is_reversal: bool = False


Guard = Callable[[TransitionContext], None]


def _blank(text: str | None) -> bool:
    return text is None or not text.strip()


def author_only(ctx: TransitionContext) -> None:
    if ctx.actor_id != ctx.creator_id:
        raise ForbiddenError("Only the author can reopen a rejected document.")


def not_own_document(ctx: TransitionContext) -> None:
    if ctx.actor_id == ctx.creator_id:
        raise GuardFailedError("You cannot approve a document you created.", code=ErrorCode.SELF_APPROVAL_FORBIDDEN)


def complete(ctx: TransitionContext) -> None:
    if not ctx.is_complete:
        raise GuardFailedError("The document is incomplete.", code=ErrorCode.DOCUMENT_INCOMPLETE)


def balanced(ctx: TransitionContext) -> None:
    if not ctx.is_balanced:
        raise GuardFailedError("Total debits must equal total credits.", code=ErrorCode.VOUCHER_UNBALANCED)


def comment_required(ctx: TransitionContext) -> None:
    if _blank(ctx.comment):
        raise GuardFailedError("A comment is required to reject.", code=ErrorCode.COMMENT_REQUIRED)


def reason_required(ctx: TransitionContext) -> None:
    if _blank(ctx.reason):
        raise GuardFailedError("A reason is required to void.", code=ErrorCode.REASON_REQUIRED)


def period_open(ctx: TransitionContext) -> None:
    if not ctx.period_open:
        raise GuardFailedError("The accounting period is closed.", code=ErrorCode.PERIOD_CLOSED)


def not_a_reversal(ctx: TransitionContext) -> None:
    if ctx.is_reversal:
        raise GuardFailedError("A reversing voucher cannot be voided.", code=ErrorCode.REVERSAL_NOT_VOIDABLE)


@dataclass(frozen=True)
class Transition:
    document_type: DocumentType
    source: DocumentStatus
    target: DocumentStatus
    roles: frozenset[Role]
    guards: tuple[Guard, ...] = ()


_AUTHORS = frozenset({Role.ADMIN, Role.ACCOUNTANT, Role.STAFF})  # who may create and submit expenses
_BOOKKEEPERS = frozenset({Role.ADMIN, Role.ACCOUNTANT})
_REVIEWERS = frozenset({Role.ADMIN, Role.APPROVER})


def _flow(
    document_type: DocumentType,
    authors: frozenset[Role],
    *,
    submit_guards: tuple[Guard, ...] = (complete,),
    post_guards: tuple[Guard, ...] = (period_open,),
    extra: tuple[Transition, ...] = (),
) -> tuple[Transition, ...]:
    return (
        Transition(document_type, S.DRAFT, S.SUBMITTED, authors, submit_guards),
        Transition(document_type, S.SUBMITTED, S.APPROVED, _REVIEWERS, (not_own_document,)),
        Transition(document_type, S.SUBMITTED, S.REJECTED, _REVIEWERS, (comment_required,)),
        Transition(document_type, S.REJECTED, S.DRAFT, authors, (author_only,)),
        Transition(document_type, S.APPROVED, S.POSTED, _BOOKKEEPERS, post_guards),
        *extra,
    )


TRANSITIONS: tuple[Transition, ...] = (
    *_flow(T.EXPENSE, _AUTHORS),
    *_flow(T.PURCHASE, _BOOKKEEPERS),
    *_flow(
        T.VOUCHER,
        _BOOKKEEPERS,
        submit_guards=(complete, balanced),
        post_guards=(balanced, period_open),
        extra=(Transition(T.VOUCHER, S.POSTED, S.VOID, _BOOKKEEPERS, (reason_required, not_a_reversal, period_open)),),
    ),
)

_BY_PAIR: dict[tuple[DocumentType, DocumentStatus, DocumentStatus], Transition] = {
    (t.document_type, t.source, t.target): t for t in TRANSITIONS
}


def find_transition(document_type: DocumentType, source: DocumentStatus, target: DocumentStatus) -> Transition | None:
    return _BY_PAIR.get((document_type, source, target))


def check_transition(
    document_type: DocumentType,
    source: DocumentStatus,
    target: DocumentStatus,
    ctx: TransitionContext,
) -> Transition:
    """Return the transition if it may happen now; otherwise raise the error the API reports."""
    transition = find_transition(document_type, source, target)
    if transition is None:
        raise InvalidTransitionError(f"A {document_type.value} cannot go from {source.value} to {target.value}.")
    if ctx.actor_role not in transition.roles:
        raise ForbiddenError(f"Your role cannot move a {document_type.value} to {target.value}.")
    for guard in transition.guards:
        guard(ctx)
    return transition


def apply_transition(
    document: Statused,
    document_type: DocumentType,
    target: DocumentStatus,
    ctx: TransitionContext,
) -> Transition:
    """The only place a document's status is assigned."""
    transition = check_transition(document_type, document.status, target, ctx)
    document.status = transition.target
    return transition


def start_posted(document: Statused) -> None:
    """Give a reversing voucher its status. A reversal is born Posted: it mirrors a voucher that was already
    approved and posted, so it never passes through approval. This is the only status assignment outside
    `apply_transition`."""
    document.status = DocumentStatus.POSTED
