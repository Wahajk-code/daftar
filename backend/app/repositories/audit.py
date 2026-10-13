from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


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


def search(
    session: Session,
    *,
    actor_id: int | None,
    entity_type: str | None,
    entity_id: int | None,
    action: str | None,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[AuditEvent, str | None]], int]:
    """A page of the audit log, newest first, with the name of whoever acted. `end` is exclusive."""
    statement = select(AuditEvent, User.full_name.label("actor_name")).outerjoin(User, User.id == AuditEvent.actor_id)
    if actor_id is not None:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if entity_type:
        statement = statement.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(AuditEvent.entity_id == entity_id)
    if action:
        statement = statement.where(func.lower(AuditEvent.action).like(f"%{action.lower()}%"))
    if start is not None:
        statement = statement.where(AuditEvent.occurred_at >= start)
    if end is not None:
        statement = statement.where(AuditEvent.occurred_at < end)
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    page = session.execute(statement.order_by(AuditEvent.id.desc()).limit(limit).offset(offset))
    return [(event, name) for event, name in page], total
