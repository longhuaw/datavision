"""
Pagination helper utilities for SQLAlchemy 2.0 async.

Provides:
- paginate()             — apply limit/offset to a SQLAlchemy select statement
- get_page_info()        — build pagination metadata dict
- parse_pagination_params() — validate and coerce raw page/page_size inputs
"""

from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import Select


def paginate(query: Select[Any], page: int, page_size: int) -> Select[Any]:
    """Apply limit/offset to a SQLAlchemy 2.0 select statement.

    Args:
        query: A SQLAlchemy ``Select`` statement (before execution).
        page: 1-based page number (must be >= 1).
        page_size: Number of rows per page.

    Returns:
        The same ``Select`` with ``.limit()`` and ``.offset()`` applied.
    """
    offset = (page - 1) * page_size
    return query.limit(page_size).offset(offset)


def get_page_info(total: int, page: int, page_size: int) -> dict[str, int | bool]:
    """Build a pagination metadata dictionary.

    Args:
        total: Total number of records across all pages.
        page: Current page number (1-based).
        page_size: Number of rows per page.

    Returns:
        A dictionary with keys:
        - total
        - page
        - page_size
        - total_pages
        - has_next
        - has_prev
    """
    total_pages: int = max(1, ceil(total / page_size)) if total > 0 else 1
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def parse_pagination_params(
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, int]:
    """Validate, coerce, and return sanitised pagination parameters.

    Rules:
    - ``page`` is clamped to >= 1.
    - ``page_size`` is clamped to the range [1, 100].

    Args:
        page: Raw page number (may come from user input).
        page_size: Raw page size (may come from user input).

    Returns:
        A ``(page, page_size)`` tuple of validated integers.
    """
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    return page, page_size
