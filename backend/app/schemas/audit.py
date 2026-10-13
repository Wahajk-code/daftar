from typing import Any

from app.schemas.base import ResponseModel, UtcInstant


class AuditEventRead(ResponseModel):
    """One entry of the audit log: who did what to which record, and what changed."""

    id: int
    occurred_at: UtcInstant
    actor_id: int | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: int | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    correlation_id: str | None
