from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def add(session: Session, event: AuditEvent) -> AuditEvent:
    """Insert inside the caller's transaction. Flushes so the id and any constraint failure surface now."""
    session.add(event)
    session.flush()
    return event


def list_for_entity(session: Session, entity_type: str, entity_id: int) -> list[AuditEvent]:
    statement = (
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.id)
    )
    return list(session.scalars(statement))
