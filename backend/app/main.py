from fastapi import APIRouter, FastAPI

from app import __version__
from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.errors import ERROR_RESPONSES, register_error_handlers
from app.middleware import CorrelationIdMiddleware
from app.routers import health, me


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # `debug` is never passed to FastAPI: its debug page would replace the bare 500 with a traceback.
    app = FastAPI(title="Daftar API", version=__version__)
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)

    app.include_router(health.router)
    api = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
    api.include_router(me.router)
    app.include_router(api)
    return app


app = create_app()
