from typing import Any, TypedDict


class PageDataType(TypedDict):
    """One page of options as computed by ``PaginatedOptionsBaseSerializer``."""

    count: int
    num_pages: int
    page_number: int
    data: list[Any]


class OptionType[T](TypedDict):
    """A single ``{value, label}`` option."""

    value: T
    label: str
