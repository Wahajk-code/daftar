"""Managing users: roles, deactivation and Admin-triggered resets. Only Admins reach this; the router checks the role
and this service checks again against the locked database rows."""

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import mail_templates
from app.core.clock import Clock
from app.core.enums import Role
from app.core.errors import ErrorCode, ForbiddenError, GuardFailedError, NotFoundError
from app.core.mail import Outbox
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.models.base import JsonDict
from app.models.user import User
from app.repositories import tokens as token_repository
from app.repositories import users as user_repository
from app.services import tokens as token_service
from app.services.audit import AuditService


class UserService:
    def __init__(
        self, session: Session, clock: Clock, settings: Settings, limiter: RateLimiter, outbox: Outbox
    ) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._limiter = limiter
        self._outbox = outbox
        self._audit = AuditService(session, clock)

    def list_users(
        self, *, q: str | None, role: Role | None, is_active: bool | None, sort: str | None, limit: int, offset: int
    ) -> tuple[list[User], int]:
        return user_repository.list_users(
            self._session, q=q, role=role, is_active=is_active, sort=sort, limit=limit, offset=offset
        )

    def get(self, user_id: int) -> User:
        user = user_repository.get(self._session, user_id)
        if user is None:
            raise NotFoundError("There is no such user.")
        return user

    def complete_tour(self, actor: Principal) -> User:
        """Remember on the server that this person has finished or skipped the onboarding tour, so it follows them to
        every device. Doing it twice changes nothing."""
        user = self.get(actor.id)
        if user.tour_completed_at is None:
            now = self._clock.now()
            user.tour_completed_at = now
            user.updated_at = now
            self._audit.record(actor_id=actor.id, action="user.tour_completed", entity_type="user", entity_id=user.id)
            self._session.commit()
        return user

    def restart_tour(self, actor: Principal) -> User:
        """Offer the tour again, for someone who wants to see it once more."""
        user = self.get(actor.id)
        if user.tour_completed_at is not None:
            user.tour_completed_at = None
            user.updated_at = self._clock.now()
            self._audit.record(actor_id=actor.id, action="user.tour_restarted", entity_type="user", entity_id=user.id)
            self._session.commit()
        return user

    def change_role(self, actor: Principal, user_id: int, role: Role) -> User:
        target = self._lock_for_change(actor, user_id, still_admin=role is Role.ADMIN)
        if target.role is role:
            return target
        before = {"role": target.role.value}
        target.role = role
        self._finish(actor, target, "user.role_changed", before, {"role": role.value})
        return target

    def set_active(self, actor: Principal, user_id: int, *, active: bool) -> User:
        target = self._lock_for_change(actor, user_id, still_admin=active)
        if target.is_active is active:
            return target
        target.is_active = active
        self._finish(
            actor,
            target,
            "user.reactivated" if active else "user.deactivated",
            {"is_active": not active},
            {"is_active": active},
        )
        return target

    def trigger_reset(self, actor: Principal, user_id: int) -> None:
        """Send the user the same reset email they could ask for themselves. The Admin never sees or sets a password."""
        user = self.get(user_id)
        if not user.is_active:
            raise GuardFailedError(
                "A deactivated user cannot reset a password. Reactivate the account first.",
                code=ErrorCode.CONFLICT,
            )
        self._limiter.hit(("admin_target", f"user:{user.id}"))
        now = self._clock.now()
        row, plain = token_service.issue_reset(self._session, self._settings, user_id=user.id, now=now)
        self._audit.record(actor_id=actor.id, action="user.reset_triggered", entity_type="user", entity_id=user.id)
        self._outbox.add(
            mail_templates.password_reset(
                to=user.email,
                link=token_service.link(self._settings, "reset-password", plain),
                expires=token_service.expiry_text(self._settings, row.expires_at),
                started_by_admin=True,
            )
        )
        self._session.commit()

    # -----------------------------------------------------------------------------------------------------------------

    def _lock_for_change(self, actor: Principal, user_id: int, *, still_admin: bool) -> User:
        """Check the rules for a role change or deactivation against rows locked in a fixed order, so two Admins
        acting at the same moment are handled one after the other and the second sees the first's result."""
        if actor.id == user_id:
            raise ForbiddenError(
                "You cannot change your own role or deactivate yourself. Ask another Admin.",
                code=ErrorCode.SELF_CHANGE_FORBIDDEN,
            )
        admins = user_repository.lock_active_admins(self._session)
        if actor.id not in {admin.id for admin in admins}:
            raise ForbiddenError("Your own access changed while you were acting. Sign in again.")
        target = user_repository.get(self._session, user_id, for_update=True)
        if target is None:
            raise NotFoundError("There is no such user.")
        is_active_admin = target.role is Role.ADMIN and target.is_active
        if is_active_admin and not still_admin and len(admins) <= 1:
            raise GuardFailedError(
                "This is the last active Admin. Make someone else an Admin first.",
                code=ErrorCode.LAST_ADMIN_PROTECTED,
            )
        return target

    def _finish(self, actor: Principal, target: User, action: str, before: JsonDict, after: JsonDict) -> None:
        now = self._clock.now()
        target.updated_at = now
        # A changed role or a deactivation takes effect on the next request; ending sessions makes it hold.
        token_repository.revoke_all_refresh(self._session, target.id, now)
        if not target.is_active:
            token_repository.revoke_user_resets(self._session, target.id, now)
        self._audit.record(
            actor_id=actor.id, action=action, entity_type="user", entity_id=target.id, before=before, after=after
        )
        self._session.commit()
