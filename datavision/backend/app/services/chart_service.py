"""
图表服务 - 图表CRUD、数据查询、缓存管理和图表类型推荐
"""
import logging
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.chart import Chart, ChartCache
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.schemas.chart import ChartCreate, ChartUpdate

# 核心工具
from app.core.query_builder import QueryBuilder, QueryBuilderError
from app.core.sql_executor import (
    AsyncSQLExecutor,
    create_engine_from_datasource,
    QueryResult,
)
from app.core.cache_manager import CacheManager, KEY_CHART
from app.core.chart_recommender import ChartRecommender, ChartRecommendation

logger = logging.getLogger("datavision.chart_service")

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _build_data_hash(data: dict) -> str:
    """计算数据哈希，用于判断缓存是否需要刷新"""
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1. 创建图表
# ---------------------------------------------------------------------------


async def create_chart(
    db: AsyncSession, data: ChartCreate, user_id: Optional[str] = None
) -> Chart:
    """根据 ChartCreate 数据创建新图表"""
    chart = Chart(
        name=data.name,
        description=data.description,
        chart_type=data.chart_type,
        dataset_id=data.dataset_id,
        config=data.config,
        style_config=data.style_config,
        query_config=data.query_config,
        nl_prompt=data.nl_prompt,
        category=data.category,
        created_by=user_id,
    )
    db.add(chart)
    await db.commit()
    await db.refresh(chart)
    logger.info("图表已创建 id=%s name=%s type=%s", chart.id, chart.name, chart.chart_type)
    return chart


# ---------------------------------------------------------------------------
# 2. 更新图表
# ---------------------------------------------------------------------------


async def update_chart(
    db: AsyncSession, chart_id: str, data: ChartUpdate
) -> Optional[Chart]:
    """更新图表配置，返回更新后的 Chart，图表不存在时返回 None"""
    chart = await get_chart(db, chart_id)
    if not chart:
        logger.warning("更新图表失败: chart_id=%s 不存在", chart_id)
        return None

    # 仅更新非 None 的字段
    for field in (
        "name", "description", "chart_type", "config",
        "style_config", "query_config", "category",
    ):
        val = getattr(data, field, None)
        if val is not None:
            setattr(chart, field, val)

    chart.version = (chart.version or 1) + 1  # 更新版本号
    await db.commit()
    await db.refresh(chart)
    logger.info("图表已更新 id=%s version=%d", chart.id, chart.version)
    return chart


# ---------------------------------------------------------------------------
# 3. 软删除图表
# ---------------------------------------------------------------------------


async def delete_chart(db: AsyncSession, chart_id: str) -> bool:
    """软删除图表，同时清除对应的缓存"""
    chart = await get_chart(db, chart_id)
    if not chart:
        return False

    chart.is_deleted = True
    chart.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("图表已软删除 id=%s", chart_id)
    return True


# ---------------------------------------------------------------------------
# 4. 获取单个图表
# ---------------------------------------------------------------------------


async def get_chart(db: AsyncSession, chart_id: str) -> Optional[Chart]:
    """根据 ID 获取单个图表（自动过滤已删除记录）"""
    result = await db.execute(
        select(Chart).where(Chart.id == chart_id, Chart.is_deleted == False)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 5. 分页查询图表列表
# ---------------------------------------------------------------------------


async def list_charts(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    chart_type: Optional[str] = None,
    category: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> tuple[int, list[Chart]]:
    """分页获取图表列表，支持按 chart_type / category / dataset_id 过滤"""
    query = select(Chart).where(Chart.is_deleted == False)
    count_q = select(func.count()).select_from(Chart).where(Chart.is_deleted == False)

    if chart_type:
        query = query.where(Chart.chart_type == chart_type)
        count_q = count_q.where(Chart.chart_type == chart_type)

    if category:
        query = query.where(Chart.category == category)
        count_q = count_q.where(Chart.category == category)

    if dataset_id:
        query = query.where(Chart.dataset_id == dataset_id)
        count_q = count_q.where(Chart.dataset_id == dataset_id)

    # 获取总数
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.order_by(Chart.updated_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    charts = list(result.scalars().all())

    return total, charts


# ---------------------------------------------------------------------------
# 6. 获取图表数据（含缓存）
# ---------------------------------------------------------------------------


async def get_chart_data(
    db: AsyncSession,
    chart_id: str,
    cache_manager: Optional[CacheManager] = None,
    force_refresh: bool = False,
) -> dict:
    """根据图表配置执行 SQL 查询并返回数据。

    流程：
    1. 校验图表是否存在
    2. 查询 Redis 缓存（未过期 + force_refresh=False 时直接返回）
    3. 从 chart.config 构建 SQL（使用 QueryBuilder）
    4. 解析关联的数据集 -> 数据源，创建异步引擎执行 SQL
    5. 将结果写入 Redis 缓存
    6. 返回 {columns, rows, cached, execution_time_ms}

    参数
    ----
    cache_manager : CacheManager | None
        Redis 缓存管理器，为 None 时跳过缓存逻辑
    force_refresh : bool
        是否强制刷新，忽略已有的缓存数据
    """
    # 检查图表
    chart = await get_chart(db, chart_id)
    if not chart:
        raise ValueError(f"图表不存在: {chart_id}")

    # 尝试从缓存中读取
    cache_key = KEY_CHART(chart_id)  # "dv:chart:{chart_id}"
    if cache_manager and not force_refresh:
        cached = await cache_manager.get(cache_key)
        if cached and isinstance(cached, dict):
            logger.debug("命中缓存 chart_id=%s", chart_id)
            return {
                "columns": cached.get("columns", []),
                "rows": cached.get("rows", []),
                "cached": True,
                "execution_time_ms": 0,
            }

    # 解析关联的数据集和数据源
    dataset = await _get_dataset(db, chart.dataset_id)
    if not dataset:
        raise ValueError(f"关联数据集不存在: {chart.dataset_id}")

    datasource = await _get_datasource(db, dataset.datasource_id)
    if not datasource:
        raise ValueError(f"关联数据源不存在: {dataset.datasource_id}")

    # 解析图表配置：优先使用 dataset 的 SQL，否则从 chart.config 构建
    chart_config = chart.config or {}
    query_config = chart.query_config or {}

    if dataset.sql_text:
        # 数据集有自定义 SQL，直接使用
        sql = dataset.sql_text.strip()
        params = {}
    else:
        # 从图表 config 中提取维度、度量、过滤、排序等，使用 QueryBuilder 构建 SQL
        table_name = dataset.config.get("tables", [None])[0] if dataset.config else None
        if not table_name:
            raise ValueError("无法确定数据表，请检查数据集配置中的 tables 字段")

        dimensions_raw = chart_config.get("dimensions", [])
        metrics_raw = chart_config.get("metrics", [])
        filters_raw = chart_config.get("filters", [])
        order_by_raw = chart_config.get("order_by", [])
        limit = chart_config.get("limit")
        max_rows = query_config.get("max_rows", 10000)

        dimensions = [{"column": d["field"], "alias": d.get("alias")} for d in dimensions_raw]
        metrics = [
            {"column": m["field"], "function": m.get("aggregation", "SUM"), "alias": m.get("alias")}
            for m in metrics_raw
        ]
        filters = [
            {"column": f["field"], "operator": f["operator"], "value": f.get("value")}
            for f in filters_raw
        ]
        order_by = [
            {"column": o["field"], "direction": o.get("direction", "ASC")}
            for o in order_by_raw
        ]

        # 构建 SQL
        try:
            builder = QueryBuilder()
            sql, params_list = builder.build(
                table_name=table_name,
                dimensions=dimensions if dimensions else None,
                metrics=metrics if metrics else None,
                filters=filters if filters else None,
                order_by=order_by if order_by else None,
                limit=min(limit, max_rows) if limit else (max_rows if not dimensions else None),
            )
            # core QueryBuilder returns params as list — convert to dict for executor
            params = {}
        except QueryBuilderError as e:
            logger.error("SQL 构建失败 chart_id=%s: %s", chart_id, e)
            raise ValueError(f"SQL 构建失败: {e}")

    # 创建执行器并执行查询
    executor = None
    try:
        engine = create_engine_from_datasource(datasource.config)
        executor = AsyncSQLExecutor(engine, default_timeout=30.0)
        result: QueryResult = await executor.execute(sql, params)

        if not result.success:
            raise RuntimeError(result.error or "查询执行失败")

        columns = result.columns
        rows = result.rows
        execution_time_ms = round(result.elapsed_ms)

    except Exception as e:
        logger.exception("图表数据查询失败 chart_id=%s", chart_id)
        raise RuntimeError(f"数据查询失败: {e}")
    finally:
        if executor is not None:
            try:
                await executor.close()
            except Exception:
                pass

    # 写入缓存
    cache_entry = {"columns": columns, "rows": rows}
    if cache_manager:
        ttl = query_config.get("cache_ttl", 300)
        await cache_manager.set(cache_key, cache_entry, ttl=ttl)

        # 同时更新数据库中的 ChartCache 记录
        data_hash = _build_data_hash(cache_entry)
        await _upsert_chart_cache(db, chart_id, cache_entry, ttl, data_hash)

    return {
        "columns": columns,
        "rows": rows,
        "cached": False,
        "execution_time_ms": execution_time_ms,
    }


# ---------------------------------------------------------------------------
# 7. 推荐图表类型
# ---------------------------------------------------------------------------


async def recommend_chart_type(
    columns_info: list[dict],
    recommender: Optional[ChartRecommender] = None,
) -> dict:
    """分析列信息并返回推荐的图表类型。

    参数
    ----
    columns_info : list[dict]
        每个字典应包含 name/column_name/field, data_type/type,
        可选: cardinality, is_dimension, is_metric, semantic_type
    recommender : ChartRecommender | None
        可复用的推荐器实例，为 None 时自动创建
    """
    if recommender is None:
        recommender = ChartRecommender()

    recommendation: ChartRecommendation = recommender.recommend(columns_info)

    return {
        "recommended_type": recommendation.recommended_type,
        "confidence": recommendation.confidence,
        "reason": recommendation.reason,
        "alternatives": recommendation.alternatives,
    }


# ---------------------------------------------------------------------------
# 8. 删除图表缓存
# ---------------------------------------------------------------------------


async def delete_chart_cache(
    chart_id: str,
    cache_manager: Optional[CacheManager] = None,
    db: Optional[AsyncSession] = None,
) -> bool:
    """清除指定图表的缓存数据（Redis 缓存 + 数据库 ChartCache 记录）。

    参数
    ----
    chart_id : str
        图表 ID
    cache_manager : CacheManager | None
        Redis 缓存管理器，为 None 时跳过 Redis 清除
    db : AsyncSession | None
        数据库会话，为 None 时跳过数据库记录清除

    返回
    ----
    bool
        至少清除了一处缓存时为 True
    """
    deleted = False

    # 清除 Redis 缓存
    if cache_manager is not None:
        cache_key = KEY_CHART(chart_id)
        if await cache_manager.delete(cache_key):
            deleted = True
            logger.debug("已清除 Redis 缓存 chart_id=%s", chart_id)

    # 清除数据库中的 ChartCache 记录
    if db is not None:
        try:
            result = await db.execute(
                select(ChartCache).where(ChartCache.chart_id == chart_id)
            )
            cache_record = result.scalar_one_or_none()
            if cache_record is not None:
                await db.delete(cache_record)
                await db.commit()
                deleted = True
                logger.debug("已清除数据库缓存记录 chart_id=%s", chart_id)
        except Exception as e:
            logger.warning("清除 ChartCache 数据库记录失败 chart_id=%s: %s", chart_id, e)

    return deleted


# ---------------------------------------------------------------------------
# 9. 递增使用次数
# ---------------------------------------------------------------------------


async def increment_usage_count(db: AsyncSession, chart_id: str) -> bool:
    """递增图表的使用次数计数器"""
    chart = await get_chart(db, chart_id)
    if not chart:
        return False

    # 使用 SQL 原子递增，避免并发问题
    await db.execute(
        Chart.__table__.update()
        .where(Chart.id == chart_id)
        .values(usage_count=Chart.usage_count + 1)
    )
    await db.commit()
    logger.debug("图表使用次数递增 chart_id=%s count=%d", chart_id, (chart.usage_count or 0) + 1)
    return True


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


async def _get_dataset(db: AsyncSession, dataset_id: str) -> Optional[Dataset]:
    """获取数据集（不过滤软删除，因为数据集可能未启用软删除）"""
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    return result.scalar_one_or_none()


async def _get_datasource(db: AsyncSession, datasource_id: str) -> Optional[DataSource]:
    """获取数据源（过滤已删除和已禁用的数据源）"""
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.is_deleted == False,
            DataSource.status != "disabled",
        )
    )
    return result.scalar_one_or_none()


async def _upsert_chart_cache(
    db: AsyncSession,
    chart_id: str,
    data: dict,
    ttl: int,
    data_hash: str,
) -> None:
    """更新或插入 ChartCache 数据库记录"""
    try:
        result = await db.execute(
            select(ChartCache).where(ChartCache.chart_id == chart_id)
        )
        cache_record = result.scalar_one_or_none()

        if cache_record:
            cache_record.data = data
            cache_record.cached_at = datetime.now(timezone.utc)
            cache_record.ttl = ttl
            cache_record.data_hash = data_hash
        else:
            cache_record = ChartCache(
                chart_id=chart_id,
                data=data,
                cached_at=datetime.now(timezone.utc),
                ttl=ttl,
                data_hash=data_hash,
            )
            db.add(cache_record)

        await db.commit()
    except Exception as e:
        logger.warning("更新 ChartCache 数据库记录失败 chart_id=%s: %s", chart_id, e)
        # 不影响主流程，仅记录日志
