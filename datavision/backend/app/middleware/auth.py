"""
JWT 认证中间件 - 提供路由保护依赖

提供:
- get_current_user()          — 从 JWT Bearer token 解析当前用户 (401 if missing/invalid)
- get_current_active_user()   — 验证用户状态为 active (403 if disabled)
- get_admin_user()            — 验证用户角色为 admin (403 if not admin)
- get_optional_user()         — 可选认证，未提供 token 时返回 None，不抛出异常
"""
from fastapi import Header, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt

from app.config import settings
from app.dependencies import get_db


async def get_current_user(
    authorization: str = Header(None, description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
):
    """
    从 JWT Token 中提取当前用户信息
    - 验证 Token 有效性
    - 从数据库加载用户
    - 返回 User 对象
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "缺少认证令牌"},
        )

    # 解析 Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "认证格式错误，应为 Bearer <token>"},
        )

    token = parts[1]

    # 解码 JWT
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": 401, "message": "令牌无效"},
            )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": f"令牌验证失败: {str(e)}"},
        )

    # 从数据库加载用户
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 401, "message": "用户不存在或已被删除"},
        )

    return user


async def get_current_active_user(
    current_user=Depends(get_current_user),
):
    """要求用户状态为 active"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 403, "message": "用户账户已被禁用"},
        )
    return current_user


async def get_admin_user(
    current_user=Depends(get_current_active_user),
):
    """要求用户角色为 admin"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 403, "message": "需要管理员权限"},
        )
    return current_user


async def get_optional_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    可选认证：如果提供了有效的 Bearer token 则返回用户，否则返回 None。
    用于既支持匿名访问又支持登录用户的接口。
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        return None

    return user
