"""
数据集管理服务 - 创建、更新、删除、列表、预览、SQL执行、字段导入与配置
"""
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.dataset import Dataset, DatasetColumn
from app.models.datasource import DataSource
from app.core.sql_executor import (
    AsyncSQLExecutor,
    create_engine_from_datasource,
    create_executor_from_datasource,
)

logger = logging.getLogger("datavision.dataset_service")

# ---------------------------------------------------------------------------
# Mapping from database data types to canonical types
# ---------------------------------------------------------------------------
_TYPE_MAP = {
    # Integer families
    "tinyint": "int", "smallint": "int", "mediumint": "int", "int": "int",
    "integer": "int", "bigint": "int", "serial": "int", "bigserial": "int",
    "int2": "int", "int4": "int", "int8": "int",
    # Float families
    "float": "float", "real": "float", "double": "float",
    "double precision": "float", "float4": "float", "float8": "float",
    "decimal": "float", "numeric": "float", "number": "float", "money": "float",
    # String families
    "varchar": "string", "char": "string", "text": "string",
    "tinytext": "string", "mediumtext": "string", "longtext": "string",
    "nvarchar": "string", "nchar": "string", "ntext": "string",
    "clob": "string", "character varying": "string", "character": "string",
    "enum": "string", "set": "string",
    # Date / time families
    "date": "date", "datetime": "datetime",
    "timestamp": "datetime", "timestamptz": "datetime",
    "time": "datetime", "timetz": "datetime",
    "year": "int",
    # Boolean
    "bool": "boolean", "boolean": "boolean", "bit": "boolean",
    # JSON / binary
    "json": "string", "jsonb": "string", "blob": "string", "binary": "string",
    "varbinary": "string", "bytea": "string",
}


def _canonical_type(raw_type: Optional[str]) -> str:
    """Convert a database-native type string into our canonical type."""
    if not raw_type:
        return "string"
    # Strip length / precision args, e.g. "decimal(10,2)" → "decimal"
    base = re.sub(r"\(.*\)", "", raw_type.strip()).lower()
    return _TYPE_MAP.get(base, "string")


def _guess_is_dimension(data_type: str, column_name: str) -> bool:
    """Heuristic: columns that are strings, dates, or IDs are dimensions."""
    if data_type in ("string", "date", "datetime", "boolean"):
        return True
    if column_name.lower().endswith("_id") or column_name.lower() == "id":
        return True
    return False


def _guess_is_metric(data_type: str, column_name: str) -> bool:
    """Heuristic: numeric columns that are not IDs are likely metrics."""
    if data_type in ("int", "float"):
        if column_name.lower().endswith("_id") or column_name.lower() == "id":
            return False
        return True
    return False


def _guess_aggregation(data_type: str, column_name: str) -> Optional[str]:
    """Suggest a default aggregation for a metric column."""
    if data_type not in ("int", "float"):
        return None
    if "count" in column_name.lower() or column_name.lower().endswith("_cnt"):
        return "count"
    if "avg" in column_name.lower() or "rate" in column_name.lower():
        return "avg"
    return "sum"


_SEMANTIC_PATTERNS = [
    (r"\b(city|城市|城市名)\b", "city"),
    (r"\b(province|prov|省份|省)\b", "geo"),
    (r"\b(country|国家|nation)\b", "geo"),
    (r"\b(longitude|lng|经度|lon)\b", "geo"),
    (r"\b(latitude|lat|纬度)\b", "geo"),
    (r"\b(amount|金额|价格|price|revenue|收入|cost|成本|fee)\b", "currency"),
    (r"\b(percentage|rate|ratio|百分比|比例|率)\b", "percentage"),
    (r"\b(url|link|网址|链接|href)\b", "url"),
    (r"\b(image|img|图片|avatar|头像|photo|照片)\b", "image"),
    (r"\b(email|邮箱|mail)\b", "string"),
]


def _guess_semantic_type(column_name: str) -> Optional[str]:
    """Guess the semantic type from the column name."""
    lower = column_name.lower()
    for pattern, stype in _SEMANTIC_PATTERNS:
        if re.search(pattern, lower):
            return stype
    return None


def _type_from_python_value(val: Any) -> str:
    """Infer a canonical type from a Python value (for fallback detection)."""
    if val is None:
        return "string"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "float"
    if isinstance(val, (datetime,)):
        return "datetime"
    return "string"


# ---------------------------------------------------------------------------
# 1. create_dataset
# ---------------------------------------------------------------------------


async def create_dataset(
    db: AsyncSession, data: dict, user_id: Optional[str] = None
) -> Dataset:
    """创建数据集。

    *data* 应包含: name, datasource_id, sql_text(可选), description(可选),
    config(可选), cache_ttl(可选), category(可选), tags(可选)

    自动从关联数据源冗余 datasource_name。
    """
    datasource_id = data["datasource_id"]

    # 解析关联数据源名称
    datasource_name = None
    result = await db.execute(
        select(DataSource.name).where(
            DataSource.id == datasource_id,
            DataSource.is_deleted == False,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        datasource_name = row

    ds = Dataset(
        name=data["name"],
        description=data.get("description"),
        datasource_id=datasource_id,
        datasource_name=datasource_name,
        sql_text=data.get("sql_text"),
        config=data.get("config"),
        cache_ttl=data.get("cache_ttl", 300),
        status=data.get("status", "draft"),
        created_by=user_id,
        category=data.get("category"),
        tags=data.get("tags"),
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    logger.info("创建数据集: %s (datasource=%s, user=%s)", ds.id, datasource_id, user_id)
    return ds


# ---------------------------------------------------------------------------
# 2. update_dataset
# ---------------------------------------------------------------------------


async def update_dataset(db: AsyncSession, ds_id: str, data: dict) -> Optional[Dataset]:
    """部分更新数据集。返回更新后的 Dataset，不存在时返回 None。"""
    ds = await get_dataset(db, ds_id)
    if not ds:
        logger.warning("更新数据集失败: ds_id=%s 不存在", ds_id)
        return None

    updatable = (
        "name", "description", "sql_text", "config", "cache_ttl",
        "status", "category", "tags",
    )
    for key in updatable:
        val = data.get(key)
        if val is not None and hasattr(ds, key):
            setattr(ds, key, val)

    await db.commit()
    await db.refresh(ds)
    logger.info("更新数据集: %s", ds_id)
    return ds


# ---------------------------------------------------------------------------
# 3. delete_dataset
# ---------------------------------------------------------------------------


async def delete_dataset(db: AsyncSession, ds_id: str) -> bool:
    """软删除数据集。成功返回 True，不存在返回 False。"""
    ds = await get_dataset(db, ds_id)
    if not ds:
        return False
    ds.is_deleted = True
    ds.deleted_at = datetime.now(timezone.utc)
    ds.status = "archived"
    await db.commit()
    logger.info("删除数据集: %s", ds_id)
    return True


# ---------------------------------------------------------------------------
# 4. get_dataset
# ---------------------------------------------------------------------------


async def get_dataset(db: AsyncSession, ds_id: str) -> Optional[Dataset]:
    """根据 ID 获取数据集（排除已软删除的）。"""
    result = await db.execute(
        select(Dataset).where(
            Dataset.id == ds_id,
            Dataset.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 5. list_datasets
# ---------------------------------------------------------------------------


async def list_datasets(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    datasource_id: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[int, list[Dataset]]:
    """分页列出数据集。可按数据源ID和状态过滤。"""
    query = select(Dataset).where(Dataset.is_deleted == False)
    count_q = select(func.count()).select_from(Dataset).where(Dataset.is_deleted == False)

    if datasource_id:
        query = query.where(Dataset.datasource_id == datasource_id)
        count_q = count_q.where(Dataset.datasource_id == datasource_id)

    if status:
        query = query.where(Dataset.status == status)
        count_q = count_q.where(Dataset.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Dataset.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    return total, items


# ---------------------------------------------------------------------------
# 6. preview_data
# ---------------------------------------------------------------------------


async def _get_dataset_sql(ds: Dataset) -> str:
    """Resolve the effective SQL for a dataset.

    If ``sql_text`` is set, use it directly.  Otherwise, construct a
    ``SELECT * FROM <first table>`` query from the dataset config.
    """
    if ds.sql_text:
        return ds.sql_text.strip()

    if ds.config and ds.config.get("tables"):
        table = ds.config["tables"][0]
        return f"SELECT * FROM {table}"

    raise ValueError("数据集未配置 SQL 查询或数据表，无法执行预览")


async def _get_executor_for_dataset(
    db: AsyncSession, ds: Dataset
) -> AsyncSQLExecutor:
    """Return an ``AsyncSQLExecutor`` wired to the dataset's datasource.

    The caller is responsible for calling ``await executor.close()`` when done.
    """
    result = await db.execute(
        select(DataSource.config, DataSource.type).where(
            DataSource.id == ds.datasource_id,
            DataSource.is_deleted == False,
            DataSource.status != "disabled",
        )
    )
    row = result.one_or_none()
    if not row:
        raise ValueError(f"关联数据源不存在或不可用: {ds.datasource_id}")

    ds_config, ds_type = row
    config_with_type = dict(ds_config or {})
    config_with_type["type"] = ds_type

    return await create_executor_from_datasource(config_with_type, default_timeout=30.0)


async def preview_data(
    db: AsyncSession,
    dataset_id: str,
    limit: int = 100,
) -> dict:
    """预览数据集的前 N 行数据。

    流程:
    1. 获取数据集
    2. 解析 SQL 文本
    3. 连接数据源并执行查询 (LIMIT 由代码追加)
    4. 返回 {columns, rows, total, execution_time_ms}
    """
    ds = await get_dataset(db, dataset_id)
    if not ds:
        raise ValueError(f"数据集不存在: {dataset_id}")

    sql = await _get_dataset_sql(ds)

    # Append LIMIT if not already present (naive check)
    if "LIMIT" not in sql.upper():
        sql = f"{sql.rstrip(';')} LIMIT {int(limit)}"

    executor = await _get_executor_for_dataset(db, ds)
    try:
        start = time.perf_counter()
        result = await executor.execute(sql)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not result.success:
            raise RuntimeError(result.error or "查询执行失败")

        return {
            "columns": result.columns,
            "rows": result.rows,
            "total": result.row_count,
            "execution_time_ms": round(elapsed_ms, 1),
        }
    finally:
        try:
            await executor.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 7. execute_dataset_sql
# ---------------------------------------------------------------------------


async def execute_dataset_sql(
    db: AsyncSession,
    dataset_id: str,
    custom_sql: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """在数据集关联的数据源上执行 SQL 并返回结果。

    参数
    ----
    custom_sql:
        自定义 SQL。为 None 时使用数据集本身的 sql_text。
    limit:
        限制返回行数，追加到 SQL 末尾（仅当 SQL 中没有 LIMIT 时）。
    """
    ds = await get_dataset(db, dataset_id)
    if not ds:
        raise ValueError(f"数据集不存在: {dataset_id}")

    sql = (custom_sql or ds.sql_text or "").strip()
    if not sql:
        raise ValueError("未提供可执行的 SQL")

    # Append LIMIT if not already present
    if "LIMIT" not in sql.upper():
        sql = f"{sql.rstrip(';')} LIMIT {int(limit)}"

    executor = await _get_executor_for_dataset(db, ds)
    try:
        result = await executor.execute(sql)

        if not result.success:
            raise RuntimeError(result.error or "查询执行失败")

        return {
            "columns": result.columns,
            "rows": result.rows,
        }
    finally:
        try:
            await executor.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 8. import_columns
# ---------------------------------------------------------------------------


async def import_columns(db: AsyncSession, dataset_id: str) -> list[DatasetColumn]:
    """从数据集的 SQL 查询中自动检测字段并创建/更新 DatasetColumn 记录。

    策略:
    1. 尝试用 LIMIT 0 获取列名和类型（通过 SQLAlchemy result keys + 查询一小批
       真实数据来推断类型）。
    2. 删除该数据集已有的所有列记录，全量重建。
    3. 对每一列推断 data_type / is_dimension / is_metric / semantic_type。
    """
    ds = await get_dataset(db, dataset_id)
    if not ds:
        raise ValueError(f"数据集不存在: {dataset_id}")

    # 1. 执行探测查询获取列名和少量样本数据用以推断类型
    sql = await _get_dataset_sql(ds)
    probe_sql = f"{sql.rstrip(';')} LIMIT 5"

    executor = await _get_executor_for_dataset(db, ds)
    try:
        result = await executor.execute(probe_sql)
        if not result.success:
            raise RuntimeError(result.error or "探测查询失败")

        columns = result.columns
        rows = result.rows
    finally:
        try:
            await executor.close()
        except Exception:
            pass

    # 2. 删除旧字段记录，全量重建
    await db.execute(
        DatasetColumn.__table__.delete().where(
            DatasetColumn.dataset_id == dataset_id
        )
    )

    # 3. 推断每列的类型
    # --- 优先使用 SQLAlchemy 返回的列名进行启发式判断 ---
    # 我们从 rows 数据中采样推断实际 Python 类型
    column_types: dict[str, str] = {}
    for col in columns:
        # 从样本数据中收集非 None 值
        sampled_types: list[str] = []
        for row_dict in rows:
            val = row_dict.get(col)
            if val is not None:
                sampled_types.append(_type_from_python_value(val))
        if sampled_types:
            # 使用出现最多的类型
            from collections import Counter
            column_types[col] = Counter(sampled_types).most_common(1)[0][0]
        else:
            # fallback: 从列名推断
            lower = col.lower()
            if any(kw in lower for kw in ("date", "time", "at", "created", "updated")):
                column_types[col] = "datetime"
            elif any(kw in lower for kw in ("count", "num", "id", "age", "year", "qty", "quantity")):
                column_types[col] = "int"
            elif any(kw in lower for kw in ("amount", "price", "rate", "total", "sum", "avg", "cost", "fee", "revenue")):
                column_types[col] = "float"
            elif any(kw in lower for kw in ("is_", "has_", "flag", "active", "deleted", "enabled")):
                column_types[col] = "boolean"
            else:
                column_types[col] = "string"

    # 4. 创建新的 DatasetColumn 记录
    new_columns: list[DatasetColumn] = []
    for idx, col_name in enumerate(columns):
        data_type = column_types.get(col_name, "string")
        dcol = DatasetColumn(
            dataset_id=dataset_id,
            column_name=col_name,
            alias=col_name,
            data_type=data_type,
            is_virtual=False,
            is_dimension=_guess_is_dimension(data_type, col_name),
            is_metric=_guess_is_metric(data_type, col_name),
            default_aggregation=_guess_aggregation(data_type, col_name),
            semantic_type=_guess_semantic_type(col_name),
            sort_order=idx,
        )
        db.add(dcol)
        new_columns.append(dcol)

    await db.commit()
    # Refresh each to get populated IDs / timestamps
    for dcol in new_columns:
        await db.refresh(dcol)

    # 更新数据集的 schema_info
    ds.schema_info = [
        {
            "name": col_name,
            "type": column_types.get(col_name, "string"),
            "alias": col_name,
            "is_dimension": _guess_is_dimension(column_types.get(col_name, "string"), col_name),
            "is_metric": _guess_is_metric(column_types.get(col_name, "string"), col_name),
        }
        for col_name in columns
    ]
    await db.commit()
    await db.refresh(ds)

    logger.info(
        "字段导入完成: dataset_id=%s, 字段数=%d", dataset_id, len(new_columns)
    )
    return new_columns


# ---------------------------------------------------------------------------
# 9. get_dataset_columns
# ---------------------------------------------------------------------------


async def get_dataset_columns(
    db: AsyncSession, dataset_id: str
) -> list[DatasetColumn]:
    """获取数据集的字段配置列表，按 sort_order 排序。"""
    result = await db.execute(
        select(DatasetColumn)
        .where(DatasetColumn.dataset_id == dataset_id)
        .order_by(DatasetColumn.sort_order)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# 10. update_dataset_column
# ---------------------------------------------------------------------------


_UPDATABLE_COLUMN_FIELDS = (
    "alias", "data_type", "is_virtual", "virtual_expr",
    "is_dimension", "is_metric", "default_aggregation",
    "format_config", "semantic_type", "sort_order",
)


async def update_dataset_column(
    db: AsyncSession, column_id: str, data: dict
) -> Optional[DatasetColumn]:
    """更新单个字段配置。返回更新后的 DatasetColumn，不存在时返回 None。"""
    result = await db.execute(
        select(DatasetColumn).where(DatasetColumn.id == column_id)
    )
    dcol = result.scalar_one_or_none()
    if not dcol:
        logger.warning("更新字段失败: column_id=%s 不存在", column_id)
        return None

    for key in _UPDATABLE_COLUMN_FIELDS:
        val = data.get(key)
        if val is not None and hasattr(dcol, key):
            setattr(dcol, key, val)

    await db.commit()
    await db.refresh(dcol)
    logger.info("更新字段: column_id=%s column_name=%s", column_id, dcol.column_name)
    return dcol
