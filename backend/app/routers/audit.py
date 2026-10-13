"""The audit log, for Admins to read. There is no way to change or delete an entry."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.enums import Role
from app.deps import AuditLogServiceDep, roles
from app.schemas.audit import AuditEventRead
from app.schemas.page import Page, PageParamsDep

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", operation_id="list_audit_events", **roles(Role.ADMIN))
def list_audit_events(
    service: AuditLogServiceDep,
    page: PageParamsDep,
    actor_id: int | None = None,
    entity_type: Annotated[
        str | None, Query(max_length=50, description="For example expense, voucher or user.")
    ] = None,
    entity_id: int | None = None,
    action: Annotated[str | None, Query(max_length=100, description="Part of an action name, such as posted.")] = None,
    date_from: Annotated[date | None, Query(description="First day, inclusive, in the display zone.")] = None,
    date_to: Annotated[date | None, Query(description="Last day, inclusive, in the display zone.")] = None,
) -> Page[AuditEventRead]:
    """Newest first. Each entry says who did what to which record and, where it applies, the values before and after."""
    rows, total = service.search(
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=page.limit,
        offset=page.offset,
    )
    items = [
        AuditEventRead(
            id=event.id,
            occurred_at=event.occurred_at,
            actor_id=event.actor_id,
            actor_name=actor_name,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            before=event.before,
            after=event.after,
            correlation_id=event.correlation_id,
        )
        for event, actor_name in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
