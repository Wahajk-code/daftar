"""Dependency providers for routers: settings, session, clock, the signed-in user, role guards, services."""

import ipaddress
from functools import lru_cache
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.clock import Clock
from app.core.enums import Role
from app.core.errors import FieldError, ForbiddenError, UnauthenticatedError, ValidationFailedError
from app.core.mail import ConsoleMailer, Mailer, Outbox
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.security import Passwords, read_access_token, same_secret
from app.core.storage import Storage, make_storage
from app.db import get_session
from app.repositories import users as user_repository
from app.services.accounts import AccountService
from app.services.attachments import AttachmentService
from app.services.auth import AuthService
from app.services.expenses import ExpenseService
from app.services.invites import InviteService
from app.services.lookups import CategoryService, CostCenterService, ProjectService
from app.services.periods import PeriodService, PostingAccountService
from app.services.purchases import PurchaseService
from app.services.tax_rules import TaxRuleService
from app.services.users import UserService
from app.services.vendors import VendorService

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]

BFF_SECRET_HEADER = "X-Daftar-BFF-Secret"  # noqa: S105 - a header name, not a secret
BFF_CLIENT_IP_HEADER = "X-Daftar-Client-Ip"


@lru_cache
def get_clock() -> Clock:
    return Clock()


@lru_cache
def get_mailer() -> Mailer:
    return ConsoleMailer()


@lru_cache
def get_passwords() -> Passwords:
    settings = get_settings()
    return Passwords(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_kib,
        parallelism=settings.argon2_parallelism,
    )


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


ClockDep = Annotated[Clock, Depends(get_clock)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]
PasswordsDep = Annotated[Passwords, Depends(get_passwords)]
LimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


class RequestOutbox(Outbox):
    """Collects the emails a service wants sent. `dispatch` hands them to the background, after the response is ready;
    a router calls it only once the service has returned, which is after the commit."""

    def __init__(self, background: BackgroundTasks, mailer: Mailer) -> None:
        super().__init__()
        self._background = background
        self._mailer = mailer

    def dispatch(self) -> None:
        for message in self.messages:
            self._background.add_task(self._mailer.send_safely, message)


def get_outbox(background: BackgroundTasks, mailer: MailerDep) -> RequestOutbox:
    return RequestOutbox(background, mailer)


OutboxDep = Annotated[RequestOutbox, Depends(get_outbox)]


def get_client_ip(
    request: Request,
    settings: SettingsDep,
    secret: Annotated[str | None, Header(alias=BFF_SECRET_HEADER, include_in_schema=False)] = None,
    forwarded: Annotated[str | None, Header(alias=BFF_CLIENT_IP_HEADER, include_in_schema=False)] = None,
) -> str:
    """The caller's address. A forwarded address is believed only when it comes with the BFF's shared secret: the API is
    public, so anyone can send a header. Otherwise the connection address is used."""
    expected = settings.bff_shared_secret.get_secret_value() if settings.bff_shared_secret else None
    if forwarded and same_secret(secret, expected):
        try:
            return str(ipaddress.ip_address(forwarded.strip()))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


ClientIpDep = Annotated[str, Depends(get_client_ip)]


def get_principal(
    request: Request, session: SessionDep, settings: SettingsDep, clock: ClockDep, limiter: LimiterDep
) -> Principal:
    """Who is calling. The role is read from the database on every request, so a change applies at once."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthenticatedError("Sign in to continue.")
    user_id = read_access_token(token, secret_key=settings.secret_key.get_secret_value(), now=clock.now())
    user = user_repository.get(session, user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("Sign in to continue.")
    limiter.hit(("user_all", str(user.id)))  # the per-user safety net
    return Principal(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def roles(*allowed: Role) -> dict[str, Any]:
    """Route options that require one of these roles. The roles are also published in the OpenAPI file as `x-roles`,
    which the access-matrix test reads, so a route cannot be added without declaring who may call it."""

    def require(principal: PrincipalDep) -> Principal:
        if principal.role not in allowed:
            needed = " or ".join(role.value.capitalize() for role in allowed)
            raise ForbiddenError(f"This needs the {needed} role.")
        return principal

    return {"dependencies": [Depends(require)], "openapi_extra": {"x-roles": sorted(role.value for role in allowed)}}


# For the few routes that are open to anyone: sign in, refresh, reset, accept an invitation.
PUBLIC: dict[str, Any] = {"openapi_extra": {"x-public": True}}


def if_match_version(
    if_match: Annotated[str | None, Header(description="The `version` of the record you loaded.")] = None,
) -> int:
    """The version the client last saw, from the `If-Match` header. An update without one is refused."""
    problem = FieldError("If-Match", "Send the version you loaded in an If-Match header.", "required")
    if if_match is None:
        raise ValidationFailedError("Send the version you loaded in an If-Match header.", errors=[problem])
    try:
        return int(if_match.strip().strip('"'))
    except ValueError as exc:
        raise ValidationFailedError("The If-Match header must be a version number.", errors=[problem]) from exc


IfMatchDep = Annotated[int, Depends(if_match_version)]


def get_auth_service(
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    passwords: PasswordsDep,
    limiter: LimiterDep,
    outbox: OutboxDep,
) -> AuthService:
    return AuthService(session, clock, settings, passwords, limiter, outbox)


def get_user_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep, limiter: LimiterDep, outbox: OutboxDep
) -> UserService:
    return UserService(session, clock, settings, limiter, outbox)


def get_invite_service(
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    passwords: PasswordsDep,
    limiter: LimiterDep,
    outbox: OutboxDep,
) -> InviteService:
    return InviteService(session, clock, settings, passwords, limiter, outbox)


def get_vendor_service(
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    passwords: PasswordsDep,
    limiter: LimiterDep,
    outbox: OutboxDep,
) -> VendorService:
    return VendorService(session, clock, settings, passwords, limiter, outbox)


def get_account_service(session: SessionDep, clock: ClockDep) -> AccountService:
    return AccountService(session, clock)


def get_category_service(session: SessionDep, clock: ClockDep) -> CategoryService:
    return CategoryService(session, clock)


def get_cost_center_service(session: SessionDep, clock: ClockDep) -> CostCenterService:
    return CostCenterService(session, clock)


def get_project_service(session: SessionDep, clock: ClockDep) -> ProjectService:
    return ProjectService(session, clock)


def get_period_service(session: SessionDep, clock: ClockDep) -> PeriodService:
    return PeriodService(session, clock)


def get_posting_account_service(session: SessionDep, clock: ClockDep) -> PostingAccountService:
    return PostingAccountService(session, clock)


def get_tax_rule_service(session: SessionDep, clock: ClockDep) -> TaxRuleService:
    return TaxRuleService(session, clock)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
CategoryServiceDep = Annotated[CategoryService, Depends(get_category_service)]
CostCenterServiceDep = Annotated[CostCenterService, Depends(get_cost_center_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
PeriodServiceDep = Annotated[PeriodService, Depends(get_period_service)]
PostingAccountServiceDep = Annotated[PostingAccountService, Depends(get_posting_account_service)]
TaxRuleServiceDep = Annotated[TaxRuleService, Depends(get_tax_rule_service)]


@lru_cache
def get_storage() -> Storage:
    return make_storage(get_settings())


StorageDep = Annotated[Storage, Depends(get_storage)]


def get_expense_service(session: SessionDep, clock: ClockDep, settings: SettingsDep) -> ExpenseService:
    return ExpenseService(session, clock, settings)


def get_purchase_service(session: SessionDep, clock: ClockDep, settings: SettingsDep) -> PurchaseService:
    return PurchaseService(session, clock, settings)


def get_attachment_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep, storage: StorageDep, limiter: LimiterDep
) -> AttachmentService:
    return AttachmentService(session, clock, settings, storage, limiter)


ExpenseServiceDep = Annotated[ExpenseService, Depends(get_expense_service)]
PurchaseServiceDep = Annotated[PurchaseService, Depends(get_purchase_service)]
AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
VendorServiceDep = Annotated[VendorService, Depends(get_vendor_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
InviteServiceDep = Annotated[InviteService, Depends(get_invite_service)]
