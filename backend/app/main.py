import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app import __version__
from app.config import Settings, get_settings
from app.core.clock import Clock
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimiter, build_policies
from app.db import get_session_factory
from app.deps import get_storage
from app.errors import ERROR_RESPONSES, register_error_handlers
from app.middleware import CorrelationIdMiddleware
from app.routers import audit, auth, documents, health, master, me, reports, users, vendors, vouchers
from app.seed.restore import restore_demo_receipts

logger = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # In development the receipt store is in memory and starts empty, so the demonstration receipts are drawn again.
        if settings.environment == "development" and settings.storage_backend == "memory":
            try:
                with get_session_factory()() as session:
                    restored = restore_demo_receipts(session, get_storage(), settings)
                if restored:
                    logger.info("restored %s demonstration receipts into the in-memory store", restored)
            except Exception:
                logger.warning("could not restore the demonstration receipts", exc_info=True)
        yield

    # `debug` is never passed to FastAPI: its debug page would replace the bare 500 with a traceback.
    app = FastAPI(title="Daftar API", version=__version__, lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    # In memory, one process: the counters reset on restart (docs/architecture.md section 9a). Tests replace this.
    app.state.rate_limiter = RateLimiter(
        Clock(), build_policies(settings.rate_limit_overrides), max_keys=settings.rate_limit_max_keys
    )
    register_error_handlers(app)

    app.include_router(health.router)
    api = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
    api.include_router(auth.router)
    api.include_router(me.router)
    api.include_router(users.users)
    api.include_router(users.invites)
    api.include_router(vendors.router)
    api.include_router(reports.router)
    api.include_router(audit.router)
    for router in (documents.expenses, documents.purchases, documents.attachments, vouchers.router):
        api.include_router(router)
    for router in (
        master.accounts,
        master.categories,
        master.cost_centers,
        master.projects,
        master.periods,
        master.posting_accounts,
        master.tax_rules,
        master.accounting_settings,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = create_app()
