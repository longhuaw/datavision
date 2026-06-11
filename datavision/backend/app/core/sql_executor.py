"""
Async SQL Executor — executes user-supplied SELECT queries against arbitrary
datasource backends via SQLAlchemy 2.0's async API.

Features
--------
- Per-datasource async engine creation from a configuration dict
- Parameterised queries (pyformat style — :param_name) to prevent injection
- Configurable query timeout (default 30 s)
- Returns results as list[dict] keyed by column name
- Catches and wraps all exceptions into a structured result type
- Logs query execution time
- Optional streaming of large results in batched pages
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import (
    DBAPIError,
    OperationalError,
    ProgrammingError,
    StatementError,
    TimeoutError as SATimeoutError,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger("datavision.sql_executor")

# ---------------------------------------------------------------------------
# Supported driver lookup — maps DataSource.type to the async driver portion
# of the SQLAlchemy URL scheme.
# ---------------------------------------------------------------------------
_DRIVER_MAP: Dict[str, str] = {
    "mysql": "mysql+asyncmy",
    "postgresql": "postgresql+asyncpg",
    "mssql": "mssql+aioodbc",
    "sqlite": "sqlite+aiosqlite",
    "clickhouse": "clickhouse+asynch",  # requires external dialect
}

# ---------------------------------------------------------------------------
# Per-dialect URL builders — produce the connection string from config fields.
# ---------------------------------------------------------------------------

def _build_mysql_url(config: Dict[str, Any]) -> str:
    host = config.get("host", "localhost")
    port = config.get("port", 3306)
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")
    charset = config.get("charset", "utf8mb4")
    return (
        f"mysql+asyncmy://{username}:{password}@{host}:{port}/{database}"
        f"?charset={charset}"
    )


def _build_postgresql_url(config: Dict[str, Any]) -> str:
    host = config.get("host", "localhost")
    port = config.get("port", 5432)
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")
    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"


def _build_mssql_url(config: Dict[str, Any]) -> str:
    host = config.get("host", "localhost")
    port = config.get("port", 1433)
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")
    return (
        f"mssql+aioodbc://{username}:{password}@{host}:{port}/{database}"
        f"?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )


def _build_sqlite_url(config: Dict[str, Any]) -> str:
    file_path = config.get("file_path", config.get("database", ":memory:"))
    return f"sqlite+aiosqlite:///{file_path}"


def _build_clickhouse_url(config: Dict[str, Any]) -> str:
    host = config.get("host", "localhost")
    port = config.get("port", 9000)
    database = config.get("database", "default")
    username = config.get("username", "default")
    password = config.get("password", "")
    return f"clickhouse+asynch://{username}:{password}@{host}:{port}/{database}"


_URL_BUILDERS: Dict[str, Any] = {
    "mysql": _build_mysql_url,
    "postgresql": _build_postgresql_url,
    "mssql": _build_mssql,
    "sqlite": _build_sqlite,
    "clickhouse": _build_clickhouse_url,
}


# ---------------------------------------------------------------------------
# Result / error types
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Structured result returned by every execute call."""

    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    # Metadata surfaced for the caller
    query: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class QueryExecutionError(Exception):
    """Wraps low-level database / driver errors with a user-safe message."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a plain dict copy (shallow) or empty dict — never None."""
    if params is None:
        return {}
    return dict(params)


def _row_to_dict(row: Any, columns: List[str]) -> Dict[str, Any]:
    """Convert a Row / RowMapping to a plain dict keyed by column name."""
    # SQLAlchemy RowMapping supports both mapping-style and index-style access.
    # Prefer _mapping for compatibility across Row proxies.
    try:
        mapping = row._mapping  # type: ignore[union-attr]
    except AttributeError:
        mapping = row
    return {col: mapping[col] for col in columns}


async def _execute_with_timeout(
    session: AsyncSession,
    compiled_query: Any,
    timeout_s: float,
) -> Any:
    """Execute *compiled_query* inside *session* with a statement-level timeout.

    Uses dialect-specific SET commands for backends that honour per-statement
    timeouts.  Falls back to the driver-level connection timeout otherwise.
    """
    driver = session.bind.dialect.name if session.bind else "mysql"  # type: ignore[union-attr]

    # --- Best-effort per-statement timeout via SET ---
    if driver in ("mysql", "mariadb"):
        # max_execution_time is in milliseconds
        await session.execute(
            text(f"SET SESSION max_execution_time={int(timeout_s * 1000)}")
        )
    elif driver == "postgresql":
        # statement_timeout is in milliseconds
        await session.execute(
            text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}")
        )
    elif driver == "mssql":
        await session.execute(
            text(f"SET LOCK_TIMEOUT {int(timeout_s * 1000)}")
        )
    # SQLite / ClickHouse do not support a per-statement timeout natively

    return await session.execute(compiled_query)


# ---------------------------------------------------------------------------
# Core executor
# ---------------------------------------------------------------------------


class AsyncSQLExecutor:
    """Execute parameterised SELECT statements against an async engine.

    Usage::

        executor = AsyncSQLExecutor(engine)
        result = await executor.execute(
            "SELECT id, name FROM users WHERE status = :status",
            {"status": "active"},
        )
        if result.success:
            for row in result.rows:
                print(row["id"], row["name"])
    """

    def __init__(self, engine: AsyncEngine, *, default_timeout: float = 30.0):
        self._engine = engine
        self._default_timeout = default_timeout
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> QueryResult:
        """Execute a single SELECT and return all rows.

        Parameters
        ----------
        query : str
            SQL SELECT statement (textual, can include :named parameters).
        params : dict | None
            Parameter bindings (pyformat style).
        timeout : float | None
            Per-call timeout in seconds.  Falls back to *default_timeout*.
        """
        params = _sanitize_params(params)
        effective_timeout = timeout if timeout is not None else self._default_timeout
        start = time.perf_counter()

        try:
            async with self._session_factory() as session:
                compiled = text(query)
                result_proxy = await _execute_with_timeout(
                    session, compiled.bindparams(**params), effective_timeout
                )

                columns = list(result_proxy.keys())
                rows = [_row_to_dict(r, columns) for r in result_proxy.fetchall()]

            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "Query executed in %.1f ms | rows=%d | timeout=%.1fs | query=%s...",
                elapsed_ms,
                len(rows),
                effective_timeout,
                query[:200],
            )
            return QueryResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed_ms=elapsed_ms,
                query=query,
                params=params,
            )

        except SATimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            msg = f"Query timed out after {effective_timeout:.1f}s"
            logger.warning("%s | elapsed=%.1fms", msg, elapsed_ms)
            return QueryResult(
                success=False,
                error=msg,
                elapsed_ms=elapsed_ms,
                query=query,
                params=params,
            )
        except (OperationalError, ProgrammingError, StatementError, DBAPIError) as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            msg = f"Database error: {_user_safe_error(exc)}"
            logger.error(
                "Query failed | elapsed=%.1fms | %s | query=%s",
                elapsed_ms,
                msg,
                query[:200],
            )
            return QueryResult(
                success=False,
                error=msg,
                elapsed_ms=elapsed_ms,
                query=query,
                params=params,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            msg = f"Unexpected query error: {exc}"
            logger.exception(
                "Unexpected error | elapsed=%.1fms | query=%s",
                elapsed_ms,
                query[:200],
            )
            return QueryResult(
                success=False,
                error=msg,
                elapsed_ms=elapsed_ms,
                query=query,
                params=params,
            )

    async def execute_raw(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> QueryResult:
        """Alias for ``execute`` — included for naming clarity."""
        return await self.execute(query, params, timeout=timeout)

    async def stream(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        batch_size: int = 1000,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream large result sets in batched pages.

        Yields one ``list[dict]`` per batch.  The caller must fully consume
        (or close) the iterator to release the underlying connection.

        Usage::

            async for batch in executor.stream("SELECT * FROM huge_table", batch_size=500):
                process(batch)
        """
        params = _sanitize_params(params)
        effective_timeout = timeout if timeout is not None else self._default_timeout

        async with self._session_factory() as session:
            compiled = text(query)
            result_proxy = await _execute_with_timeout(
                session, compiled.bindparams(**params), effective_timeout
            )
            columns: List[str] = list(result_proxy.keys())

            batch: List[Dict[str, Any]] = []
            async for row in result_proxy:
                batch.append(_row_to_dict(row, columns))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch

    # ------------------------------------------------------------------
    # Connection health check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Check whether the engine can reach the database."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.warning("Health-check (ping) failed for engine %s", self._engine.url)
            return False

    async def close(self) -> None:
        """Dispose the underlying connection pool."""
        await self._engine.dispose()
        logger.info("Engine disposed: %s", self._engine.url)


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def _build_db_url(ds_type: str, config: Dict[str, Any]) -> str:
    """Construct a database URL from a DataSource type and config dict."""
    ds_type_lower = ds_type.lower().strip()
    builder = _URL_BUILDERS.get(ds_type_lower)
    if builder is None:
        raise ValueError(
            f"Unsupported datasource type '{ds_type}'. "
            f"Supported types: {', '.join(sorted(_URL_BUILDERS))}"
        )
    return builder(config)


def create_engine_from_datasource(
    config: Dict[str, Any],
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 3600,
    echo: bool = False,
) -> AsyncEngine:
    """Build an :class:`AsyncEngine` from a DataSource configuration dict.

    The *config* dict must contain at least ``"type"`` indicating the backend
    (mysql, postgresql, sqlite, mssql, clickhouse).  The remaining keys are
    backend-specific (host, port, database, username, password, etc.).

    Parameters
    ----------
    config : dict
        A dict matching the DataSource model's ``config`` JSON field.
    pool_size : int
        Connection pool size.
    max_overflow : int
        Maximum overflow connections beyond *pool_size*.
    pool_recycle : int
        Recycle connections after this many seconds.
    echo : bool
        If True, SQLAlchemy logs every SQL statement.
    """
    ds_type = config.get("type", "")
    if not ds_type:
        raise ValueError("Datasource config must include a 'type' key.")

    url = _build_db_url(ds_type, config)

    engine = create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        echo=echo,
    )
    logger.info("Engine created for datasource type=%s url=%s", ds_type, _redact_url(url))
    return engine


async def create_executor_from_datasource(
    config: Dict[str, Any],
    *,
    default_timeout: float = 30.0,
    **engine_kwargs: Any,
) -> AsyncSQLExecutor:
    """One-shot helper: engine + executor from a DataSource config dict.

    Returns an :class:`AsyncSQLExecutor` ready for queries.  Call
    ``await executor.close()`` when done.
    """
    engine = create_engine_from_datasource(config, **engine_kwargs)
    return AsyncSQLExecutor(engine, default_timeout=default_timeout)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _user_safe_error(exc: Exception) -> str:
    """Strip connection credentials from driver-level error messages."""
    msg = str(exc).strip()
    # Replace password in URL-like strings
    import re

    msg = re.sub(r"://[^:@]+:[^@]+@", "://***:***@", msg)
    return msg


def _redact_url(url_or_engine: Any) -> str:
    """Return a string representation of a URL with password removed."""
    u = str(url_or_engine)
    import re

    return re.sub(r"://[^:@]+:[^@]+@", "://***:***@", u)
