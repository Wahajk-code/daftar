from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Identity, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDict, UtcDateTime


class AuditEvent(Base):
    """Append only. The application role has insert and select on this table and nothing else."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=text("now()"))
    # Null for events with no signed-in user, such as a failed login or a self-service reset request.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    before: Mapped[JsonDict | None] = mapped_column(JSONB, default=None)
    after: Mapped[JsonDict | None] = mapped_column(JSONB, default=None)
    correlation_id: Mapped[str | None] = mapped_column(String(64), default=None)
