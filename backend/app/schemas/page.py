from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


class Page[T](BaseModel):
    """Every list answers in this shape: the items on this page and the total across all pages."""

    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: int
    offset: int
    sort: str | None


def page_params(
    limit: Annotated[
        int, Query(ge=1, description="Page size; values above 100 are treated as 100.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str | None, Query(description="A field name; prefix with - for descending.", max_length=40)] = None,
) -> PageParams:
    return PageParams(limit=min(limit, MAX_PAGE_SIZE), offset=offset, sort=sort)


PageParamsDep = Annotated[PageParams, Depends(page_params)]
