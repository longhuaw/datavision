"""
用户管理 API — 管理员专用接口

提供：
- GET    /            — 分页列出用户（支持 username/role/status 过滤）
- GET    /{user_id}   — 用户详情
- POST   /            — 管理员创建用户
- PUT    /{user_id}   — 更新用户信息（email, nickname, role, status）
- DELETE /{user_id}   — 软删除用户
- PUT    /{user_id}/reset-password — 管理员重置用户密码
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.auth import get_admin_user
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services import auth_service
from app.utils.encrypt import hash_password
from app.utils.response import error_response, paginated_response, success_response

router = APIRouter(prefix="/users")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _user_to_dict(u: User) -> dict:
    """将 User ORM 对象转换为 API 响应字典"""
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "nickname": u.nickname,
        "avatar": u.avatar,
        "role": u.role,
        "status": u.status,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@router.get("/", summary="用户列表（管理员）")
async def list_users(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，最大 100"),
    username: str = Query(default=None, description="按用户名模糊搜索"),
    role: str = Query(default=None, description="按角色筛选: admin / editor / viewer / user"),
    status: str = Query(default=None, description="按状态筛选: active / disabled / pending"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员查看所有用户，支持分页和多条件过滤"""

    # 构建基础查询（排除软删除用户）
    query = select(User).where(User.is_deleted == False)
    count_query = select(func.count()).select_from(User).where(User.is_deleted == False)

    if username:
        query = query.where(User.username.contains(username))
        count_query = count_query.where(User.username.contains(username))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
        count_query = count_query.where(User.status == status)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    items = [_user_to_dict(u) for u in users]
    return paginated_response(items, total, page, page_size)


@router.get("/{user_id}", summary="用户详情（管理员）")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员查看指定用户的详细信息"""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在或已被删除",
        )
    return success_response(data=_user_to_dict(user))


@router.post("/", summary="创建用户（管理员）")
async def create_user(
    request: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员创建新用户，可指定角色和初始状态"""
    # 检查用户名是否已存在（包括已软删除用户）
    existing = await db.execute(
        select(User).where(User.username == request.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在，请更换后重试",
        )

    user = await auth_service.create_user(
        db,
        request.username,
        request.password,
        email=request.email,
        nickname=request.nickname,
    )

    return success_response(
        data={
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        message="用户创建成功",
    )


@router.put("/{user_id}", summary="更新用户信息（管理员）")
async def update_user(
    user_id: str,
    request: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员更新用户的 email、nickname、role、status 等信息"""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在或已被删除",
        )

    # 按需更新字段
    if request.email is not None:
        # 检查邮箱是否被其他用户占用
        if request.email != user.email:
            email_check = await db.execute(
                select(User).where(
                    User.email == request.email,
                    User.id != user_id,
                )
            )
            if email_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="该邮箱已被其他用户使用",
                )
            user.email = request.email

    if request.nickname is not None:
        user.nickname = request.nickname
    if request.avatar is not None:
        user.avatar = request.avatar
    if request.role is not None:
        valid_roles = {"admin", "editor", "viewer", "user"}
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的角色，可选值为: {', '.join(sorted(valid_roles))}",
            )
        user.role = request.role
    if request.status is not None:
        valid_statuses = {"active", "disabled", "pending"}
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的状态，可选值为: {', '.join(sorted(valid_statuses))}",
            )
        user.status = request.status

    await db.commit()
    await db.refresh(user)

    return success_response(data=_user_to_dict(user), message="用户信息更新成功")


@router.delete("/{user_id}", summary="软删除用户（管理员）")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员软删除用户 — 标记 is_deleted 和时间戳，不物理删除数据"""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在或已被删除",
        )

    # 禁止删除自己
    if user.id == _admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号",
        )

    # 执行软删除
    user.is_deleted = True
    user.deleted_at = datetime.now()
    await db.commit()

    return success_response(message=f"用户 {user.username} 已被删除")


@router.put("/{user_id}/reset-password", summary="重置用户密码（管理员）")
async def reset_password(
    user_id: str,
    new_password: str = Query(..., min_length=6, max_length=128, description="新密码"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """管理员重置指定用户的密码，无需提供原密码"""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在或已被删除",
        )

    user.password_hash = hash_password(new_password)
    await db.commit()

    return success_response(message=f"用户 {user.username} 的密码已重置")
