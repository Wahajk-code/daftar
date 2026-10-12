"""One canonical form for an email. Used by the account lookup, by every schema and by every rate-limit key, so a
different spelling can never buy a fresh counter."""

import unicodedata
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator

MAX_EMAIL_LENGTH = 254


def canonical_email(raw: str) -> str:
    """Compatibility-normalise, trim and lower-case. Does not judge validity."""
    return unicodedata.normalize("NFKC", raw).strip().lower()


def valid_email(raw: str) -> str:
    """The canonical form, or ValueError if it is not a plausible address."""
    candidate = canonical_email(raw)
    if len(candidate) > MAX_EMAIL_LENGTH:
        raise ValueError("email is too long")
    try:
        validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError("enter a valid email address") from exc
    return candidate


def collapse_spaces(raw: str) -> str:
    return " ".join(unicodedata.normalize("NFC", raw).split())


# For schemas: stored and compared in exactly this form.
Email = Annotated[str, AfterValidator(valid_email)]
