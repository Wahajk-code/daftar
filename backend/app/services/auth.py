"""Sign in, token refresh, sign out and password reset. Throttled before any password is checked."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import NoReturn

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import mail_templates
from app.core.clock import Clock
from app.core.enums import AuthPurpose
from app.core.errors import (
    ErrorCode,
    FieldError,
    GuardFailedError,
    UnauthenticatedError,
    ValidationFailedError,
)
from app.core.mail import Outbox
from app.core.normalize import canonical_email
from app.core.principal import Principal
from app.core.rate_limit import RateLimiter
from app.core.security import (
    Passwords,
    create_access_token,
    hash_token,
    new_secret_token,
    password_problem,
)
from app.models.auth import RefreshToken
from app.models.user import User
from app.repositories import tokens as token_repository
from app.repositories import users as user_repository
from app.services import tokens as token_service
from app.services.audit import AuditService
from app.services.master import reauthenticate

logger = logging.getLogger("app.auth")

BAD_CREDENTIALS = "The email or password is incorrect."


@dataclass(frozen=True)
class SignedIn:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


class AuthService:
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

    # Sign in ---------------------------------------------------------------------------------------------------------

    def login(self, email: str, password: str, ip: str) -> SignedIn:
        email = canonical_email(email)
        # Counted before the password is looked at, so a burst of parallel guesses cannot all slip through.
        ticket = self._limiter.hit(("login_strict", f"{email}|{ip}"), ("login_loose", email), ("login_ip", ip))
        user = user_repository.get_by_email(self._session, email)
        usable = user if user is not None and user.is_active else None
        # An unknown or inactive account is checked against a dummy hash: same work, same time, same answer.
        valid = self._passwords.verify(usable.password_hash if usable else None, password)
        if usable is None or not valid:
            self._audit.record(
                actor_id=None,
                action="auth.login_failed",
                entity_type="user",
                entity_id=user.id if user else None,
            )
            self._session.commit()
            raise UnauthenticatedError(BAD_CREDENTIALS, code=ErrorCode.INVALID_CREDENTIALS)
        self._limiter.refund(ticket)

        now = self._clock.now()
        if self._passwords.needs_rehash(usable.password_hash):
            usable.password_hash = self._passwords.hash(password)
        signed_in = self._start_session(usable)
        self._audit.record(actor_id=usable.id, action="auth.login", entity_type="user", entity_id=usable.id)
        usable.updated_at = now
        self._session.commit()
        return signed_in

    def _start_session(self, user: User) -> SignedIn:
        now = self._clock.now()
        refresh = new_secret_token()
        token_repository.add_refresh(
            self._session,
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh),
                created_at=now,
                expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            ),
        )
        access = create_access_token(
            user.id,
            secret_key=self._settings.secret_key.get_secret_value(),
            now=now,
            ttl_seconds=self._settings.access_token_ttl_seconds,
        )
        return SignedIn(access, refresh, self._settings.access_token_ttl_seconds, user)

    # Refresh and sign out --------------------------------------------------------------------------------------------

    def refresh(self, refresh_token: str) -> SignedIn:
        """Rotate: the old token is consumed and a new one issued. Presenting a consumed or revoked token is reuse, and
        revokes every refresh token the user has."""
        now = self._clock.now()
        row = token_repository.get_refresh_by_hash(self._session, hash_token(refresh_token))
        if row is None:
            raise UnauthenticatedError("Sign in again.")
        if row.consumed_at is not None or row.revoked_at is not None:
            self._revoke_for_reuse(row.user_id)
        if row.expires_at <= now:
            raise UnauthenticatedError("Your session has expired. Sign in again.")
        # Of two parallel requests with this token, exactly one claims it; the other is treated as reuse.
        if not token_repository.claim_refresh(self._session, row.id, now):
            self._revoke_for_reuse(row.user_id)
        user = user_repository.get(self._session, row.user_id)
        if user is None or not user.is_active:
            token_repository.revoke_all_refresh(self._session, row.user_id, now)
            self._session.commit()
            raise UnauthenticatedError("Sign in again.")
        signed_in = self._start_session(user)
        self._session.commit()
        return signed_in

    def _revoke_for_reuse(self, user_id: int) -> NoReturn:
        now = self._clock.now()
        revoked = token_repository.revoke_all_refresh(self._session, user_id, now)
        self._audit.record(
            actor_id=None,
            action="auth.refresh_reuse_detected",
            entity_type="user",
            entity_id=user_id,
            after={"revoked_tokens": revoked},
        )
        self._session.commit()
        logger.warning("refresh token reuse", extra={"user_id": user_id, "revoked": revoked})
        raise UnauthenticatedError("Sign in again.")

    def logout(self, refresh_token: str) -> None:
        row = token_repository.get_refresh_by_hash(self._session, hash_token(refresh_token))
        if row is None or row.revoked_at is not None:
            return
        token_repository.revoke_refresh(self._session, row.id, self._clock.now())
        self._audit.record(actor_id=row.user_id, action="auth.logout", entity_type="user", entity_id=row.user_id)
        self._session.commit()

    # Password reset --------------------------------------------------------------------------------------------------

    def request_reset(self, email: str, ip: str) -> None:
        """Self-service reset. The reply never depends on whether the email has an account; an unknown email does the
        same limiter work and token generation, and simply sends nothing."""
        email = canonical_email(email)
        self._limiter.hit(("forgot_email", email), ("forgot_ip", ip))
        user = user_repository.get_by_email(self._session, email)
        now = self._clock.now()
        if user is None or not user.is_active:
            new_secret_token()  # keep the work comparable
            return
        row, plain = token_service.issue_reset(self._session, self._settings, user_id=user.id, now=now)
        self._audit.record(actor_id=user.id, action="auth.reset_requested", entity_type="user", entity_id=user.id)
        self._outbox.add(
            mail_templates.password_reset(
                to=user.email,
                link=token_service.link(self._settings, "reset-password", plain),
                expires=token_service.expiry_text(self._settings, row.expires_at),
                started_by_admin=False,
            )
        )
        self._session.commit()

    def reset_password(self, token: str, new_password: str, ip: str) -> None:
        self._limiter.hit(("token_confirm_ip", ip))
        now = self._clock.now()
        row = token_service.usable_or_error(
            token_repository.get_auth_token_by_hash(self._session, hash_token(token)), AuthPurpose.PASSWORD_RESET, now
        )
        user = user_repository.get(self._session, row.user_id or 0)
        if user is None or not user.is_active:
            raise GuardFailedError("This link is not valid. Ask for a new one.", code=ErrorCode.TOKEN_INVALID)
        self._require_acceptable(new_password, user.email)
        # Claimed only after the new password is accepted, so a weak first try does not burn the link.
        if not token_repository.claim_auth_token(self._session, row.id, now):
            raise GuardFailedError("This link has already been used.", code=ErrorCode.TOKEN_INVALID)
        user.password_hash = self._passwords.hash(new_password)
        user.updated_at = now
        token_repository.revoke_all_refresh(self._session, user.id, now)
        self._audit.record(actor_id=user.id, action="auth.password_reset", entity_type="user", entity_id=user.id)
        self._session.commit()

    # Signed in -------------------------------------------------------------------------------------------------------

    def reauthenticate(self, principal: Principal, password: str) -> None:
        """Ask for the password again before a sensitive change. Throttled per user, counted before the check."""
        reauthenticate(self._session, self._passwords, self._limiter, principal, password)

    def change_password(self, principal: Principal, current_password: str, new_password: str) -> None:
        self.reauthenticate(principal, current_password)
        self._require_acceptable(new_password, principal.email)
        user = user_repository.get(self._session, principal.id)
        if user is None:
            raise UnauthenticatedError("Sign in to continue.")
        now = self._clock.now()
        user.password_hash = self._passwords.hash(new_password)
        user.updated_at = now
        token_repository.revoke_all_refresh(self._session, user.id, now)
        self._audit.record(actor_id=user.id, action="auth.password_changed", entity_type="user", entity_id=user.id)
        self._session.commit()

    @staticmethod
    def _require_acceptable(password: str, email: str) -> None:
        problem = password_problem(password, email)
        if problem:
            raise ValidationFailedError(
                "Choose a different password.", errors=[FieldError("new_password", problem, "weak_password")]
            )
