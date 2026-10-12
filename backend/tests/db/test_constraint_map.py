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
    missing = set(CONSTRAINT_ERRORS) - names
    assert not missing, f"mapped but not in the database: {sorted(missing)}"
