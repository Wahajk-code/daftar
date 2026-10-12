from sqlalchemy import text
from sqlalchemy.orm import Session

from app.errors import CONSTRAINT_ERRORS


def test_every_mapped_constraint_exists_in_the_database(db_session: Session) -> None:
    """The error map keys on names the migrations create; if one is renamed the map must follow."""
    names = {
        row[0]
        for row in db_session.execute(
            text(
                "SELECT conname FROM pg_constraint UNION SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
                " UNION SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
            )
        )
    }
    # A trigger function names the rule it enforces in its RAISE; that name is the one the error map keys on.
    functions = " ".join(str(row[0]) for row in db_session.execute(text("SELECT prosrc FROM pg_proc")))
    raised = {name for name in CONSTRAINT_ERRORS if f"CONSTRAINT = '{name}'" in functions}
    missing = set(CONSTRAINT_ERRORS) - names - raised
    assert not missing, f"mapped but not in the database: {sorted(missing)}"
