"""The approval workflow shared by expenses, purchases and (in Pass 4) vouchers.

A document service locks the row, then asks this engine to move it. The engine builds the facts a guard needs, lets
`core/transitions.py` decide (the only place a status is assigned), and records the move in the history and the
audit log in the same transaction. Nothing here commits: the calling service does."""

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.enums import DocumentStatus, DocumentType
from app.core.errors import ErrorCode, FieldError, GuardFailedError, VersionConflictError
from app.core.principal import Principal
from app.core.transitions import TRANSITIONS, Transition, TransitionContext, apply_transition
from app.models.documents import DocumentEvent
from app.repositories import documents as document_repository
from app.services.audit import AuditService

S = DocumentStatus

# What each move is called, in the API and in the history.
ACTION_NAMES: dict[tuple[DocumentStatus, DocumentStatus], str] = {
    (S.DRAFT, S.SUBMITTED): "submit",
    (S.SUBMITTED, S.APPROVED): "approve",
    (S.SUBMITTED, S.REJECTED): "reject",
    (S.REJECTED, S.DRAFT): "reopen",
    (S.APPROVED, S.POSTED): "post",
    (S.POSTED, S.VOID): "void",
}
PAST_TENSE = {
    "submit": "submitted",
    "approve": "approved",
    "reject": "rejected",
    "reopen": "reopened",
    "post": "posted",
    "void": "voided",
}
# Moves a person asks for directly. Posting and voiding happen through vouchers (Pass 4).
DIRECT_ACTIONS = ("submit", "approve", "reject", "reopen")


class WorkflowDocument(Protocol):
    id: int
    status: DocumentStatus
    created_by: int
    version: int


class Workflow:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._audit = AuditService(session, clock)

    def move(
        self,
        document: WorkflowDocument,
        document_type: DocumentType,
        actor: Principal,
        target: DocumentStatus,
        *,
        expected_version: int,
        comment: str | None = None,
        reason: str | None = None,
        problems: Sequence[FieldError] = (),
    ) -> Transition:
        """Move a locked document to `target`, or raise the error that says why not."""
        if document.version != expected_version:
            raise VersionConflictError("Someone else changed this record. Reload it and try again.")
        source = document.status
        context = TransitionContext(
            actor_id=actor.id,
            actor_role=actor.role,
            creator_id=document.created_by,
            comment=comment,
            reason=reason,
            is_complete=not problems,
        )
        try:
            transition = apply_transition(document, document_type, target, context)
        except GuardFailedError as error:
            if error.code is ErrorCode.DOCUMENT_INCOMPLETE:
                error.errors = list(problems)
            raise
        action = ACTION_NAMES[(source, target)]
        past = PAST_TENSE[action]
        document_repository.add_event(
            self._session,
            DocumentEvent(
                document_type=document_type,
                document_id=document.id,
                action=past,
                from_status=source,
                to_status=target,
                actor_id=actor.id,
                comment=(comment or reason or "").strip() or None,
                created_at=self._clock.now(),
            ),
        )
        self._audit.record(
            actor_id=actor.id,
            action=f"{document_type.value}.{past}",
            entity_type=document_type.value,
            entity_id=document.id,
            before={"status": source.value},
            after={"status": target.value, **({"comment": comment} if comment else {})},
        )
        return transition

    def record_creation(self, document: WorkflowDocument, document_type: DocumentType, actor: Principal) -> None:
        document_repository.add_event(
            self._session,
            DocumentEvent(
                document_type=document_type,
                document_id=document.id,
                action="created",
                from_status=None,
                to_status=document.status,
                actor_id=actor.id,
                created_at=self._clock.now(),
            ),
        )


def available_actions(
    document_type: DocumentType, status: DocumentStatus, creator_id: int, actor: Principal
) -> list[str]:
    """The moves this person may make from here, for the screen to show. Whether the document is complete is not judged:
    that is explained when they try to submit."""
    found: list[str] = []
    for transition in TRANSITIONS:
        if transition.document_type is not document_type or transition.source is not status:
            continue
        action = ACTION_NAMES[(transition.source, transition.target)]
        if action not in DIRECT_ACTIONS or actor.role not in transition.roles:
            continue
        is_author = actor.id == creator_id
        if action in {"submit", "reopen"} and not is_author:
            continue
        if action == "approve" and is_author:
            continue
        found.append(action)
    return found


def may_edit(actor: Principal, creator_id: int, status: DocumentStatus) -> bool:
    return actor.id == creator_id and status is DocumentStatus.DRAFT
