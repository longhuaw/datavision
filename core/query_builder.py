"""
Dynamic SQL SELECT query builder for chart configuration.

Builds parameterized SQL queries from structured chart config:
- table_name, dimensions, metrics, filters, order_by, limit

Supports MySQL-style backtick identifier quoting.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Operators that do not need a value
# ---------------------------------------------------------------------------
NULL_OPERATORS = frozenset({"IS NULL", "IS NOT NULL"})

# Valid aggregation functions
VALID_AGGREGATIONS = frozenset({"SUM", "COUNT", "AVG", "MAX", "MIN"})

# Value-type operators — the value is used directly as a single parameter.
VALUE_OPERATORS = frozenset({"=", "!=", ">", "<", ">=", "<=", "LIKE"})

# Multi-value operators
MULTI_VALUE_OPERATORS = frozenset({"IN", "BETWEEN"})

ALL_OPERATORS = VALUE_OPERATORS | MULTI_VALUE_OPERATORS | NULL_OPERATORS


class QueryBuilderError(ValueError):
    """Raised when the provided chart configuration is invalid."""


class QueryBuilder:
    """Builds parameterized SQL SELECT statements from a chart configuration.

    Typical usage::

        sql, params = QueryBuilder.build(
            table_name="orders",
            dimensions=[{"column": "region", "alias": "Region"}],
            metrics=[
                {"function": "SUM", "column": "amount", "alias": "total_amount"},
                {"function": "COUNT", "column": "*", "alias": "order_count"},
            ],
            filters=[
                {"column": "status", "operator": "=", "value": "paid"},
                {"column": "created_at", "operator": "BETWEEN", "value": ["2024-01-01", "2024-12-31"]},
                {"column": "deleted_at", "operator": "IS NULL"},
            ],
            order_by=[{"column": "total_amount", "direction": "DESC"}],
            limit=100,
        )

    Parameters are returned as a flat list suitable for use with
    ``cursor.execute(sql, params)``.
    """

    # ------------------------------------------------------------------
    # Public API (all static)
    # ------------------------------------------------------------------

    @staticmethod
    def build(
        table_name: str,
        dimensions: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[List[Dict[str, Any]]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        order_by: Optional[List[Dict[str, Any]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Tuple[str, List[Any]]:
        """Build a complete parameterized SELECT query.

        Returns
        -------
        (sql, params)
            ``sql`` is the final SQL string with ``%s`` placeholders.
            ``params`` is the flat list of parameter values.
        """
        dimensions = dimensions or []
        metrics = metrics or []
        filters = filters or []
        order_by = order_by or []

        if not table_name:
            raise QueryBuilderError("table_name is required")

        params: List[Any] = []

        select_clause, _ = QueryBuilder._build_select(dimensions, metrics)
        from_clause = QueryBuilder._build_from(table_name)
        where_clause, where_params = QueryBuilder._build_where(filters)
        group_by_clause = QueryBuilder._build_group_by(dimensions)
        order_clause = QueryBuilder._build_order_by(order_by)
        limit_clause = QueryBuilder._build_limit_offset(limit, offset)

        params.extend(where_params)

        sql = QueryBuilder._assemble(
            select=select_clause,
            from_=from_clause,
            where=where_clause,
            group_by=group_by_clause,
            order_by=order_clause,
            limit=limit_clause,
        )

        return sql, params

    # ------------------------------------------------------------------
    # Clause builders (all static)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_select(
        dimensions: List[Dict[str, Any]],
        metrics: List[Dict[str, Any]],
    ) -> Tuple[str, List[str]]:
        """Build the SELECT clause and return a list of select items for GROUP BY."""
        columns: List[str] = []       # fully formed column expressions
        select_items: List[str] = []  # bare names for downstream use

        for dim in dimensions:
            col = QueryBuilder._require_column(dim, "dimension")
            alias = dim.get("alias")
            expr = QueryBuilder._format_identifier(col)
            if alias:
                expr += f" AS {QueryBuilder._format_identifier(alias)}"
            columns.append(expr)
            select_items.append(alias or col)

        for metric in metrics:
            func = (metric.get("function") or "").upper()
            if func not in VALID_AGGREGATIONS:
                raise QueryBuilderError(
                    f"Invalid metric function: {func!r}. Must be one of {sorted(VALID_AGGREGATIONS)}"
                )
            col = metric.get("column", "*")
            alias = metric.get("alias")
            if col == "*":
                expr = f"{func}(*)"
            else:
                expr = f"{func}({QueryBuilder._format_identifier(col)})"
            if alias:
                expr += f" AS {QueryBuilder._format_identifier(alias)}"
            columns.append(expr)
            select_items.append(alias or col)

        if not columns:
            columns.append("*")

        clause = "SELECT " + ", ".join(columns)
        return clause, select_items

    @staticmethod
    def _build_from(table_name: str) -> str:
        return f"FROM {QueryBuilder._format_identifier(table_name)}"

    @staticmethod
    def _build_where(filters: List[Dict[str, Any]]) -> Tuple[str, List[Any]]:
        """Build WHERE clause with parameterized values."""
        if not filters:
            return "", []

        params: List[Any] = []
        conditions: List[str] = []

        for f in filters:
            condition, cond_params = QueryBuilder._build_filter_condition(f)
            conditions.append(condition)
            params.extend(cond_params)

        where = " AND ".join(conditions)
        return f"WHERE {where}", params

    @staticmethod
    def _build_filter_condition(f: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Build a single filter condition."""
        col = QueryBuilder._require_column(f, "filter")
        operator = (f.get("operator") or "").upper().strip()
        identifier = QueryBuilder._format_identifier(col)

        if operator in NULL_OPERATORS:
            return f"{identifier} {operator}", []

        if operator in VALUE_OPERATORS:
            value = f.get("value")
            if value is None and operator not in ("=", "!="):
                raise QueryBuilderError(
                    f"Operator {operator!r} requires a non-None value for column {col!r}"
                )
            return f"{identifier} {operator} %s", [value]

        if operator == "IN":
            value = f.get("value")
            if not isinstance(value, list) or len(value) == 0:
                raise QueryBuilderError(
                    f"IN operator requires a non-empty list value for column {col!r}"
                )
            placeholders = ", ".join(["%s"] * len(value))
            return f"{identifier} IN ({placeholders})", list(value)

        if operator == "BETWEEN":
            value = f.get("value")
            if not isinstance(value, list) or len(value) != 2:
                raise QueryBuilderError(
                    f"BETWEEN operator requires a list of exactly 2 values for column {col!r}"
                )
            return f"{identifier} BETWEEN %s AND %s", list(value)

        raise QueryBuilderError(
            f"Unsupported operator: {operator!r}. Supported: {sorted(ALL_OPERATORS)}"
        )

    @staticmethod
    def _build_group_by(dimensions: List[Dict[str, Any]]) -> str:
        if not dimensions:
            return ""
        cols = [QueryBuilder._format_identifier(d["column"]) for d in dimensions]
        return "GROUP BY " + ", ".join(cols)

    @staticmethod
    def _build_order_by(order_by: List[Dict[str, Any]]) -> str:
        if not order_by:
            return ""
        items: List[str] = []
        for entry in order_by:
            col = QueryBuilder._require_column(entry, "order_by")
            direction = (entry.get("direction") or "ASC").upper()
            if direction not in ("ASC", "DESC"):
                raise QueryBuilderError(
                    f"Invalid sort direction: {direction!r}. Use ASC or DESC."
                )
            items.append(f"{QueryBuilder._format_identifier(col)} {direction}")
        return "ORDER BY " + ", ".join(items)

    @staticmethod
    def _build_limit_offset(
        limit: Optional[int],
        offset: Optional[int],
    ) -> str:
        clauses: List[str] = []
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise QueryBuilderError(f"limit must be a non-negative integer, got {limit!r}")
            clauses.append(f"LIMIT {int(limit)}")
        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise QueryBuilderError(f"offset must be a non-negative integer, got {offset!r}")
            clauses.append(f"OFFSET {int(offset)}")
        return " ".join(clauses)

    # ------------------------------------------------------------------
    # Helpers (all static)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_identifier(name: str) -> str:
        """Quote an identifier with backticks for MySQL.

        Prevents double-quoting and strips out characters that are not
        safe inside an identifier.
        """
        # Strip existing backticks so we don't double-quote.
        name = name.strip("`").strip()
        if not name:
            raise QueryBuilderError("Identifier must not be empty")
        # Basic safety: reject characters obviously used for injection.
        if re.search(r"[;\x00'\"\\]", name):
            raise QueryBuilderError(f"Unsafe characters in identifier: {name!r}")
        return f"`{name}`"

    @staticmethod
    def _require_column(item: Dict[str, Any], context: str) -> str:
        col = item.get("column")
        if not col or not isinstance(col, str):
            raise QueryBuilderError(
                f"Each {context} entry must have a non-empty 'column' string"
            )
        return col

    @staticmethod
    def _assemble(
        select: str,
        from_: str,
        where: str,
        group_by: str,
        order_by: str,
        limit: str,
    ) -> str:
        parts = [select, from_]
        if where:
            parts.append(where)
        if group_by:
            parts.append(group_by)
        if order_by:
            parts.append(order_by)
        if limit:
            parts.append(limit)
        return "\n".join(parts)
