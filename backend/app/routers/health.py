from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.core.errors import ServiceUnavailableError
from app.deps import SessionDep, SettingsDep
from app.services import health as health_service

router = APIRouter(tags=["health"])


class StatusRead(BaseModel):
    status: str


class VersionRead(BaseModel):
    version: str
    git_sha: str


@router.get("/health", operation_id="get_health")
def get_health() -> StatusRead:
    """Liveness: the process is up. Touches nothing else."""
    return StatusRead(status="ok")


@router.get("/ready", operation_id="get_ready")
def get_ready(session: SessionDep) -> StatusRead:
    """Readiness: the database answers."""
    if not health_service.database_is_reachable(session):
        raise ServiceUnavailableError("The database is not reachable.")
    return StatusRead(status="ok")


@router.get("/version", operation_id="get_version")
def get_version(settings: SettingsDep) -> VersionRead:
    return VersionRead(version=__version__, git_sha=settings.git_sha)
