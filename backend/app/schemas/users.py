from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.clock import require_utc
from app.core.enums import Role
from app.core.normalize import Email
from app.models.auth import AuthToken
from app.schemas.auth import Password
from app.schemas.base import RequestModel, ResponseModel, UtcInstant


class UserRead(ResponseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    tour_completed_at: UtcInstant | None
    created_at: UtcInstant


class RoleChange(RequestModel):
    role: Role


class InviteCreate(RequestModel):
    email: Email
    role: Role


class InviteRead(ResponseModel):
    id: int
    email: str
    role: Role
    status: Literal["pending", "expired", "accepted", "revoked"]
    created_at: UtcInstant
    expires_at: UtcInstant
    used_at: UtcInstant | None
    revoked_at: UtcInstant | None

    @classmethod
    def of(cls, token: AuthToken, now: datetime) -> "InviteRead":
        assert token.email is not None
        assert token.role is not None
        if token.used_at is not None:
            status: Literal["pending", "expired", "accepted", "revoked"] = "accepted"
        elif token.revoked_at is not None:
            status = "revoked"
        elif require_utc(token.expires_at) <= require_utc(now):
            status = "expired"
        else:
            status = "pending"
        return cls(
            id=token.id,
            email=token.email,
            role=token.role,
            status=status,
            created_at=token.created_at,
            expires_at=token.expires_at,
            used_at=token.used_at,
            revoked_at=token.revoked_at,
        )


class InviteInspectRequest(RequestModel):
    token: str = Field(min_length=10, max_length=200)


class InviteInspectRead(ResponseModel):
    email: str
    role: Role
    expires_at: UtcInstant


class InviteAcceptRequest(RequestModel):
    token: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    password: Password
