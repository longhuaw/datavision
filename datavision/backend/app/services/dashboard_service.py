"""
看板服务 - 看板CRUD、组件管理、发布/取消发布、已发布访问
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.models.dashboard import Dashboard, DashboardComponent, ShareRecord
from app.models.chart import Chart
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    ComponentCreate,
    ComponentUpdate,
)
from app.utils.encrypt import generate_token, hash_password, verify_password

logger = logging.getLogger("datavision.dashboard_service")


# ---------------------------------------------------------------------------
# 看板 CRUD
# ---------------------------------------------------------------------------


async def create_dashboard(
    db: AsyncSession, data: DashboardCreate, user_id: Optional[str] = None
) -> Dashboard:
    """创建新看板"""
    dashboard = Dashboard(
        title=data.title,
        description=data.description,
        theme=data.theme,
        width=data.width,
        height=data.height,
        background=data.background,
        refresh_interval=data.refresh_interval,
        category=data.category,
        tags=data.tags,
        created_by=user_id,
    )
    db.add(dashboard)
    await db.commit()
    await db.refresh(dashboard)
    logger.info("看板已创建 id=%s title=%s", dashboard.id, dashboard.title)
    return dashboard


async def update_dashboard(
    db: AsyncSession, dashboard_id: str, data: DashboardUpdate
) -> Optional[Dashboard]:
    """更新看板配置，返回更新后的看板，不存在时返回 None"""
    dashboard = await _get_dashboard_optional(db, dashboard_id)
    if not dashboard:
        logger.warning("更新看板失败: dashboard_id=%s 不存在", dashboard_id)
        return None

    for field in (
        "title", "description", "theme", "width", "height",
        "background", "refresh_interval", "category", "tags",
    ):
        val = getattr(data, field, None)
        if val is not None:
            setattr(dashboard, field, val)

    await db.commit()
    await db.refresh(dashboard)
    logger.info("看板已更新 id=%s", dashboard.id)
    return dashboard


async def delete_dashboard(db: AsyncSession, dashboard_id: str) -> bool:
    """软删除看板（不同时删除组件，保留数据完整性）"""
    dashboard = await _get_dashboard_optional(db, dashboard_id)
    if not dashboard:
        return False

    dashboard.is_deleted = True
    dashboard.deleted_at = datetime.utcnow()
    await db.commit()
    logger.info("看板已软删除 id=%s", dashboard_id)
    return True


async def get_dashboard(db: AsyncSession, dashboard_id: str) -> Optional[Dashboard]:
    """根据 ID 获取单个看板（自动过滤已删除记录）

    组件通过 _components 属性附加：调用方在序列化时遍历 dashboard._components。
    """
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id, Dashboard.is_deleted == False
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        return None

    # 单独查询关联组件并附加到看板对象上
    comp_result = await db.execute(
        select(DashboardComponent)
        .where(DashboardComponent.dashboard_id == dashboard_id)
        .order_by(DashboardComponent.sort_order)
    )
    dashboard._components = list(comp_result.scalars().all())
    return dashboard


async def list_dashboards(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    is_published: Optional[bool] = None,
) -> tuple[int, list[Dashboard]]:
    """分页获取看板列表，支持按 category / is_published 过滤"""
    query = select(Dashboard).where(Dashboard.is_deleted == False)
    count_q = select(func.count()).select_from(Dashboard).where(Dashboard.is_deleted == False)

    if category is not None:
        query = query.where(Dashboard.category == category)
        count_q = count_q.where(Dashboard.category == category)

    if is_published is not None:
        query = query.where(Dashboard.is_published == is_published)
        count_q = count_q.where(Dashboard.is_published == is_published)

    # 获取总数
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.order_by(Dashboard.updated_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    dashboards = list(result.scalars().all())

    return total, dashboards


# ---------------------------------------------------------------------------
# 组件管理
# ---------------------------------------------------------------------------


async def add_component(
    db: AsyncSession, dashboard_id: str, component_data: ComponentCreate
) -> DashboardComponent:
    """向看板添加一个布局组件"""
    # 校验看板是否存在
    await _get_dashboard_or_raise(db, dashboard_id)

    component = DashboardComponent(
        dashboard_id=dashboard_id,
        chart_id=component_data.chart_id,
        position=component_data.position,
        z_index=component_data.z_index,
        config=component_data.config,
        sort_order=component_data.sort_order,
    )
    db.add(component)
    await db.commit()
    await db.refresh(component)
    logger.info(
        "组件已添加 id=%s dashboard_id=%s chart_id=%s",
        component.id, dashboard_id, component_data.chart_id,
    )
    return component


async def update_component(
    db: AsyncSession, component_id: str, data: ComponentUpdate
) -> Optional[DashboardComponent]:
    """更新组件配置，返回更新后的组件，不存在时返回 None"""
    component = await _get_component(db, component_id)
    if not component:
        logger.warning("更新组件失败: component_id=%s 不存在", component_id)
        return None

    for field in ("position", "z_index", "config", "sort_order"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(component, field, val)

    await db.commit()
    await db.refresh(component)
    logger.info("组件已更新 id=%s", component_id)
    return component


async def remove_component(db: AsyncSession, component_id: str) -> bool:
    """物理删除组件"""
    component = await _get_component(db, component_id)
    if not component:
        return False

    await db.delete(component)
    await db.commit()
    logger.info("组件已删除 id=%s", component_id)
    return True


async def update_component_position(
    db: AsyncSession, component_id: str, position: dict
) -> Optional[DashboardComponent]:
    """更新组件位置"""
    component = await _get_component(db, component_id)
    if not component:
        logger.warning("更新组件位置失败: component_id=%s 不存在", component_id)
        return None

    component.position = position
    await db.commit()
    await db.refresh(component)
    logger.info("组件位置已更新 id=%s pos=%s", component_id, position)
    return component


async def reorder_components(
    db: AsyncSession, dashboard_id: str, component_ids: list[str]
) -> bool:
    """批量重排组件顺序，按传入的 component_ids 顺序更新 sort_order"""
    # 校验看板存在
    await _get_dashboard_or_raise(db, dashboard_id)

    for idx, cid in enumerate(component_ids):
        await db.execute(
            update(DashboardComponent)
            .where(
                DashboardComponent.id == cid,
                DashboardComponent.dashboard_id == dashboard_id,
            )
            .values(sort_order=idx)
        )

    await db.commit()
    logger.info("组件已重排 dashboard_id=%s count=%d", dashboard_id, len(component_ids))
    return True


# ---------------------------------------------------------------------------
# 发布 / 取消发布
# ---------------------------------------------------------------------------


async def publish_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    publish_data: Optional[dict] = None,
) -> dict:
    """发布看板，生成唯一 publish_url，创建 ShareRecord

    返回 {"publish_url": str, "token": str}
    """
    dashboard = await _get_dashboard_or_raise(db, dashboard_id)

    password = publish_data.get("password") if publish_data else None
    expires_at = publish_data.get("expires_at") if publish_data else None

    # 生成唯一令牌
    token = generate_token(16)

    dashboard.is_published = True
    dashboard.publish_url = token

    if password:
        dashboard.password_protected = True
        dashboard.password_hash = hash_password(password)
    else:
        dashboard.password_protected = False
        dashboard.password_hash = None

    await db.commit()
    await db.refresh(dashboard)

    # 创建 ShareRecord
    share_record = ShareRecord(
        dashboard_id=dashboard_id,
        shared_by=dashboard.created_by or "",
        share_type="link",
        token=token,
        password_protected=bool(password),
        password_hash=hash_password(password) if password else None,
        expires_at=expires_at,
    )
    db.add(share_record)
    await db.commit()
    await db.refresh(share_record)

    logger.info(
        "看板已发布 id=%s token=%s password_protected=%s share_id=%s",
        dashboard_id, token, dashboard.password_protected, share_record.id,
    )

    return {"publish_url": token, "token": token}


async def unpublish_dashboard(db: AsyncSession, dashboard_id: str) -> bool:
    """取消发布看板"""
    dashboard = await _get_dashboard_or_raise(db, dashboard_id)

    dashboard.is_published = False
    dashboard.publish_url = None
    dashboard.password_protected = False
    dashboard.password_hash = None

    await db.commit()
    logger.info("看板已取消发布 id=%s", dashboard_id)
    return True


# ---------------------------------------------------------------------------
# 已发布看板访问
# ---------------------------------------------------------------------------


async def get_published_dashboard(
    db: AsyncSession,
    token_or_url: str,
    password: Optional[str] = None,
) -> dict:
    """通过 token 或 publish_url 获取已发布的看板及其组件。

    参数
    ----
    token_or_url : str
        发布令牌（同时匹配 Dashboard.publish_url 和 ShareRecord.token）
    password : str | None
        访问密码，当看板受密码保护时需要提供

    返回
    ----
    dict
        {"dashboard": Dashboard, "components": list[DashboardComponent]}

    异常
    ----
    ValueError
        看板不存在、未发布、已过期、密码错误
    """
    # 查找看板（通过 publish_url 匹配）
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.publish_url == token_or_url,
            Dashboard.is_deleted == False,
            Dashboard.is_published == True,
        )
    )
    dashboard = result.scalar_one_or_none()

    if not dashboard:
        raise ValueError("看板不存在或未发布")

    # 查找对应的 ShareRecord（通过 token 匹配）
    share_result = await db.execute(
        select(ShareRecord).where(
            ShareRecord.token == token_or_url,
        )
    )
    share_record = share_result.scalar_one_or_none()

    # 检查 ShareRecord 是否过期
    if share_record and share_record.expires_at:
        if share_record.expires_at < datetime.now(timezone.utc):
            raise ValueError("分享链接已过期")

    # 检查密码保护
    if dashboard.password_protected:
        if not password:
            raise ValueError("该看板需要密码访问")
        if not verify_password(password, dashboard.password_hash):
            raise ValueError("密码错误")

    # 也检查 ShareRecord 级别的密码
    if share_record and share_record.password_protected:
        if not password:
            raise ValueError("该分享需要密码访问")
        if not verify_password(password, share_record.password_hash):
            raise ValueError("密码错误")

    # 查询关联组件
    comp_result = await db.execute(
        select(DashboardComponent)
        .where(DashboardComponent.dashboard_id == dashboard.id)
        .order_by(DashboardComponent.sort_order)
    )
    components = list(comp_result.scalars().all())

    # 递增访问计数（在 ShareRecord 上）
    if share_record:
        share_record.access_count = (share_record.access_count or 0) + 1
        share_record.last_accessed_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info(
        "已发布看板被访问 dashboard_id=%s token=%s",
        dashboard.id, token_or_url,
    )

    return {"dashboard": dashboard, "components": components}


# ---------------------------------------------------------------------------
# 看板组件数据查询
# ---------------------------------------------------------------------------


async def get_dashboard_components_data(
    db: AsyncSession,
    dashboard_id: str,
) -> list[dict]:
    """获取看板中所有图表的数据（并行查询）。

    对看板中的每个 DashboardComponent，查询对应 Chart 的 chart_type，
    返回组件ID、图表类型和结构化的数据占位。

    返回
    ----
    list[dict]
        每个元素为 {"component_id": str, "chart_type": str, "data": {"columns": [...], "rows": [...]}}

    注意
    ----
    实际数据查询需要 chart_service.get_chart_data 配合 CacheManager。
    本函数返回结构化的数据占位，调用方负责注入 CacheManager 并实际执行查询。
    """
    # 校验看板存在
    await _get_dashboard_or_raise(db, dashboard_id)

    # 获取所有组件
    comp_result = await db.execute(
        select(DashboardComponent)
        .where(DashboardComponent.dashboard_id == dashboard_id)
        .order_by(DashboardComponent.sort_order)
    )
    components = list(comp_result.scalars().all())

    if not components:
        return []

    # 批量获取关联的图表信息
    chart_ids = [c.chart_id for c in components]
    chart_result = await db.execute(
        select(Chart).where(
            Chart.id.in_(chart_ids),
            Chart.is_deleted == False,
        )
    )
    charts_map = {c.id: c for c in chart_result.scalars().all()}

    # 构建返回数据（并行执行实际数据查询的入口点）
    # 每个组件返回 component_id + 数据占位结构
    # 调用方可以使用此列表并行调用 chart_service.get_chart_data
    results = []
    for component in components:
        chart = charts_map.get(component.chart_id)
        entry = {
            "component_id": component.id,
            "chart_id": component.chart_id,
            "chart_type": chart.chart_type if chart else component.chart_type,
            "data": {
                "columns": [],
                "rows": [],
                "_pending": True,  # 标记数据尚未实际加载
            },
        }
        results.append(entry)

    return results


async def get_dashboard_components_data_parallel(
    db: AsyncSession,
    dashboard_id: str,
    cache_manager=None,
    force_refresh: bool = False,
) -> list[dict]:
    """并行获取看板中所有图表的数据。

    与 get_dashboard_components_data 不同，本函数会实际执行 SQL 查询并
    返回真实数据。所有图表查询并行执行以提高性能。

    参数
    ----
    db : AsyncSession
        数据库会话
    dashboard_id : str
        看板 ID
    cache_manager : CacheManager | None
        Redis 缓存管理器
    force_refresh : bool
        是否强制刷新所有图表缓存

    返回
    ----
    list[dict]
        每个元素为 {"component_id": str, "chart_type": str, "data": {"columns": [...], "rows": [...]}}
    """
    # 延迟导入，避免循环依赖
    from app.services.chart_service import get_chart_data

    # 校验看板存在
    await _get_dashboard_or_raise(db, dashboard_id)

    # 获取所有组件
    comp_result = await db.execute(
        select(DashboardComponent)
        .where(DashboardComponent.dashboard_id == dashboard_id)
        .order_by(DashboardComponent.sort_order)
    )
    components = list(comp_result.scalars().all())

    if not components:
        return []

    # 并行获取所有图表数据
    async def fetch_chart_data(component: DashboardComponent) -> dict:
        try:
            chart_data = await get_chart_data(
                db=db,
                chart_id=component.chart_id,
                cache_manager=cache_manager,
                force_refresh=force_refresh,
            )
            return {
                "component_id": component.id,
                "chart_id": component.chart_id,
                "data": {
                    "columns": chart_data.get("columns", []),
                    "rows": chart_data.get("rows", []),
                },
            }
        except Exception as e:
            logger.error(
                "获取组件数据失败 component_id=%s chart_id=%s: %s",
                component.id, component.chart_id, e,
            )
            return {
                "component_id": component.id,
                "chart_id": component.chart_id,
                "data": {"columns": [], "rows": [], "error": str(e)},
            }

    # 使用 asyncio.gather 并行查询所有图表
    results = await asyncio.gather(*[fetch_chart_data(c) for c in components])
    return list(results)


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


async def _get_dashboard_or_raise(db: AsyncSession, dashboard_id: str) -> Dashboard:
    """获取看板（未删除），不存在时抛出 ValueError"""
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id, Dashboard.is_deleted == False
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise ValueError(f"看板不存在: {dashboard_id}")
    return dashboard


async def _get_dashboard_optional(db: AsyncSession, dashboard_id: str) -> Optional[Dashboard]:
    """获取看板（未删除），不存在时返回 None"""
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id, Dashboard.is_deleted == False
        )
    )
    return result.scalar_one_or_none()


async def _get_component(
    db: AsyncSession, component_id: str
) -> Optional[DashboardComponent]:
    """根据 ID 获取单个组件"""
    result = await db.execute(
        select(DashboardComponent).where(DashboardComponent.id == component_id)
    )
    return result.scalar_one_or_none()
