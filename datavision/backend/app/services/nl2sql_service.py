"""
NL2SQL Service — Natural Language to SQL engine.

This is the core differentiator of DataVision. It takes a user's natural
language prompt, enriches it with dataset schema context, builds a carefully
engineered LLM prompt, calls the LLM, validates the generated SQL, and returns
a structured result with chart recommendation.

Fallback: when no LLM API key is configured, the service operates in *mock mode*,
returning template SQL so the frontend and API surface can still be exercised.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chart import NLQueryHistory, Chart
from app.models.dataset import Dataset, DatasetColumn
from app.core.sql_validator import SQLValidator

logger = logging.getLogger("datavision.nl2sql")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of sample rows to include in the schema context sent to the LLM.
# Keeping this small avoids blowing the token budget while still giving the model
# enough signal about data shape and distribution.
_MAX_SAMPLE_ROWS = 3

# The chart types we allow the model to recommend.  Kept as a typed set so the
# prompt can enumerate them for the LLM, and so we can validate the response.
_VALID_CHART_TYPES: frozenset[str] = frozenset({
    "line", "bar", "pie", "scatter", "heatmap", "funnel",
    "radar", "sankey", "map", "table", "gauge", "treemap",
    "wordcloud", "area", "combo", "number",
})

# Default fallback chart type when the LLM picks something unrecognized.
_DEFAULT_CHART_TYPE = "table"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_sql(
    prompt: str,
    dataset_id: str,
    db: AsyncSession,
) -> dict:
    """Generate SQL from a natural language prompt.

    This is the primary entry point.  It:

    1. Loads dataset metadata + column definitions from the database.
    2. Optionally fetches a few sample rows from the source (best-effort).
    3. Builds a richly-formatted schema context.
    4. Constructs a detailed LLM prompt with guardrails.
    5. Calls the LLM (or mock) and parses the JSON response.
    6. Validates the generated SQL for security.
    7. Returns a dict with ``sql``, ``chart_type``, ``confidence``, and
       ``explanation``.

    Parameters
    ----------
    prompt : str
        The user's NL question (e.g. "show me monthly revenue by region").
    dataset_id : str
        The dataset this query should target.
    db : AsyncSession
        Active database session.

    Returns
    -------
    dict
        Keys: ``sql``, ``chart_type``, ``confidence`` (0-100), ``explanation``,
        ``is_valid``, ``validation_message``.
    """
    start_time = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Load dataset
    # ------------------------------------------------------------------
    dataset = await _get_dataset(db, dataset_id)
    if not dataset:
        raise ValueError(f"Dataset not found: {dataset_id}")

    # ------------------------------------------------------------------
    # 2. Load columns
    # ------------------------------------------------------------------
    columns = await _get_dataset_columns(db, dataset_id)
    if not columns:
        raise ValueError(f"Dataset '{dataset.name}' has no columns defined.")

    # ------------------------------------------------------------------
    # 3. Sample data (best-effort — may be empty)
    # ------------------------------------------------------------------
    sample_data = await _fetch_sample_data(db, dataset, columns, _MAX_SAMPLE_ROWS)

    # ------------------------------------------------------------------
    # 4. Build schema context
    # ------------------------------------------------------------------
    schema_context = build_schema_context(dataset, columns, sample_data)

    # ------------------------------------------------------------------
    # 5. Build LLM prompt
    # ------------------------------------------------------------------
    llm_prompt = _build_llm_prompt(schema_context, prompt)

    # ------------------------------------------------------------------
    # 6. Call LLM
    # ------------------------------------------------------------------
    llm_response = await _call_llm(llm_prompt)
    execution_time_ms = round((time.perf_counter() - start_time) * 1000)

    # ------------------------------------------------------------------
    # 7. Parse JSON response
    # ------------------------------------------------------------------
    parsed = _parse_llm_response(llm_response, execution_time_ms)

    # ------------------------------------------------------------------
    # 8. Validate SQL
    # ------------------------------------------------------------------
    is_valid, validation_message = validate_generated_sql(parsed["sql"])
    parsed["is_valid"] = is_valid
    parsed["validation_message"] = validation_message

    logger.info(
        "NL2SQL generated | dataset=%s | chart=%s | confidence=%s | valid=%s | time=%dms",
        dataset.name,
        parsed["chart_type"],
        parsed["confidence"],
        is_valid,
        execution_time_ms,
    )

    return parsed


def build_schema_context(
    dataset: Dataset,
    columns: list[DatasetColumn],
    sample_data: Optional[list[dict]] = None,
) -> str:
    """Build a markdown-formatted schema context string for the LLM.

    The output includes:

    - Table name
    - Column list with type, role (dimension / metric), and optional notes
    - Sample rows (when available) to help the model understand data shape

    Parameters
    ----------
    dataset : Dataset
        The dataset model instance.
    columns : list[DatasetColumn]
        Columns belonging to this dataset, ordered by ``sort_order``.
    sample_data : list[dict] or None
        A short list of sample rows, each a dict keyed by column name.

    Returns
    -------
    str
        A markdown string suitable for inclusion in an LLM system / user prompt.
    """
    # Determine the primary table name from the dataset config.
    table_name = _resolve_table_name(dataset)

    lines: list[str] = []
    lines.append("## Dataset Schema")
    lines.append("")
    lines.append(f"- **Dataset name**: {dataset.name or '(unnamed)'}")
    lines.append(f"- **Table**: `{table_name}`")
    if dataset.description:
        lines.append(f"- **Description**: {dataset.description}")
    lines.append("")

    # Column table
    lines.append("### Columns")
    lines.append("")
    lines.append("| # | Column | Type | Role | Aggregation | Notes |")
    lines.append("|---|--------|------|------|-------------|-------|")

    for i, col in enumerate(columns, start=1):
        role_parts: list[str] = []
        if col.is_dimension:
            role_parts.append("dimension")
        if col.is_metric:
            role_parts.append("metric")
        role = ", ".join(role_parts) if role_parts else "—"

        agg = col.default_aggregation or "—"
        notes = col.alias or ""
        if col.semantic_type:
            notes += f" [semantic: {col.semantic_type}]"
        if col.is_virtual:
            notes += f" [virtual: {col.virtual_expr}]"

        lines.append(
            f"| {i} | `{col.column_name}` | {col.data_type} | {role} "
            f"| {agg} | {notes.strip()} |"
        )

    lines.append("")

    # Sample data
    if sample_data:
        lines.append("### Sample Data (first few rows)")
        lines.append("")
        # Build a compact markdown table from the sample rows
        col_names = sorted(sample_data[0].keys()) if sample_data else []
        if col_names:
            header = "| " + " | ".join(f"`{c}`" for c in col_names) + " |"
            sep = "|" + "|".join(" --- " for _ in col_names) + "|"
            lines.append(header)
            lines.append(sep)
            for row in sample_data:
                vals = "| " + " | ".join(
                    _fmt_sample_value(row.get(c)) for c in col_names
                ) + " |"
                lines.append(vals)
        lines.append("")

    return "\n".join(lines)


def validate_generated_sql(sql: str) -> tuple[bool, str]:
    """Validate a generated SQL string via the SQLValidator.

    Returns
    -------
    (bool, str)
        Tuple of (is_valid, message).  When valid, ``message`` is an empty string.
    """
    if not sql or not sql.strip():
        return False, "Generated SQL is empty."

    result = SQLValidator.validate(sql)
    if result.is_valid:
        return True, ""
    return False, result.error_message or "SQL validation failed."


async def save_query_history(
    db: AsyncSession,
    user_id: str,
    prompt: str,
    result: dict,
) -> NLQueryHistory:
    """Persist an NL query and its result to the history table.

    Parameters
    ----------
    db : AsyncSession
    user_id : str
    prompt : str
        The raw user prompt.
    result : dict
        The dict returned by ``generate_sql``.

    Returns
    -------
    NLQueryHistory
    """
    history = NLQueryHistory(
        user_id=user_id,
        dataset_id=result.get("dataset_id"),
        prompt=prompt,
        generated_sql=result.get("sql"),
        chart_type=result.get("chart_type"),
        is_valid=result.get("is_valid"),
        error_message=result.get("validation_message"),
        execution_time_ms=result.get("execution_time_ms"),
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)
    logger.debug("NL query history saved id=%s", history.id)
    return history


async def get_query_history(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[NLQueryHistory]]:
    """Retrieve paginated NL query history for a user.

    Parameters
    ----------
    db : AsyncSession
    user_id : str
    page : int
        1-indexed page number.
    page_size : int
        Items per page (clamped 1-100).

    Returns
    -------
    (int, list[NLQueryHistory])
        Total count and list of history records for the current page.
    """
    page_size = max(1, min(100, page_size))
    page = max(1, page)

    base_where = NLQueryHistory.user_id == user_id

    # Count query
    count_q = select(func.count()).select_from(NLQueryHistory).where(base_where)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Page query
    offset = (page - 1) * page_size
    q = (
        select(NLQueryHistory)
        .where(base_where)
        .order_by(NLQueryHistory.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    rows = list(result.scalars().all())

    return total, rows


async def submit_feedback(
    db: AsyncSession,
    history_id: str,
    feedback: str,
) -> bool:
    """Record user feedback on an NL query result.

    Parameters
    ----------
    db : AsyncSession
    history_id : str
        The NLQueryHistory record id.
    feedback : str
        One of ``positive``, ``negative``, ``neutral``.

    Returns
    -------
    bool
        True if the record was found and updated, False otherwise.
    """
    result = await db.execute(
        select(NLQueryHistory).where(NLQueryHistory.id == history_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        logger.warning("Feedback target not found: history_id=%s", history_id)
        return False

    record.feedback = feedback
    await db.commit()
    logger.info("Feedback recorded history_id=%s feedback=%s", history_id, feedback)
    return True


# ============================================================================
# Internal helpers
# ============================================================================


def _resolve_table_name(dataset: Dataset) -> str:
    """Best-effort extraction of the primary table name from a dataset."""
    config = dataset.config or {}
    tables = config.get("tables", [])
    if tables:
        return str(tables[0])
    # Fallback: try to extract from sql_text if it contains FROM
    if dataset.sql_text:
        match = re.search(
            r"\bFROM\s+`?(\w+)`?",
            dataset.sql_text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    # Final fallback: use the dataset name as a virtual table identifier
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", dataset.name or "dataset")
    return safe


def _fmt_sample_value(value: Any) -> str:
    """Format a single sample value for display in a markdown table cell."""
    if value is None:
        return "NULL"
    s = str(value)
    # Truncate very long values
    if len(s) > 60:
        s = s[:57] + "..."
    # Escape pipe characters so they don't break the markdown table
    s = s.replace("|", "\\|")
    return s


async def _get_dataset(db: AsyncSession, dataset_id: str) -> Optional[Dataset]:
    """Load a single dataset (excluding soft-deleted)."""
    result = await db.execute(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def _get_dataset_columns(
    db: AsyncSession, dataset_id: str
) -> list[DatasetColumn]:
    """Load columns for a dataset, ordered by sort_order."""
    result = await db.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.sort_order)
    )
    return list(result.scalars().all())


async def _fetch_sample_data(
    db: AsyncSession,
    dataset: Dataset,
    columns: list[DatasetColumn],
    limit: int = 3,
) -> list[dict]:
    """Fetch a few sample rows from the dataset source (best-effort).

    This is a lightweight wrapper that attempts to query the underlying
    datasource for a handful of rows.  If the datasource is unreachable, or
    the dataset uses an unsupported backend, we return an empty list
    gracefully — the LLM can still reason from column names and types alone.

    .. note::
        For datasets backed by large tables, a ``LIMIT N`` query should be
        near-instantaneous.  In the rare case where even that is slow, the
        executor's timeout will cap the wait.
    """
    # Avoid attempting a sample query when we have nothing to query against
    table_name = _resolve_table_name(dataset)
    if not columns:
        return []

    col_list = ", ".join(f"`{c.column_name}`" for c in columns[:20])

    # Build a simple SELECT ... LIMIT N
    sample_sql = f"SELECT {col_list} FROM `{table_name}` LIMIT {limit}"

    try:
        # We import here to keep the dependency optional at import time
        from app.models.datasource import DataSource
        from app.core.sql_executor import (
            AsyncSQLExecutor,
            create_engine_from_datasource,
        )

        # Resolve the datasource
        ds_result = await db.execute(
            select(DataSource).where(
                DataSource.id == dataset.datasource_id,
                DataSource.is_deleted == False,
                DataSource.status != "disabled",
            )
        )
        datasource = ds_result.scalar_one_or_none()
        if not datasource:
            logger.debug("Cannot fetch sample: datasource not available for dataset=%s", dataset.id)
            return []

        engine = create_engine_from_datasource(datasource.config)
        executor = AsyncSQLExecutor(engine, default_timeout=5.0)
        try:
            query_result = await executor.execute(sample_sql)
            if query_result.success:
                return query_result.rows
        except Exception as exc:
            logger.debug("Sample fetch failed for dataset=%s: %s", dataset.id, exc)
        finally:
            try:
                await executor.close()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("Sample fetch skipped for dataset=%s: %s", dataset.id, exc)

    return []


# ============================================================================
# LLM Prompt Engineering
# ============================================================================


def _build_llm_prompt(schema_context: str, user_prompt: str) -> str:
    """Construct the full LLM prompt with system instructions, schema, and
    the user's natural language question.

    The prompt is carefully engineered to:

    * Constrain the model to **SELECT-only** SQL (defense in depth — the
      validator also enforces this).
    * Instruct the model to use proper quoting, aliases, and standard SQL
      functions.
    * Guide the model toward recommending the most appropriate chart type
      given the query semantics.
    * Require a JSON-only response so parsing is deterministic.
    * Include few-shot examples that demonstrate the expected output shape.
    """
    prompt_parts = [
        _SYSTEM_INSTRUCTION,
        "",
        schema_context,
        "",
        "---",
        "",
        "**User question**:",
        user_prompt,
        "",
        "Respond with **only** the JSON object described above.  "
        "Do not include any other text, markdown fences, or commentary.",
    ]
    return "\n".join(prompt_parts)


_SYSTEM_INSTRUCTION = """You are an expert SQL analyst.  Your task is to translate a
natural language question into a **single, valid SQL SELECT statement**,
and to recommend the best chart type for visualizing the result.

Follow these rules strictly:

### SQL Rules
1. Generate **standard SQL** compatible with MySQL 8.0.
2. **ONLY SELECT** — never INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE.
3. Use the exact column names and table name provided in the schema below.
4. Always quote identifiers with backticks (e.g. `column_name`, `table_name`).
5. Use meaningful aliases for aggregated columns (e.g. `SUM(amount) AS total_amount`).
6. When the user asks for time-based grouping, use `DATE_FORMAT()` for month/week/day.
7. Apply reasonable `LIMIT` when the question implies "top N" or "last N".
8. Use `ORDER BY` when ranking or sorting is implied.
9. For "growth" or "change" questions, consider window functions (`LAG`, `LEAD`)
   or self-joins.
10. Always use `GROUP BY` when an aggregation function is present and non-aggregated
    columns appear in the SELECT list.
11. Include `WHERE` clauses for filters that are explicitly mentioned, but do NOT
    invent filters that the user did not ask for.
12. When the question is vague, prefer a reasonable default aggregation
    (e.g. "sales by region" → SUM of the most likely metric column grouped by region)
    over returning raw rows.

### Chart Recommendation Rules
Choose exactly one chart type from this list:
line, bar, pie, scatter, heatmap, funnel, radar, sankey, map, table, gauge,
treemap, wordcloud, area, combo, number.

Guidelines:
- **line** — time series, trend over time.
- **bar** — comparing categories, ranking.
- **pie** — part-to-whole with few categories (< 8).
- **scatter** — correlation between two numeric columns.
- **heatmap** — matrix / cross-tabulation.
- **table** — detailed listing, no obvious visualization.
- **number** — single aggregate value (total, count, average).
- **area** — stacked time series.
- **combo** — multiple metrics with different scales.
- **map** — geographic data (city, country names present).
- **treemap** — hierarchical part-to-whole.
- **wordcloud** — text / keyword frequency.
- **funnel** — sequential stages (conversion funnel).
- **gauge** — single value against a target / range.
- **radar** — multi-dimensional comparison.
- **sankey** — flow / relationship between categories.

### Response Format
Return a JSON object with exactly these keys:
```json
{
  "sql": "SELECT ...",
  "chart_type": "bar",
  "explanation": "Brief reasoning about the SQL and chart choice (1-3 sentences).",
  "confidence": 85
}
```

- `sql`: the generated SQL statement (string).
- `chart_type`: one of the types listed above (string, lowercase).
- `explanation`: short human-readable rationale (string).
- `confidence`: your internal confidence in this generation, 0-100 (integer).

### Examples

**Example 1**
Schema: table `orders` with columns `id`, `order_date`, `amount`, `region`, `category`
User: "Show total sales by region for 2024"
Response:
```json
{
  "sql": "SELECT `region`, SUM(`amount`) AS total_sales FROM `orders` WHERE YEAR(`order_date`) = 2024 GROUP BY `region` ORDER BY total_sales DESC",
  "chart_type": "bar",
  "explanation": "Comparing sales across regions is best visualized with a bar chart. Filtered to 2024 using YEAR() on the order_date column.",
  "confidence": 93
}
```

**Example 2**
Schema: table `users` with columns `id`, `signup_date`, `status`, `plan`
User: "How many users signed up each month?"
Response:
```json
{
  "sql": "SELECT DATE_FORMAT(`signup_date`, '%Y-%m') AS month, COUNT(*) AS signups FROM `users` GROUP BY DATE_FORMAT(`signup_date`, '%Y-%m') ORDER BY month",
  "chart_type": "line",
  "explanation": "Monthly signups over time is a classic line chart use case, showing trends and seasonality.",
  "confidence": 90
}
```

**Example 3**
Schema: table `products` with columns `id`, `name`, `price`, `category`, `stock`
User: "What is the average price by category?"
Response:
```json
{
  "sql": "SELECT `category`, AVG(`price`) AS avg_price FROM `products` GROUP BY `category` ORDER BY avg_price DESC",
  "chart_type": "bar",
  "explanation": "Comparing average prices across categories — bar chart provides clear comparison.",
  "confidence": 95
}
```
"""


# ============================================================================
# LLM invocation
# ============================================================================


async def _call_llm(prompt: str) -> str:
    """Send the prompt to the configured LLM and return the raw text response.

    When ``LLM_API_KEY`` is unset or set to the default placeholder,
    we fall back to **mock mode** so the service remains usable for demos
    and development.
    """
    if _should_use_mock():
        logger.info("NL2SQL running in MOCK mode (no LLM API key configured).")
        return _mock_llm_response(prompt)

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            openai_api_key=settings.LLM_API_KEY,
            openai_api_base=settings.LLM_BASE_URL,
            temperature=0.1,   # low temperature for deterministic SQL
            max_tokens=2048,
            request_timeout=30.0,
        )

        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return content.strip()

    except Exception as exc:
        logger.exception("LLM call failed: %s", exc)
        raise RuntimeError(f"LLM invocation failed: {exc}") from exc


def _should_use_mock() -> bool:
    """Return True when we should use the mock LLM instead of calling the API."""
    key = (settings.LLM_API_KEY or "").strip()
    if not key:
        return True
    # The default placeholder value from config means "not configured"
    if key == "sk-your-api-key-here":
        return True
    return False


def _mock_llm_response(prompt: str) -> str:
    """Generate a mock JSON response when the LLM is not configured.

    This extracts the table name and columns from the schema context and
    builds a reasonable template SELECT so the frontend and API surface
    stay testable.
    """
    # Try to extract the table name from the prompt
    table_match = re.search(r"\*\*Table\*\*:\s*`(\w+)`", prompt)
    table = table_match.group(1) if table_match else "dataset"

    # Try to extract column names from the markdown table
    columns = re.findall(r"\|\s*\d+\s*\|\s*`(\w+)`", prompt)
    col_names = columns[:4] if columns else ["id", "name", "value"]

    # Build a reasonable mock SQL
    if len(col_names) >= 2:
        mock_sql = (
            f"SELECT `{col_names[0]}`, COUNT(*) AS cnt "
            f"FROM `{table}` "
            f"GROUP BY `{col_names[0]}` "
            f"LIMIT 50"
        )
    else:
        mock_sql = (
            f"SELECT * FROM `{table}` LIMIT 50"
        )

    mock = {
        "sql": mock_sql,
        "chart_type": "bar",
        "explanation": (
            "[MOCK MODE] This is a template SQL generated without an LLM.  "
            "Configure a valid LLM_API_KEY in .env to enable AI-powered NL2SQL."
        ),
        "confidence": 0,
    }
    return json.dumps(mock, ensure_ascii=False)


# ============================================================================
# Response parsing
# ============================================================================


def _parse_llm_response(raw: str, execution_time_ms: int = 0) -> dict:
    """Parse the LLM's JSON response into a structured dict.

    Handles common LLM output issues:

    - Markdown code fences (`` ```json ... ``` ``).
    - Leading/trailing text before or after the JSON object.
    - Missing or extra keys (fills safe defaults).

    Returns
    -------
    dict
        With keys ``sql``, ``chart_type``, ``confidence``, ``explanation``,
        ``execution_time_ms``.
    """
    # Strip markdown code fences
    json_str = raw.strip()

    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", json_str, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1).strip()

    # If the response has text before/after the JSON object, try to extract
    # just the JSON by finding the outermost { ... }
    if not json_str.startswith("{"):
        brace_start = json_str.find("{")
        if brace_start != -1:
            brace_end = json_str.rfind("}")
            if brace_end > brace_start:
                json_str = json_str[brace_start:brace_end + 1]

    # Parse
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response. Raw: %.300s", raw)
        return _error_result(
            "Failed to parse LLM response as JSON.",
            raw,
            execution_time_ms,
        )

    sql = (parsed.get("sql") or "").strip()

    chart_type = (parsed.get("chart_type") or _DEFAULT_CHART_TYPE).lower().strip()
    if chart_type not in _VALID_CHART_TYPES:
        logger.debug(
            "LLM returned unrecognized chart_type=%r, falling back to %r",
            chart_type,
            _DEFAULT_CHART_TYPE,
        )
        chart_type = _DEFAULT_CHART_TYPE

    confidence = parsed.get("confidence", 50)
    try:
        confidence = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        confidence = 50

    explanation = str(parsed.get("explanation", "")).strip()

    return {
        "sql": sql,
        "chart_type": chart_type,
        "confidence": confidence,
        "explanation": explanation,
        "execution_time_ms": execution_time_ms,
    }


def _error_result(message: str, raw: str, execution_time_ms: int) -> dict:
    """Return a safe fallback dict when parsing fails."""
    return {
        "sql": "",
        "chart_type": _DEFAULT_CHART_TYPE,
        "confidence": 0,
        "explanation": message,
        "raw_response": raw[:500],
        "execution_time_ms": execution_time_ms,
    }
