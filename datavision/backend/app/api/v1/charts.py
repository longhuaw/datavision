"""
图表工作台 API — NL2SQL 自然语言生成图表

核心功能:
- 图表 CRUD（列表、创建、详情、更新、软删除）
- 图表数据查询（含 Redis 缓存）
- 图表类型推荐（基于列特征分析）
- NL2SQL 自然语言转 SQL（核心亮点）
- NL 查询历史与反馈
- 图表克隆
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.dependencies import get_db, get_redis, PaginationParams
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.schemas.chart import (
    ChartCreate,
    ChartUpdate,
    ChartResponse,
    NLQueryRequest,
    NLQueryResponse,
    ChartDataResponse,
)
from app.services import chart_service
from app.services import nl2sql_service
from app.utils.response import success_response, paginated_response, error_response

router = APIRouter(prefix="/charts", tags=["图表工作台"])


# ============================================================================
# 辅助函数
# ============================================================================

def _chart_to_response_dict(chart) -> dict:
    """将 Chart ORM 对象转换为 ChartResponse 兼容的字典。"""
    return {
        "id": chart.id,
        "name": chart.name,
        "description": chart.description,
        "chart_type": chart.chart_type,
        "dataset_id": chart.dataset_id,
        "dataset_name": chart.dataset_name,
        "config": chart.config,
        "style_config": chart.style_config,
        "query_config": chart.query_config,
        "nl_prompt": chart.nl_prompt,
        "generated_sql": chart.generated_sql,
        "nl_confidence": chart.nl_confidence,
        "thumbnail_url": chart.thumbnail_url,
        "version": chart.version,
        "is_template": chart.is_template,
        "category": chart.category,
        "usage_count": chart.usage_count,
        "created_by": chart.created_by,
        "created_at": chart.created_at.isoformat() if chart.created_at else None,
        "updated_at": chart.updated_at.isoformat() if chart.updated_at else None,
    }


def _get_current_user_id(
    current_user: User = Depends(get_current_active_user),
) -> str:
    """返回当前用户 ID，用于记录 created_by。"""
    return current_user.id


# ============================================================================
# 1. 图表列表
# ============================================================================

@router.get("/", summary="图表列表")
async def list_charts(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    chart_type: str = Query(default=None, description="按图表类型过滤"),
    category: str = Query(default=None, description="按分类过滤"),
    dataset_id: str = Query(default=None, description="按关联数据集ID过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """分页获取图表列表，支持按 chart_type / category / dataset_id 过滤。"""
    total, charts = await chart_service.list_charts(
        db,
        page=page,
        page_size=page_size,
        chart_type=chart_type,
        category=category,
        dataset_id=dataset_id,
    )
    data = [_chart_to_response_dict(c) for c in charts]
    return paginated_response(data, total, page, page_size)


# ============================================================================
# 2. 创建图表
# ============================================================================

@router.post("/", summary="创建图表", status_code=201)
async def create_chart(
    body: ChartCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(_get_current_user_id),
):
    """创建新的图表配置。"""
    chart = await chart_service.create_chart(db, data=body, user_id=user_id)
    return success_response(
        data=_chart_to_response_dict(chart),
        message="图表创建成功",
        code=201,
    )


# ============================================================================
# 3. 获取图表详情
# ============================================================================

@router.get("/{chart_id}", summary="获取图表详情")
async def get_chart(
    chart_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """根据 ID 获取单个图表的完整配置信息。"""
    chart = await chart_service.get_chart(db, chart_id)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图表不存在",
        )
    return success_response(data=_chart_to_response_dict(chart))


# ============================================================================
# 4. 更新图表配置
# ============================================================================

@router.put("/{chart_id}", summary="更新图表配置")
async def update_chart(
    chart_id: str,
    body: ChartUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """部分更新图表配置（仅更新提供的字段）。"""
    chart = await chart_service.update_chart(db, chart_id, data=body)
    if not chart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图表不存在",
        )
    return success_response(
        data=_chart_to_response_dict(chart),
        message="图表更新成功",
    )


# ============================================================================
# 5. 软删除图表
# ============================================================================

@router.delete("/{chart_id}", summary="删除图表")
async def delete_chart(
    chart_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(get_current_active_user),
):
    """软删除图表（标记 is_deleted）并清除关联缓存。"""
    ok = await chart_service.delete_chart(db, chart_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图表不存在",
        )

    # 删除后清除图表缓存
    from app.core.cache_manager import CacheManager
    cache = CacheManager(redis)
    await cache.invalidate_chart_cache(chart_id)

    return success_response(message="图表已删除")


# ============================================================================
# 6. 获取图表数据（执行查询）
# ============================================================================

@router.get("/{chart_id}/data", summary="获取图表数据")
async def get_chart_data(
    chart_id: str,
    force_refresh: bool = Query(default=False, description="是否强制刷新缓存"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(get_current_active_user),
):
    """
    根据图表配置执行 SQL 查询并返回数据。

    优先返回 Redis 缓存（除非 force_refresh=true 强制刷新）。
    同时递增 chart 的使用次数。
    """
    from app.core.cache_manager import CacheManager
    cache = CacheManager(redis)

    try:
        result = await chart_service.get_chart_data(
            db,
            chart_id,
            cache_manager=cache,
            force_refresh=force_refresh,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # 递增使用次数（非阻塞，失败不影响主流程）
    try:
        await chart_service.increment_usage_count(db, chart_id)
    except Exception:
        pass

    return success_response(data={
        "chart_id": chart_id,
        "data": {
            "columns": result["columns"],
            "rows": result["rows"],
        },
        "cached": result["cached"],
        "execution_time_ms": result["execution_time_ms"],
    })


# ============================================================================
# 7. 强制刷新图表数据缓存
# ============================================================================

@router.post("/{chart_id}/refresh", summary="刷新图表数据缓存")
async def refresh_chart_data(
    chart_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(get_current_active_user),
):
    """强制刷新指定图表的缓存数据，先清除旧缓存再重新查询。"""
    from app.core.cache_manager import CacheManager
    cache = CacheManager(redis)

    # 先清除已有缓存（Redis + 数据库）
    await chart_service.delete_chart_cache(
        chart_id,
        cache_manager=cache,
        db=db,
    )

    # 重新执行查询并写入缓存
    try:
        result = await chart_service.get_chart_data(
            db,
            chart_id,
            cache_manager=cache,
            force_refresh=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    return success_response(
        data={
            "chart_id": chart_id,
            "data": {
                "columns": result["columns"],
                "rows": result["rows"],
            },
            "cached": False,
            "execution_time_ms": result["execution_time_ms"],
        },
        message="缓存已刷新",
    )


# ============================================================================
# 8. 推荐图表类型
# ============================================================================

@router.post("/recommend-type", summary="推荐图表类型")
async def recommend_chart_type(
    body: dict = Body(..., description="列信息列表，每个元素包含 name/column_name/field、data_type/type 等"),
    _: User = Depends(get_current_active_user),
):
    """
    根据提供的列信息（名称、类型、基数、语义角色等）推荐最优图表类型。

    请求体示例:
        [
            {"field": "order_date", "data_type": "datetime", "is_dimension": true},
            {"field": "amount", "data_type": "decimal", "is_metric": true, "default_aggregation": "SUM"},
            {"field": "region", "data_type": "varchar", "is_dimension": true}
        ]

    返回:
        {"recommended_type": "line", "confidence": 0.92, "reason": "...", "alternatives": ["bar", "area"]}
    """
    if not isinstance(body, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是列信息数组",
        )

    columns_info = body
    if not columns_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="列信息不能为空",
        )

    try:
        result = await chart_service.recommend_chart_type(columns_info)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"图表类型推荐失败: {e}",
        )

    return success_response(data=result)


# ============================================================================
# 9. NL2SQL — 自然语言转 SQL（核心亮点）
# ============================================================================

@router.post("/nl-query", summary="NL2SQL 自然语言查询")
async def nl2sql_query(
    body: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    输入自然语言描述，返回生成的 SQL 和推荐图表类型。

    这是 DataVision 的核心亮点功能：
    1. 加载目标数据集的 schema 上下文（表名、列、类型、角色、样本数据）
    2. 构建精心设计的 LLM 提示词
    3. 调用 LLM 生成 SQL（或 mock 模式）
    4. 校验 SQL 安全性（仅 SELECT）
    5. 保存查询历史
    """
    if not body.dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定 dataset_id",
        )

    # 1. 生成 SQL
    try:
        result = await nl2sql_service.generate_sql(
            prompt=body.prompt,
            dataset_id=body.dataset_id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # 2. 注入 dataset_id 以便保存历史
    result["dataset_id"] = body.dataset_id

    # 3. 保存查询历史
    history = None
    try:
        history = await nl2sql_service.save_query_history(
            db=db,
            user_id=current_user.id,
            prompt=body.prompt,
            result=result,
        )
    except Exception:
        # 历史保存失败不影响主流程
        pass

    response_data = NLQueryResponse(
        prompt=body.prompt,
        generated_sql=result.get("sql", ""),
        chart_type=result.get("chart_type", "table"),
        confidence=result.get("confidence", 0) / 100.0,  # 转换为 0-1 浮点数
        suggested_chart_type=result.get("chart_type"),
    )

    extra = {
        "explanation": result.get("explanation", ""),
        "is_valid": result.get("is_valid", False),
        "validation_message": result.get("validation_message", ""),
        "execution_time_ms": result.get("execution_time_ms", 0),
        "history_id": history.id if history else None,
    }

    return success_response(
        data={
            **response_data.model_dump(),
            **extra,
        },
        message="SQL 生成成功" if result.get("is_valid") else "SQL 生成完成但校验未通过",
    )


# ============================================================================
# 10. NL 查询历史
# ============================================================================

@router.get("/nl-history", summary="NL查询历史")
async def get_nl_query_history(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取当前用户的 NL2SQL 查询历史，按创建时间倒序排列。
    """
    total, items = await nl2sql_service.get_query_history(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )

    data = [
        {
            "id": h.id,
            "user_id": h.user_id,
            "dataset_id": h.dataset_id,
            "prompt": h.prompt,
            "generated_sql": h.generated_sql,
            "chart_type": h.chart_type,
            "is_valid": h.is_valid,
            "feedback": h.feedback,
            "error_message": h.error_message,
            "execution_time_ms": h.execution_time_ms,
            "row_count": h.row_count,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in items
    ]
    return paginated_response(data, total, page, page_size)


# ============================================================================
# 11. NL 查询反馈
# ============================================================================

@router.post("/nl-feedback/{history_id}", summary="提交NL查询反馈")
async def submit_nl_feedback(
    history_id: str,
    body: dict = Body(..., description="反馈内容: {\"feedback\": \"positive|negative|neutral\"}"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    对某次 NL2SQL 查询结果提交用户反馈。

    feedback 取值:
        - positive: 生成的 SQL / 图表类型符合预期
        - negative: 结果不理想
        - neutral: 中性评价
    """
    feedback = body.get("feedback", "").strip().lower()
    if feedback not in ("positive", "negative", "neutral"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feedback 必须是 positive / negative / neutral 之一",
        )

    ok = await nl2sql_service.submit_feedback(db, history_id, feedback)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="查询历史记录不存在",
        )

    return success_response(message="反馈提交成功")


# ============================================================================
# 12. 克隆图表
# ============================================================================

@router.post("/{chart_id}/clone", summary="克隆图表", status_code=201)
async def clone_chart(
    chart_id: str,
    body: dict = Body(default={"name": None}, description="可选: {\"name\": \"副本名称\"}"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(_get_current_user_id),
):
    """
    基于现有图表创建一个副本（克隆）。

    会复制原图表的所有配置（config、style_config、query_config、chart_type 等），
    仅 name 可覆盖（默认在原名称后追加 " - 副本"）。
    """
    original = await chart_service.get_chart(db, chart_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原图表不存在",
        )

    new_name = body.get("name") if body and body.get("name") else f"{original.name} - 副本"

    clone_data = ChartCreate(
        name=new_name,
        description=original.description,
        chart_type=original.chart_type,
        dataset_id=original.dataset_id,
        config=original.config,
        style_config=original.style_config,
        query_config=original.query_config,
        category=original.category,
    )

    chart = await chart_service.create_chart(db, data=clone_data, user_id=user_id)

    return success_response(
        data=_chart_to_response_dict(chart),
        message="图表克隆成功",
        code=201,
    )
