from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.core.enums import Role
from app.core.normalize import canonical_email
from app.schemas.base import RequestModel, ResponseModel

# Passwords keep their spaces: the request base trims strings, which would silently change a password.
Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)]
TokenText = Annotated[str, Field(min_length=10, max_length=200)]
# Looked up and rate-limited in exactly the canonical form; whether it is a plausible address is not judged here.
LookupEmail = Annotated[str, Field(max_length=254), AfterValidator(canonical_email)]


class LoginRequest(RequestModel):
    email: LookupEmail
    password: Password


class RefreshRequest(RequestModel):
    refresh_token: TokenText


class ForgotPasswordRequest(RequestModel):
    email: LookupEmail


class ResetPasswordRequest(RequestModel):
    token: TokenText
    new_password: Password


class ChangePasswordRequest(RequestModel):
    current_password: Password
    new_password: Password


class UserBrief(ResponseModel):
    id: int
    email: str
    full_name: str
    role: Role


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - the scheme name, not a secret
    expires_in: int
    user: UserBrief


class Accepted(BaseModel):
    """The reply to a request that is acted on in the background and must not reveal whether it matched anything."""

    status: str = "accepted"
