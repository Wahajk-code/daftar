from fastapi import APIRouter

from app.deps import SettingsDep
from app.schemas.base import ResponseModel

router = APIRouter(prefix="/me", tags=["me"])


class MeRead(ResponseModel):
    display_timezone: str


@router.get("", operation_id="get_me")
def get_me(settings: SettingsDep) -> MeRead:
    """The zone both clients format instants in. Pass 2 adds the signed-in user to this response."""
    return MeRead(display_timezone=settings.display_timezone)
