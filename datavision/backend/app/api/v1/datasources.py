"""
数据源管理 API — CRUD、连接测试、元数据同步、表/列查询
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import get_current_active_user
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    MetadataSyncResponse,
    TableInfo,
    ColumnInfo,
)
from app.services import datasource_service
from app.utils.response import success_response, paginated_response

# 路由前缀由 main.py 通过 include_router(prefix=...) 统一添加，此处留空
router = APIRouter(prefix="/datasources", tags=["数据源"])


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _ds_to_response_dict(ds) -> dict:
    """将 DataSource ORM 对象转换为 DataSourceResponse 兼容的字典。"""
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "type": ds.type,
        "config": ds.config,
        "status": ds.status,
        "version": ds.version,
        "created_by": ds.created_by,
        "tags": ds.tags,
        "icon": ds.icon,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


# ── 列表 ────────────────────────────────────────────────────────────────────────

@router.get("/", summary="数据源列表")
async def list_datasources(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    type: str = Query(default=None, alias="type", description="按类型过滤"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """分页获取数据源列表，支持按类型（mysql/postgresql/...）过滤。"""
    total, items = await datasource_service.list_datasources(
        db, page=page, page_size=page_size, type_filter=type
    )
    data = [_ds_to_response_dict(d) for d in items]
    return paginated_response(data, total, page, page_size)


# ── 创建 ────────────────────────────────────────────────────────────────────────

@router.post("/", summary="创建数据源", status_code=201)
async def create_datasource(
    body: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """创建新的数据源连接配置。"""
    ds = await datasource_service.create_datasource(
        db,
        data=body.model_dump(),
        user_id=current_user.id,
    )
    return success_response(
        data=_ds_to_response_dict(ds),
        message="数据源创建成功",
        code=201,
    )


# ── 详情 ────────────────────────────────────────────────────────────────────────

@router.get("/{ds_id}", summary="获取数据源详情")
async def get_datasource(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """根据 ID 获取单个数据源的完整信息。"""
    ds = await datasource_service.get_datasource(db, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return success_response(data=_ds_to_response_dict(ds))


# ── 更新 ────────────────────────────────────────────────────────────────────────

@router.put("/{ds_id}", summary="更新数据源")
async def update_datasource(
    ds_id: str,
    body: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """全量或部分更新数据源配置。"""
    # 只传递显式设置的字段（exclude_unset）
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何需要更新的字段",
        )
    ds = await datasource_service.update_datasource(db, ds_id, update_data)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return success_response(
        data=_ds_to_response_dict(ds),
        message="数据源更新成功",
    )


# ── 删除（软删除）───────────────────────────────────────────────────────────────

@router.delete("/{ds_id}", summary="删除数据源")
async def delete_datasource(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """软删除数据源（标记 is_deleted，设置为 disabled 状态）。"""
    ok = await datasource_service.delete_datasource(db, ds_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据源不存在",
        )
    return success_response(message="数据源已删除")


# ── 连接测试 ────────────────────────────────────────────────────────────────────

@router.post("/test", summary="测试数据源连接")
async def test_connection(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    测试数据源连接是否可用。

    支持两种传参方式：
    1. 传入数据源 ID:  ``{"ds_id": "..."}``
    2. 直接传入配置:   ``{"type": "mysql", "config": {...}}``
    """
    ds_id = payload.get("ds_id")
    ds_type = payload.get("type")
    ds_config = payload.get("config")

    if ds_id:
        ds_id_or_config = ds_id
    elif ds_type and ds_config:
        ds_id_or_config = {"type": ds_type, "config": ds_config}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供 ds_id 或 (type + config) 以测试连接",
        )

    result = await datasource_service.test_connection(db, ds_id_or_config)
    return success_response(data=result)


# ── 元数据同步 ──────────────────────────────────────────────────────────────────

@router.post("/{ds_id}/sync-metadata", summary="同步元数据")
async def sync_metadata(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    触发指定数据源的元数据同步。

    连接数据源 → 采集所有表及列信息 → 存入 datasource_metadata 缓存表。
    """
    try:
        meta = await datasource_service.sync_metadata(db, ds_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    tables = []
    if meta.tables_info:
        for t in meta.tables_info:
            columns = [
                ColumnInfo(
                    name=c.get("name", "?"),
                    type=c.get("type", "unknown"),
                    nullable=c.get("nullable", True),
                    primary_key=c.get("primary_key", False),
                    comment=c.get("comment"),
                )
                for c in t.get("columns", [])
            ]
            tables.append(
                TableInfo(
                    table_name=t.get("table_name", "?"),
                    columns=columns,
                )
            )

    response = MetadataSyncResponse(
        datasource_id=ds_id,
        tables=tables,
        sync_status=meta.sync_status or "unknown",
        last_sync_at=meta.last_sync_at.isoformat() if meta.last_sync_at else None,
    )
    return success_response(data=response.model_dump())


# ── 表列表（缓存）───────────────────────────────────────────────────────────────

@router.get("/{ds_id}/tables", summary="获取数据源表列表")
async def get_tables(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    从缓存的元数据中获取该数据源下的所有表名。
    需要先执行元数据同步（POST /{ds_id}/sync-metadata）。
    """
    tables = await datasource_service.get_tables(ds_id, db)
    return success_response(data=tables)


# ── 表列信息（缓存）─────────────────────────────────────────────────────────────

@router.get("/{ds_id}/tables/{table_name}/columns", summary="获取表列信息")
async def get_table_columns(
    ds_id: str,
    table_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    从缓存的元数据中获取指定表的列信息。
    需要先执行元数据同步（POST /{ds_id}/sync-metadata）。
    """
    columns = await datasource_service.get_table_columns(ds_id, table_name, db)
    return success_response(data=columns)
