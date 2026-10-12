from fastapi import APIRouter, status

from app.deps import PUBLIC, AuthServiceDep, ClientIpDep, InviteServiceDep, OutboxDep
from app.schemas.auth import (
    Accepted,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserBrief,
)
from app.schemas.users import InviteAcceptRequest, InviteInspectRead, InviteInspectRequest, UserRead
from app.services.auth import SignedIn

router = APIRouter(prefix="/auth", tags=["auth"])


def _pair(signed_in: SignedIn) -> TokenPair:
    return TokenPair(
        access_token=signed_in.access_token,
        refresh_token=signed_in.refresh_token,
        expires_in=signed_in.expires_in,
        user=UserBrief.model_validate(signed_in.user),
    )


@router.post("/login", operation_id="login", **PUBLIC)
def login(body: LoginRequest, service: AuthServiceDep, ip: ClientIpDep) -> TokenPair:
    return _pair(service.login(body.email, body.password, ip))


@router.post("/refresh", operation_id="refresh_session", **PUBLIC)
def refresh_session(body: RefreshRequest, service: AuthServiceDep) -> TokenPair:
    """Exchange a refresh token for a new pair. The old token stops working; presenting it again ends every session."""
    return _pair(service.refresh(body.refresh_token))


@router.post("/logout", operation_id="logout", status_code=status.HTTP_204_NO_CONTENT, **PUBLIC)
def logout(body: RefreshRequest, service: AuthServiceDep) -> None:
    service.logout(body.refresh_token)


@router.post("/forgot-password", operation_id="forgot_password", status_code=status.HTTP_202_ACCEPTED, **PUBLIC)
def forgot_password(
    body: ForgotPasswordRequest, service: AuthServiceDep, ip: ClientIpDep, outbox: OutboxDep
) -> Accepted:
    """Always the same reply, whether or not the email has an account."""
    service.request_reset(body.email, ip)
    outbox.dispatch()
    return Accepted()


@router.post("/reset-password", operation_id="reset_password", status_code=status.HTTP_204_NO_CONTENT, **PUBLIC)
def reset_password(body: ResetPasswordRequest, service: AuthServiceDep, ip: ClientIpDep) -> None:
    service.reset_password(body.token, body.new_password, ip)


@router.post("/invites/inspect", operation_id="inspect_invite", **PUBLIC)
def inspect_invite(body: InviteInspectRequest, service: InviteServiceDep, ip: ClientIpDep) -> InviteInspectRead:
    """What the accept-invitation screen shows. A used, expired or cancelled link says which."""
    token = service.inspect(body.token, ip)
    return InviteInspectRead.model_validate(token)


@router.post("/invites/accept", operation_id="accept_invite", status_code=status.HTTP_201_CREATED, **PUBLIC)
def accept_invite(body: InviteAcceptRequest, service: InviteServiceDep, ip: ClientIpDep) -> UserRead:
    return UserRead.model_validate(service.accept(body.token, body.full_name, body.password, ip))
