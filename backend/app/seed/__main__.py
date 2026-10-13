"""Run the seed against the configured database: `python -m app.seed`. It never runs in production unless
ALLOW_DEMO_SEED is set, which is how a demonstration site is filled."""

import sys

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.clock import Clock
from app.core.storage import make_storage
from app.db import build_engine
from app.seed.data import DEMO_PASSWORD, USERS
from app.seed.run import describe, seed


def main() -> int:
    settings = get_settings()
    if settings.environment == "production" and not settings.allow_demo_seed:
        sys.stderr.write(
            "Refusing to seed: this is a production environment. "
            "Set ALLOW_DEMO_SEED=true only for a demonstration site.\n"
        )
        return 2
    engine = build_engine(settings.database_url, settings)
    if not inspect(engine).has_table("users"):
        sys.stderr.write("The database has no tables yet. Run the migrations first.\n")
        return 1
    with Session(engine) as session:
        summary = seed(session, settings, make_storage(settings), Clock().now())
    if summary.already_seeded:
        sys.stdout.write("The demonstration data is already there; nothing was changed.\n")
    else:
        sys.stdout.write("Demonstration data created:\n")
    sys.stdout.write("\n".join(describe(summary)) + "\n")
    if not summary.already_seeded:
        sys.stdout.write(f"\nSign in with any of these, password {DEMO_PASSWORD}:\n")
        for email, name, role in USERS:
            sys.stdout.write(f"  {email:<22} {role:<11} {name}\n")
        if settings.storage_backend == "memory":
            sys.stdout.write(
                "\nReceipts are kept in memory in this configuration, so they disappear when the API restarts.\n"
                "Set STORAGE_BACKEND=cloudinary to keep them.\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
