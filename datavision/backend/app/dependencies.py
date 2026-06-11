"""
FastAPI 依赖注入模块

提供:
- get_db()           — 异步 SQLAlchemy 会话
- get_current_user()         — 从 JWT 解析当前用户
- get_current_active_user()  — 验证用户为 active 状态
- get_admin_user()           — 验证用户为 admin 角色
- get_redis()                — 异步 Redis 连接
- PaginationParams           — 分页查询参数
"""

from typing import AsyncGenerator, Optional

import jwt
from fastapi import Depends, Header, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.user import User

# ---------------------------------------------------------------------------
# SQLAlchemy 异步引擎 & 会话工厂（模块级别单例）
# ---------------------------------------------------------------------------
_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

_AsyncSessionLocal = sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ==================== 数据库 ====================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """每个请求获取一个独立的异步数据库会话，请求结束后自动关闭。"""
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ==================== Redis ====================

async def get_redis() -> AsyncGenerator[Redis, None]:
    """每个请求获取一个 Redis 连接，请求结束后自动关闭。"""
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


# ==================== 用户认证 ====================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 Authorization 头提取 Bearer token，解码 JWT，查询并返回当前用户。

    未提供 token、token 无效、或用户不存在时均抛出 401。
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证格式错误，应为 Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌中缺少用户标识",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """验证当前用户状态为 active，否则抛出 403。"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用或待激活",
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """验证当前用户角色为 admin，否则抛出 403。"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


# ==================== 分页 ====================

class PaginationParams:
    """
    复用分页查询参数依赖。

    使用方式:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            offset = (pagination.page - 1) * pagination.page_size
            ...
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size
