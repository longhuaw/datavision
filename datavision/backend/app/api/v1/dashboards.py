"""
看板管理 API - 拖拽布局设计器

核心功能:
- 看板 CRUD（列表、创建、详情、更新、软删除）
- 看板组件管理（添加、更新、删除、重排）
- 看板发布 / 取消发布
- 看板组件数据聚合查询
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.dependencies import get_db, get_redis, PaginationParams
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    DashboardResponse,
    ComponentCreate,
    ComponentUpdate,
    ComponentResponse,
    DashboardPublishRequest,
)
from app.services import dashboard_service
from app.utils.response import success_response, paginated_response, error_response

router = APIRouter(prefix="/dashboards", tags=["看板管理"])


# ============================================================================
# 辅助函数
# ============================================================================

def _dashboard_to_response_dict(dashboard, components: list = None) -> dict:
    """将 Dashboard ORM 对象转换为 DashboardResponse 兼容的字典。

    组件列表可通过 dashboard._components 自动获取，也可显式传入。
    """
    if components is None:
        components = getattr(dashboard, "_components", [])

    comps = [
        {
            "id": c.id,
            "chart_id": c.chart_id,
            "chart_name": c.chart_name,
            "chart_type": c.chart_type,
            "position": c.position,
            "z_index": c.z_index,
            "config": c.config,
            "sort_order": c.sort_order,
        }
        for c in components
    ]

    return {
        "id": dashboard.id,
        "title": dashboard.title,
        "description": dashboard.description,
        "theme": dashboard.theme,
        "width": dashboard.width,
        "height": dashboard.height,
        "background": dashboard.background,
        "is_published": dashboard.is_published,
        "publish_url": dashboard.publish_url,
        "password_protected": dashboard.password_protected,
        "refresh_interval": dashboard.refresh_interval,
        "category": dashboard.category,
        "tags": dashboard.tags,
        "components": comps,
        "created_by": dashboard.created_by,
        "created_at": dashboard.created_at.isoformat() if dashboard.created_at else None,
        "updated_at": dashboard.updated_at.isoformat() if dashboard.updated_at else None,
    }


def _component_to_response_dict(component) -> dict:
    """将 DashboardComponent ORM 对象转换为 ComponentResponse 兼容的字典。"""
    return {
        "id": component.id,
        "chart_id": component.chart_id,
        "chart_name": component.chart_name,
        "chart_type": component.chart_type,
        "position": component.position,
        "z_index": component.z_index,
        "config": component.config,
        "sort_order": component.sort_order,
    }


# ============================================================================
# 1. 看板列表
# ============================================================================

@router.get("/", summary="看板列表")
async def list_dashboards(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    category: str = Query(default=None, description="按分类过滤"),
    is_published: bool = Query(default=None, description="按发布状态过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """分页获取看板列表，支持按 category / is_published 过滤。"""
    total, dashboards = await dashboard_service.list_dashboards(
        db,
        page=page,
        page_size=page_size,
        category=category,
        is_published=is_published,
    )
    data = [_dashboard_to_response_dict(d) for d in dashboards]
    return paginated_response(data, total, page, page_size)


# ============================================================================
# 2. 创建看板
# ============================================================================

@router.post("/", summary="创建看板", status_code=201)
async def create_dashboard(
    body: DashboardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建新的看板。"""
    dashboard = await dashboard_service.create_dashboard(
        db, data=body, user_id=current_user.id
    )
    return success_response(
        data=_dashboard_to_response_dict(dashboard),
        message="看板创建成功",
        code=201,
    )


# ============================================================================
# 3. 获取看板详情
# ============================================================================

@router.get("/{dashboard_id}", summary="获取看板详情")
async def get_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """根据 ID 获取单个看板的完整信息（含所有组件）。"""
    dashboard = await dashboard_service.get_dashboard(db, dashboard_id)
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="看板不存在",
        )

    components = getattr(dashboard, "_components", [])
    return success_response(data=_dashboard_to_response_dict(dashboard, components))


# ============================================================================
# 4. 更新看板信息
# ============================================================================

@router.put("/{dashboard_id}", summary="更新看板信息")
async def update_dashboard(
    dashboard_id: str,
    body: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """部分更新看板配置（仅更新提供的字段）。"""
    dashboard = await dashboard_service.update_dashboard(db, dashboard_id, data=body)
    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="看板不存在",
        )
    return success_response(
        data=_dashboard_to_response_dict(dashboard),
        message="看板更新成功",
    )


# ============================================================================
# 5. 软删除看板
# ============================================================================

@router.delete("/{dashboard_id}", summary="删除看板")
async def delete_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """软删除看板（标记 is_deleted，不删除关联组件）。"""
    ok = await dashboard_service.delete_dashboard(db, dashboard_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="看板不存在",
        )
    return success_response(message="看板已删除")


# ============================================================================
# 6. 添加组件
# ============================================================================

@router.post("/{dashboard_id}/components", summary="添加组件", status_code=201)
async def add_component(
    dashboard_id: str,
    body: ComponentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """向看板添加一个布局组件（图表卡片）。"""
    try:
        component = await dashboard_service.add_component(db, dashboard_id, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return success_response(
        data=_component_to_response_dict(component),
        message="组件添加成功",
        code=201,
    )


# ============================================================================
# 7. 更新组件
# ============================================================================

@router.put("/{dashboard_id}/components/{comp_id}", summary="更新组件")
async def update_component(
    dashboard_id: str,
    comp_id: str,
    body: ComponentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """更新组件配置（位置、层级、配置等）。"""
    component = await dashboard_service.update_component(db, comp_id, data=body)
    if not component:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组件不存在",
        )
    return success_response(
        data=_component_to_response_dict(component),
        message="组件更新成功",
    )


# ============================================================================
# 8. 删除组件
# ============================================================================

@router.delete("/{dashboard_id}/components/{comp_id}", summary="删除组件")
async def remove_component(
    dashboard_id: str,
    comp_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """从看板中物理删除一个组件。"""
    ok = await dashboard_service.remove_component(db, comp_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组件不存在",
        )
    return success_response(message="组件已删除")


# ============================================================================
# 9. 重排组件顺序
# ============================================================================

@router.put("/{dashboard_id}/components/reorder", summary="重排组件顺序")
async def reorder_components(
    dashboard_id: str,
    body: list[str],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """批量重排组件顺序。

    请求体为组件 ID 列表，按期望的显示顺序排列。
    列表中组件的 sort_order 将被依次赋值为 0, 1, 2, ...
    """
    if not isinstance(body, list) or not all(isinstance(x, str) for x in body):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体必须是组件ID字符串列表",
        )

    try:
        await dashboard_service.reorder_components(db, dashboard_id, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return success_response(message="组件排序已更新")


# ============================================================================
# 10. 发布看板
# ============================================================================

@router.post("/{dashboard_id}/publish", summary="发布看板")
async def publish_dashboard(
    dashboard_id: str,
    body: DashboardPublishRequest = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """发布看板，生成唯一的 publish_url 用于外部访问。

    可选设置访问密码和过期时间。
    返回 publish_url 和访问 token。
    """
    publish_data = None
    if body is not None:
        publish_data = body.model_dump(exclude_none=True)

    try:
        result = await dashboard_service.publish_dashboard(db, dashboard_id, publish_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return success_response(
        data={
            "publish_url": result.get("publish_url"),
            "token": result.get("token"),
        },
        message="看板已发布",
    )


# ============================================================================
# 11. 取消发布看板
# ============================================================================

@router.post("/{dashboard_id}/unpublish", summary="取消发布看板")
async def unpublish_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """取消发布看板，清除 publish_url 和密码保护设置。"""
    try:
        await dashboard_service.unpublish_dashboard(db, dashboard_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return success_response(message="看板已取消发布")


# ============================================================================
# 12. 获取看板组件数据
# ============================================================================

@router.get("/{dashboard_id}/data", summary="获取看板组件数据")
async def get_dashboard_data(
    dashboard_id: str,
    force_refresh: bool = Query(default=False, description="是否强制刷新所有组件缓存"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: User = Depends(get_current_active_user),
):
    """获取看板中所有图表组件的实际数据。

    并行查询所有组件的图表数据，支持 Redis 缓存。
    返回列表，每个元素包含 component_id、chart_id、chart_type 和 data。
    """
    from app.core.cache_manager import CacheManager

    cache = CacheManager(redis)

    try:
        results = await dashboard_service.get_dashboard_components_data_parallel(
            db=db,
            dashboard_id=dashboard_id,
            cache_manager=cache,
            force_refresh=force_refresh,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return success_response(data=results)
