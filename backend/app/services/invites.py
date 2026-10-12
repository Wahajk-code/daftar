"""Invitations: an Admin invites by email with one role; the invitee chooses their own name and password."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import mail_templates
from app.core.clock import Clock
from app.core.enums import AuthPurpose, Role
from app.core.errors import (
    ConflictError,
    ErrorCode,
    FieldError,
    GuardFailedError,
    NotFoundError,
    ValidationFailedError,
)
from app.core.mail import Outbox
from app.core.normalize import collapse_spaces
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.security import Passwords, hash_token, password_problem
from app.models.auth import AuthToken
from app.models.user import User
from app.repositories import tokens as token_repository
from app.repositories import users as user_repository
from app.services import tokens as token_service
from app.services.audit import AuditService


class InviteService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        passwords: Passwords,
        limiter: RateLimiter,
        outbox: Outbox,
    ) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._passwords = passwords
        self._limiter = limiter
        self._outbox = outbox
        self._audit = AuditService(session, clock)

    # Admin ----------------------------------------------------------------------------------------------------------

    def invite(self, actor: Principal, email: str, role: Role) -> AuthToken:
        now = self._clock.now()
        if user_repository.get_by_email(self._session, email) is not None:
            raise ConflictError(
                "That email already has an account.",
                code=ErrorCode.EMAIL_TAKEN,
                errors=[FieldError("email", "An account with this email already exists.", "email_taken")],
            )
        waiting = token_repository.pending_invite_for_email(self._session, email)
        if waiting is not None:
            if waiting.expires_at > now:
                raise ConflictError(
                    "An invitation is already waiting for that email. Resend it instead.",
                    code=ErrorCode.INVITE_PENDING,
                    errors=[FieldError("email", "An invitation is already waiting.", "invite_pending")],
                )
            token_repository.revoke_auth_token(self._session, waiting.id, now)
        row = self._send(email, role, actor, now)
        self._audit.record(
            actor_id=actor.id,
            action="invite.created",
            entity_type="invite",
            entity_id=row.id,
            after={"email": email, "role": role.value},
        )
        self._session.commit()
        return row

    def resend(self, actor: Principal, invite_id: int) -> AuthToken:
        old = self._get_unaccepted(invite_id)
        if old.revoked_at is not None:
            raise ConflictError("That invitation was revoked. Send a new one instead.", code=ErrorCode.CONFLICT)
        assert old.email is not None  # guaranteed by the table's shape check
        assert old.role is not None
        self._limiter.hit(("admin_target", f"invite:{old.email}"))
        now = self._clock.now()
        token_repository.revoke_auth_token(self._session, old.id, now)
        row = self._send(old.email, old.role, actor, now)
        self._audit.record(
            actor_id=actor.id,
            action="invite.resent",
            entity_type="invite",
            entity_id=row.id,
            before={"replaced_invite": old.id},
            after={"email": old.email},
        )
        self._session.commit()
        return row

    def revoke(self, actor: Principal, invite_id: int) -> AuthToken:
        row = self._get_unaccepted(invite_id)
        if row.revoked_at is None:
            token_repository.revoke_auth_token(self._session, row.id, self._clock.now())
            self._session.refresh(row)
            self._audit.record(
                actor_id=actor.id,
                action="invite.revoked",
                entity_type="invite",
                entity_id=row.id,
                before={"email": row.email},
            )
            self._session.commit()
        return row

    def list_invites(self, *, sort: str | None, limit: int, offset: int) -> tuple[list[AuthToken], int]:
        return token_repository.list_invites(self._session, sort=sort, limit=limit, offset=offset)

    # The invitee ----------------------------------------------------------------------------------------------------

    def inspect(self, token: str, ip: str) -> AuthToken:
        """What the accept screen shows before the person types anything. A bad link says why, in words."""
        self._limiter.hit(("token_confirm_ip", ip))
        return token_service.usable_or_error(
            token_repository.get_auth_token_by_hash(self._session, hash_token(token)),
            AuthPurpose.INVITE,
            self._clock.now(),
        )

    def accept(self, token: str, full_name: str, password: str, ip: str) -> User:
        self._limiter.hit(("token_confirm_ip", ip))
        now = self._clock.now()
        row = token_service.usable_or_error(
            token_repository.get_auth_token_by_hash(self._session, hash_token(token)), AuthPurpose.INVITE, now
        )
        assert row.email is not None
        assert row.role is not None
        name = collapse_spaces(full_name)
        if not name:
            raise ValidationFailedError(
                "Enter your name.", errors=[FieldError("full_name", "Enter your name.", "required")]
            )
        problem = password_problem(password, row.email)
        if problem:
            raise ValidationFailedError(
                "Choose a different password.", errors=[FieldError("password", problem, "weak_password")]
            )
        if user_repository.get_by_email(self._session, row.email) is not None:
            raise ConflictError("That email already has an account.", code=ErrorCode.EMAIL_TAKEN)
        # Claimed last, and atomically: of two people using the same link at once, one wins.
        if not token_repository.claim_auth_token(self._session, row.id, now):
            raise GuardFailedError("This link has already been used.", code=ErrorCode.TOKEN_INVALID)
        user = user_repository.add(
            self._session,
            User(
                email=row.email,
                full_name=name,
                password_hash=self._passwords.hash(password),
                role=row.role,
                created_at=now,
                updated_at=now,
            ),
        )
        self._audit.record(
            actor_id=user.id,
            action="user.created_from_invite",
            entity_type="user",
            entity_id=user.id,
            after={"role": row.role.value, "invite": row.id},
        )
        self._session.commit()
        return user

    # -----------------------------------------------------------------------------------------------------------------

    def _get_unaccepted(self, invite_id: int) -> AuthToken:
        row = token_repository.get_auth_token(self._session, invite_id, AuthPurpose.INVITE)
        if row is None:
            raise NotFoundError("There is no such invitation.")
        if row.used_at is not None:
            raise ConflictError("That invitation was already accepted.", code=ErrorCode.CONFLICT)
        return row

    def _send(self, email: str, role: Role, actor: Principal, now: datetime) -> AuthToken:
        row, plain = token_service.issue_invite(
            self._session, self._settings, email=email, role=role, created_by=actor.id, now=now
        )
        self._outbox.add(
            mail_templates.invite(
                to=email,
                role=role.value,
                link=token_service.link(self._settings, "accept-invite", plain),
                expires=token_service.expiry_text(self._settings, row.expires_at),
                invited_by=actor.full_name,
            )
        )
        return row
