from fastapi import APIRouter, status

from app.core.enums import Role
from app.deps import AuthServiceDep, PrincipalDep, SettingsDep, UserServiceDep, roles
from app.schemas.auth import ChangePasswordRequest
from app.schemas.users import UserRead

router = APIRouter(prefix="/me", tags=["me"])


class MeRead(UserRead):
    display_timezone: str


@router.get("", operation_id="get_me", **roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER, Role.STAFF))
def get_me(principal: PrincipalDep, service: UserServiceDep, settings: SettingsDep) -> MeRead:
    """Who is signed in, and the zone both clients format times in."""
    user = UserRead.model_validate(service.get(principal.id))
    return MeRead(**user.model_dump(), display_timezone=settings.display_timezone)


@router.post(
    "/password",
    operation_id="change_my_password",
    status_code=status.HTTP_204_NO_CONTENT,
    **roles(Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER, Role.STAFF),
)
def change_my_password(body: ChangePasswordRequest, principal: PrincipalDep, service: AuthServiceDep) -> None:
    """Change your own password. It signs you out of every device, this one included."""
    service.change_password(principal, body.current_password, body.new_password)
