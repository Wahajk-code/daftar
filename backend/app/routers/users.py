from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.enums import Role
from app.deps import ClockDep, InviteServiceDep, OutboxDep, PrincipalDep, UserServiceDep, roles
from app.schemas.auth import Accepted
from app.schemas.page import Page, PageParamsDep
from app.schemas.users import InviteCreate, InviteRead, RoleChange, UserRead

users = APIRouter(prefix="/users", tags=["users"])
invites = APIRouter(prefix="/invites", tags=["invites"])


@users.get("", operation_id="list_users", **roles(Role.ADMIN))
def list_users(
    service: UserServiceDep,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Matches name or email.")] = None,
    role: Role | None = None,
    is_active: bool | None = None,
) -> Page[UserRead]:
    rows, total = service.list_users(
        q=q.strip().lower() if q else None,
        role=role,
        is_active=is_active,
        sort=page.sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page(items=[UserRead.model_validate(r) for r in rows], total=total, limit=page.limit, offset=page.offset)


@users.get("/{user_id}", operation_id="get_user", **roles(Role.ADMIN))
def get_user(user_id: int, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(service.get(user_id))


@users.post("/{user_id}/role", operation_id="change_user_role", **roles(Role.ADMIN))
def change_user_role(user_id: int, body: RoleChange, actor: PrincipalDep, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(service.change_role(actor, user_id, body.role))


@users.post("/{user_id}/deactivate", operation_id="deactivate_user", **roles(Role.ADMIN))
def deactivate_user(user_id: int, actor: PrincipalDep, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(service.set_active(actor, user_id, active=False))


@users.post("/{user_id}/reactivate", operation_id="reactivate_user", **roles(Role.ADMIN))
def reactivate_user(user_id: int, actor: PrincipalDep, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(service.set_active(actor, user_id, active=True))


@users.post(
    "/{user_id}/reset-password",
    operation_id="trigger_password_reset",
    status_code=status.HTTP_202_ACCEPTED,
    **roles(Role.ADMIN),
)
def trigger_password_reset(user_id: int, actor: PrincipalDep, service: UserServiceDep, outbox: OutboxDep) -> Accepted:
    """Email the user a reset link. The Admin never sees or sets the password."""
    service.trigger_reset(actor, user_id)
    outbox.dispatch()
    return Accepted()


@invites.get("", operation_id="list_invites", **roles(Role.ADMIN))
def list_invites(service: InviteServiceDep, page: PageParamsDep, clock: ClockDep) -> Page[InviteRead]:
    rows, total = service.list_invites(sort=page.sort, limit=page.limit, offset=page.offset)
    now = clock.now()
    return Page(items=[InviteRead.of(r, now) for r in rows], total=total, limit=page.limit, offset=page.offset)


@invites.post("", operation_id="create_invite", status_code=status.HTTP_201_CREATED, **roles(Role.ADMIN))
def create_invite(
    body: InviteCreate, actor: PrincipalDep, service: InviteServiceDep, outbox: OutboxDep, clock: ClockDep
) -> InviteRead:
    row = service.invite(actor, body.email, body.role)
    outbox.dispatch()
    return InviteRead.of(row, clock.now())


@invites.post("/{invite_id}/resend", operation_id="resend_invite", **roles(Role.ADMIN))
def resend_invite(
    invite_id: int, actor: PrincipalDep, service: InviteServiceDep, outbox: OutboxDep, clock: ClockDep
) -> InviteRead:
    row = service.resend(actor, invite_id)
    outbox.dispatch()
    return InviteRead.of(row, clock.now())


@invites.post("/{invite_id}/revoke", operation_id="revoke_invite", **roles(Role.ADMIN))
def revoke_invite(invite_id: int, actor: PrincipalDep, service: InviteServiceDep, clock: ClockDep) -> InviteRead:
    return InviteRead.of(service.revoke(actor, invite_id), clock.now())
