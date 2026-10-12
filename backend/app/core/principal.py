from dataclasses import dataclass

from app.core.enums import Role


@dataclass(frozen=True)
class Principal:
    """Who is acting. Built from the database row on every request, so a role change applies at once."""

    id: int
    email: str
    full_name: str
    role: Role
