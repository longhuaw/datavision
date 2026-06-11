"""
数据集管理 API — CRUD、预览、SQL执行、字段导入与配置
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, PaginationParams
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
)
from app.services import dataset_service
from app.utils.response import success_response, paginated_response

router = APIRouter(prefix="/datasets", tags=["数据集"])


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _ds_to_response_dict(ds) -> dict:
    """将 Dataset ORM 对象转换为 DatasetResponse 兼容的字典。"""
    return {
        "id": ds.id,
        "name": ds.name,
        "description": ds.description,
        "datasource_id": ds.datasource_id,
        "datasource_name": ds.datasource_name,
        "sql_text": ds.sql_text,
        "schema_info": ds.schema_info,
        "config": ds.config,
        "cache_ttl": ds.cache_ttl,
        "row_count": ds.row_count,
        "status": ds.status,
        "category": ds.category,
        "tags": ds.tags,
        "created_by": ds.created_by,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


def _col_to_response_dict(col) -> dict:
    """将 DatasetColumn ORM 对象转换为字典。"""
    return {
        "id": col.id,
        "dataset_id": col.dataset_id,
        "column_name": col.column_name,
        "alias": col.alias,
        "data_type": col.data_type,
        "is_virtual": col.is_virtual,
        "virtual_expr": col.virtual_expr,
        "is_dimension": col.is_dimension,
        "is_metric": col.is_metric,
        "default_aggregation": col.default_aggregation,
        "format_config": col.format_config,
        "semantic_type": col.semantic_type,
        "sort_order": col.sort_order,
        "created_at": col.created_at.isoformat() if col.created_at else None,
        "updated_at": col.updated_at.isoformat() if col.updated_at else None,
    }


def _get_current_user_id(
    current_user: User = Depends(get_current_active_user),
) -> str:
    """返回当前用户 ID，用于创建数据集时记录 created_by。"""
    return current_user.id


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------

@router.get("/", summary="数据集列表")
async def list_datasets(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    datasource_id: str = Query(default=None, description="按数据源ID过滤"),
    status: str = Query(default=None, description="按状态过滤: draft/published/archived"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """分页获取数据集列表，支持按数据源ID和状态过滤。"""
    total, items = await dataset_service.list_datasets(
        db, page=page, page_size=page_size,
        datasource_id=datasource_id, status=status,
    )
    data = [_ds_to_response_dict(d) for d in items]
    return paginated_response(data, total, page, page_size)


# ---------------------------------------------------------------------------
# 创建
# ---------------------------------------------------------------------------

@router.post("/", summary="创建数据集", status_code=201)
async def create_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(_get_current_user_id),
):
    """创建新的数据集。"""
    ds = await dataset_service.create_dataset(
        db,
        data=body.model_dump(),
        user_id=user_id,
    )
    return success_response(
        data=_ds_to_response_dict(ds),
        message="数据集创建成功",
        code=201,
    )


# ---------------------------------------------------------------------------
# 详情
# ---------------------------------------------------------------------------

@router.get("/{ds_id}", summary="获取数据集详情")
async def get_dataset(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """根据 ID 获取单个数据集的完整信息。"""
    ds = await dataset_service.get_dataset(db, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在",
        )
    return success_response(data=_ds_to_response_dict(ds))


# ---------------------------------------------------------------------------
# 更新
# ---------------------------------------------------------------------------

@router.put("/{ds_id}", summary="更新数据集")
async def update_dataset(
    ds_id: str,
    body: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """部分更新数据集配置。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供任何需要更新的字段",
        )
    ds = await dataset_service.update_dataset(db, ds_id, update_data)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在",
        )
    return success_response(
        data=_ds_to_response_dict(ds),
        message="数据集更新成功",
    )


# ---------------------------------------------------------------------------
# 删除（软删除）
# ---------------------------------------------------------------------------

@router.delete("/{ds_id}", summary="删除数据集")
async def delete_dataset(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """软删除数据集（标记 is_deleted，设置为 archived 状态）。"""
    ok = await dataset_service.delete_dataset(db, ds_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在",
        )
    return success_response(message="数据集已删除")


# ---------------------------------------------------------------------------
# 数据预览
# ---------------------------------------------------------------------------

@router.get("/{ds_id}/preview", summary="预览数据集数据")
async def preview_dataset(
    ds_id: str,
    limit: int = Query(default=100, ge=1, le=10000, description="返回行数上限"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """执行数据集 SQL 查询并返回前 N 行数据预览。"""
    try:
        result = await dataset_service.preview_data(db, ds_id, limit=limit)
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

    preview = DatasetPreviewResponse(
        columns=result["columns"],
        rows=result["rows"],
        total_rows=result["total"],
        execution_time_ms=result["execution_time_ms"],
    )
    return success_response(data=preview.model_dump())


# ---------------------------------------------------------------------------
# 执行自定义 SQL
# ---------------------------------------------------------------------------

@router.post("/{ds_id}/execute", summary="执行自定义SQL")
async def execute_dataset_sql(
    ds_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    在数据集关联的数据源上执行自定义 SQL。

    请求体:
        {"sql": "SELECT * FROM orders WHERE status = 'pending'", "limit": 50}
    若不传 sql 字段，则使用数据集自身的 sql_text。
    """
    custom_sql = body.get("sql")
    limit = body.get("limit", 100)

    try:
        result = await dataset_service.execute_dataset_sql(
            db, ds_id, custom_sql=custom_sql, limit=limit
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

    return success_response(data={
        "columns": result["columns"],
        "rows": result["rows"],
    })


# ---------------------------------------------------------------------------
# 字段配置 - 列表
# ---------------------------------------------------------------------------

@router.get("/{ds_id}/columns", summary="获取数据集字段配置")
async def get_dataset_columns(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """获取数据集的字段配置列表，按 sort_order 排序。"""
    # 先确认数据集存在
    ds = await dataset_service.get_dataset(db, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在",
        )
    columns = await dataset_service.get_dataset_columns(db, ds_id)
    return success_response(data=[_col_to_response_dict(c) for c in columns])


# ---------------------------------------------------------------------------
# 字段配置 - 更新单个字段
# ---------------------------------------------------------------------------

@router.put("/{ds_id}/columns/{col_id}", summary="更新字段配置")
async def update_dataset_column(
    ds_id: str,
    col_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    更新单个字段的展示和行为配置。

    可更新字段：alias, data_type, is_virtual, virtual_expr,
    is_dimension, is_metric, default_aggregation, format_config,
    semantic_type, sort_order。
    """
    dcol = await dataset_service.update_dataset_column(db, col_id, body)
    if not dcol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="字段不存在",
        )
    return success_response(
        data=_col_to_response_dict(dcol),
        message="字段配置更新成功",
    )


# ---------------------------------------------------------------------------
# 自动导入字段
# ---------------------------------------------------------------------------

@router.post("/{ds_id}/import-columns", summary="自动导入字段")
async def import_dataset_columns(
    ds_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_active_user),
):
    """
    从数据集的 SQL 查询中自动检测字段名和类型，创建并返回字段配置列表。

    会先删除该数据集已有的所有字段配置，然后全量重建。
    同时更新数据集自身的 schema_info。
    """
    # 先确认数据集存在
    ds = await dataset_service.get_dataset(db, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在",
        )
    try:
        columns = await dataset_service.import_columns(db, ds_id)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return success_response(
        data=[_col_to_response_dict(c) for c in columns],
        message=f"字段导入完成，共 {len(columns)} 个字段",
    )
