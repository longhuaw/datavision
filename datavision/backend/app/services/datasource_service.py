"""
数据源管理服务 - 创建、更新、删除、列表、连接测试、元数据同步
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select, func, text

from app.models.datasource import DataSource, DataSourceMetadata

logger = logging.getLogger("datavision.datasource")

# ---------------------------------------------------------------------------
# URL 构建
# ---------------------------------------------------------------------------

SUPPORTED_SQL_TYPES = ("mysql", "postgresql", "clickhouse", "mssql", "sqlite")

DRIVER_MAP = {
    "mysql":      "mysql+asyncmy",
    "postgresql": "postgresql+asyncpg",
    "clickhouse": "clickhouse+asynch",
    "mssql":      "mssql+aioodbc",
    "sqlite":     "sqlite+aiosqlite",
}


def _build_url(ds_type: str, config: dict) -> str:
    """根据数据源类型和配置构建 SQLAlchemy 异步连接 URL。"""
    ds_type = ds_type.lower()
    driver = DRIVER_MAP.get(ds_type, f"{ds_type}+asyncmy")
    host = config.get("host", "localhost")
    port = config.get("port")
    database = config.get("database", "")
    username = config.get("username", "")
    password = config.get("password", "")

    if ds_type == "sqlite":
        return f"{driver}:///{database}"

    # 端口默认值
    default_ports = {
        "mysql": 3306, "postgresql": 5432, "clickhouse": 9000, "mssql": 1433,
    }
    if port is None:
        port = default_ports.get(ds_type, 3306)

    # URL 编码密码中的特殊字符
    from urllib.parse import quote_plus
    user = quote_plus(str(username))
    pwd = quote_plus(str(password))
    host_str = f"{host}:{port}"

    if ds_type == "postgresql":
        schema = config.get("schema", "public")
        return f"{driver}://{user}:{pwd}@{host_str}/{database}?options=-c search_path={schema}"
    elif ds_type == "clickhouse":
        return f"{driver}://{user}:{pwd}@{host_str}/{database}"
    elif ds_type == "mssql":
        params = config.get("params", "")
        url = f"{driver}://{user}:{pwd}@{host_str}/{database}"
        if params:
            url += f"?{params}"
        return url
    else:
        charset = config.get("charset", "utf8mb4")
        return f"{driver}://{user}:{pwd}@{host_str}/{database}?charset={charset}"


def _create_engine_for_ds(ds_type: str, config: dict):
    """为指定数据源创建一个临时异步引擎（调用方负责 dispose）。"""
    ds_type = ds_type.lower()
    if ds_type not in SUPPORTED_SQL_TYPES:
        raise ValueError(f"不支持的数据源类型: {ds_type}")
    url = _build_url(ds_type, config)
    return create_async_engine(url, echo=False, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_datasource(
    db: AsyncSession, data: dict, user_id: Optional[str] = None
) -> DataSource:
    """
    创建数据源。

    data 应包含: name, type, config, description(可选), tags(可选), icon(可选)
    """
    ds = DataSource(
        name=data["name"],
        type=data["type"],
        config=data["config"],
        description=data.get("description"),
        created_by=user_id,
        tags=data.get("tags"),
        icon=data.get("icon"),
        status="active",
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    logger.info("创建数据源: %s (type=%s, user=%s)", ds.id, ds.type, user_id)
    return ds


async def update_datasource(
    db: AsyncSession, ds_id: str, data: dict
) -> Optional[DataSource]:
    """
    更新数据源。data 为部分字段字典，值为 None 的字段会被跳过。
    返回更新后的 DataSource，不存在时返回 None。
    """
    ds = await get_datasource(db, ds_id)
    if not ds:
        return None
    for key, val in data.items():
        if val is not None and hasattr(ds, key):
            setattr(ds, key, val)
    # 配置变更时递增版本号
    if "config" in data and data["config"] is not None:
        ds.version = (ds.version or 0) + 1
    await db.commit()
    await db.refresh(ds)
    logger.info("更新数据源: %s", ds_id)
    return ds


async def delete_datasource(db: AsyncSession, ds_id: str) -> bool:
    """软删除数据源。成功返回 True，不存在返回 False。"""
    ds = await get_datasource(db, ds_id)
    if not ds:
        return False
    ds.is_deleted = True
    ds.deleted_at = datetime.now(timezone.utc)
    ds.status = "disabled"
    await db.commit()
    logger.info("删除数据源: %s", ds_id)
    return True


async def get_datasource(db: AsyncSession, ds_id: str) -> Optional[DataSource]:
    """根据 ID 获取数据源（排除已软删除的）。"""
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == ds_id,
            DataSource.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def list_datasources(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    type_filter: Optional[str] = None,
) -> tuple[int, list[DataSource]]:
    """
    分页列出数据源。可按类型过滤。
    返回 (总数, DataSource 列表)。
    """
    base_where = DataSource.is_deleted == False

    query = select(DataSource).where(base_where)
    count_q = select(func.count()).select_from(DataSource).where(base_where)

    if type_filter:
        query = query.where(DataSource.type == type_filter)
        count_q = count_q.where(DataSource.type == type_filter)

    total = (await db.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(DataSource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    return total, items


# ---------------------------------------------------------------------------
# 连接测试
# ---------------------------------------------------------------------------

async def _get_ds_config(db: AsyncSession, ds_id_or_config) -> tuple[str, dict]:
    """
    解析 ds_id_or_config，返回 (type, config)。
    支持传入数据源 ID (str) 或直接传入 {"type": ..., "config": ...}。
    """
    if isinstance(ds_id_or_config, dict):
        return ds_id_or_config["type"], ds_id_or_config["config"]

    # 按 ID 查询
    ds = await get_datasource(db, ds_id_or_config)
    if not ds:
        raise ValueError(f"数据源不存在: {ds_id_or_config}")
    return ds.type, ds.config


async def _fetch_tables(
    ds_type: str, config: dict
) -> list[str]:
    """
    连接到指定数据源，从 information_schema 获取表名列表。
    仅支持关系型数据库。
    """
    ds_type = ds_type.lower()
    database = config.get("database", "")

    engine = _create_engine_for_ds(ds_type, config)
    try:
        async with engine.begin() as conn:
            if ds_type == "mysql":
                sql = text(
                    "SELECT table_name AS tbl "
                    "FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                )
                result = await conn.execute(sql, {"schema": database})
                rows = result.fetchall()
                return [row[0] for row in rows]

            elif ds_type == "postgresql":
                schema = config.get("schema", "public")
                sql = text(
                    "SELECT table_name AS tbl "
                    "FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name"
                )
                result = await conn.execute(sql, {"schema": schema})
                rows = result.fetchall()
                return [row[0] for row in rows]

            elif ds_type == "mssql":
                sql = text(
                    "SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS tbl "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME"
                )
                result = await conn.execute(sql)
                rows = result.fetchall()
                return [row[0] for row in rows]

            elif ds_type == "clickhouse":
                sql = text(
                    "SELECT name FROM system.tables "
                    "WHERE database = :db ORDER BY name"
                )
                result = await conn.execute(sql, {"db": database})
                rows = result.fetchall()
                return [row[0] for row in rows]

            elif ds_type == "sqlite":
                sql = text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
                result = await conn.execute(sql)
                rows = result.fetchall()
                return [row[0] for row in rows]

            return []
    finally:
        await engine.dispose()


async def test_connection(
    db: AsyncSession, ds_id_or_config
) -> dict:
    """
    测试数据源连接。

    参数:
        ds_id_or_config:
            - str: 数据源 ID，从数据库读取配置
            - dict: {"type": "...", "config": {...}} 直接传入

    返回:
        {"success": bool, "message": str, "tables": list[str]}
    """
    try:
        ds_type, config = await _get_ds_config(db, ds_id_or_config)
    except ValueError as e:
        return {"success": False, "message": str(e), "tables": []}

    ds_type = ds_type.lower()

    # API 类型：HTTP 探测
    if ds_type == "api":
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                method = config.get("method", "GET").upper()
                url = config.get("base_url", "")
                headers = config.get("headers", {}) or {}
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, headers=headers, json=config.get("body", {}))
                ok = resp.status_code < 500
                return {
                    "success": ok,
                    "message": f"API 响应状态: {resp.status_code}" if ok else f"API 返回错误: {resp.status_code}",
                    "tables": [],
                }
        except Exception as e:
            return {"success": False, "message": f"API 连接失败: {str(e)}", "tables": []}

    # Excel 类型
    if ds_type == "excel":
        import os
        file_path = config.get("file_path", "")
        if os.path.exists(file_path):
            return {"success": True, "message": "文件存在", "tables": []}
        return {"success": False, "message": f"文件不存在: {file_path}", "tables": []}

    # SQL 类型
    if ds_type in SUPPORTED_SQL_TYPES:
        try:
            engine = _create_engine_for_ds(ds_type, config)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

            # 获取表列表
            tables = await _fetch_tables(ds_type, config)
            await engine.dispose()
            return {
                "success": True,
                "message": f"连接成功，发现 {len(tables)} 张表",
                "tables": tables,
            }
        except Exception as e:
            logger.exception("连接测试失败: %s", ds_type)
            return {"success": False, "message": f"连接失败: {str(e)}", "tables": []}

    return {"success": False, "message": f"不支持的数据源类型: {ds_type}", "tables": []}


# ---------------------------------------------------------------------------
# 元数据同步
# ---------------------------------------------------------------------------

async def _fetch_columns(
    ds_type: str, config: dict, table_name: str
) -> list[dict]:
    """获取单张表的列信息。"""
    ds_type = ds_type.lower()
    database = config.get("database", "")
    engine = _create_engine_for_ds(ds_type, config)
    try:
        async with engine.begin() as conn:
            if ds_type == "mysql":
                sql = text(
                    "SELECT column_name, data_type, is_nullable, column_key, "
                    "column_default, column_comment, ordinal_position "
                    "FROM information_schema.columns "
                    "WHERE table_schema = :db AND table_name = :tbl "
                    "ORDER BY ordinal_position"
                )
                result = await conn.execute(sql, {"db": database, "tbl": table_name})

            elif ds_type == "postgresql":
                schema = config.get("schema", "public")
                sql = text(
                    "SELECT column_name, data_type, is_nullable, "
                    "CASE WHEN column_default LIKE 'nextval%%' THEN 'auto' ELSE column_default END, "
                    "CAST(NULL AS text), ordinal_position "
                    "FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = :tbl "
                    "ORDER BY ordinal_position"
                )
                result = await conn.execute(sql, {"schema": schema, "tbl": table_name})

            elif ds_type == "mssql":
                sql = text(
                    "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, "
                    "CAST(NULL AS varchar), COLUMN_DEFAULT, CAST(NULL AS varchar), ORDINAL_POSITION "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = :tbl "
                    "ORDER BY ORDINAL_POSITION"
                )
                result = await conn.execute(sql, {"tbl": table_name})

            elif ds_type == "clickhouse":
                sql = text(
                    "SELECT name, type, 'YES', "
                    "CAST(NULL AS String), CAST(NULL AS String), CAST(NULL AS String), position "
                    "FROM system.columns "
                    "WHERE database = :db AND table = :tbl "
                    "ORDER BY position"
                )
                result = await conn.execute(sql, {"db": database, "tbl": table_name})

            elif ds_type == "sqlite":
                sql = text(f"PRAGMA table_info('{table_name}')")
                result = await conn.execute(sql)
                rows = result.fetchall()
                # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
                columns = []
                for row in rows:
                    columns.append({
                        "name": row[1],
                        "type": row[2] or "TEXT",
                        "nullable": not bool(row[3]),
                        "primary_key": bool(row[5]),
                        "default_value": str(row[4]) if row[4] is not None else None,
                        "comment": None,
                        "ordinal_position": row[0] + 1,
                    })
                return columns
            else:
                return []

            rows = result.fetchall()
            columns = []
            for row in rows:
                col_info = {
                    "name": row[0],
                    "type": row[1] or "unknown",
                    "nullable": row[2].upper() == "YES" if row[2] else True,
                    "primary_key": row[3] == "PRI" if row[3] else False,
                    "default_value": str(row[4]) if row[4] is not None else None,
                    "comment": row[5] if len(row) > 5 and row[5] else None,
                    "ordinal_position": row[6] if len(row) > 6 else None,
                }
                columns.append(col_info)
            return columns
    finally:
        await engine.dispose()


async def _fetch_all_metadata(
    ds_type: str, config: dict
) -> list[dict]:
    """获取所有表的完整元数据（表名 + 列信息）。"""
    table_names = await _fetch_tables(ds_type, config)
    tables = []
    for tname in table_names:
        try:
            columns = await _fetch_columns(ds_type, config, tname)
            tables.append({
                "table_name": tname,
                "columns": columns,
            })
        except Exception as e:
            logger.warning("获取表 %s 元数据失败: %s", tname, e)
            tables.append({
                "table_name": tname,
                "columns": [],
                "error": str(e),
            })
    return tables


async def sync_metadata(
    db: AsyncSession, ds_id: str
) -> DataSourceMetadata:
    """
    同步数据源元数据。

    1. 连接数据源
    2. 获取所有表和列信息
    3. 存入 DataSourceMetadata
    4. 更新 sync_status

    返回 DataSourceMetadata。
    """
    ds = await get_datasource(db, ds_id)
    if not ds:
        raise ValueError(f"数据源不存在: {ds_id}")

    # 查找或创建 metadata 记录
    result = await db.execute(
        select(DataSourceMetadata).where(
            DataSourceMetadata.datasource_id == ds_id
        )
    )
    meta = result.scalar_one_or_none()

    if meta is None:
        meta = DataSourceMetadata(datasource_id=ds_id)
        db.add(meta)

    meta.sync_status = "syncing"
    await db.commit()

    try:
        if ds.type.lower() in SUPPORTED_SQL_TYPES:
            tables = await _fetch_all_metadata(ds.type, ds.config)
            meta.tables_info = tables
            meta.last_sync_at = datetime.now(timezone.utc)
            meta.sync_status = "success"
            meta.sync_error = None
            logger.info("元数据同步成功: ds_id=%s, 表数=%d", ds_id, len(tables))
        else:
            meta.sync_status = "failed"
            meta.sync_error = f"不支持的数据源类型: {ds.type}"
            logger.warning("元数据同步跳过: ds_id=%s, type=%s", ds_id, ds.type)
    except Exception as e:
        meta.sync_status = "failed"
        meta.sync_error = str(e)
        logger.exception("元数据同步失败: ds_id=%s", ds_id)

    await db.commit()
    await db.refresh(meta)
    return meta


async def get_tables(ds_id: str, db: AsyncSession) -> list[dict]:
    """
    从缓存的元数据中获取表列表。

    返回:
    [
      {
        "table_name": "orders",
        "column_count": 5,
        "columns": [...]
      },
      ...
    ]
    """
    result = await db.execute(
        select(DataSourceMetadata).where(
            DataSourceMetadata.datasource_id == ds_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta or not meta.tables_info:
        return []

    tables = []
    for t in meta.tables_info:
        entry = dict(t)
        entry["column_count"] = len(t.get("columns", []))
        tables.append(entry)
    return tables


async def get_table_columns(
    ds_id: str, table_name: str, db: AsyncSession
) -> list[dict]:
    """
    从缓存的元数据中获取指定表的列信息。

    返回:
    [
      {"name": "id", "type": "int", "nullable": false, "primary_key": true, ...},
      ...
    ]
    """
    result = await db.execute(
        select(DataSourceMetadata).where(
            DataSourceMetadata.datasource_id == ds_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta or not meta.tables_info:
        return []

    for t in meta.tables_info:
        if t.get("table_name") == table_name:
            return t.get("columns", [])
    return []
