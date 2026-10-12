"""Dependency providers shared by routers."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.clock import Clock
from app.db import get_session

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]


@lru_cache
def get_clock() -> Clock:
    return Clock()


ClockDep = Annotated[Clock, Depends(get_clock)]
