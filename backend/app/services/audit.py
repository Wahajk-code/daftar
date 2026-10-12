"""Audit rows are written in the caller's transaction, so a change and its record commit or roll back together.
This service never commits."""

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.logging import correlation_id_var
from app.models.audit import AuditEvent
from app.models.base import JsonDict
from app.repositories import audit as audit_repository


class AuditService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    def record(
        self,
        *,
        actor_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        before: JsonDict | None = None,
        after: JsonDict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            occurred_at=self._clock.now(),
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            correlation_id=correlation_id_var.get(),
        )
        return audit_repository.add(self._session, event)

    def history(self, entity_type: str, entity_id: int) -> list[AuditEvent]:
        return audit_repository.list_for_entity(self._session, entity_type, entity_id)
