from pydantic import BaseModel

from app.core.errors import ErrorCode


class ProblemFieldError(BaseModel):
    field: str
    message: str
    code: str | None = None


class ProblemDetail(BaseModel):
    """RFC 7807 problem details, plus the stable `code` the clients map to wording."""

    type: str
    title: str
    status: int
    detail: str
    code: ErrorCode
    correlation_id: str
    errors: list[ProblemFieldError] = []
