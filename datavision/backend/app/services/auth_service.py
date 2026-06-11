"""
认证服务 - 用户登录、注册、令牌管理
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from jose import jwt

from app.config import settings
from app.models.user import User
from app.utils.encrypt import hash_password, verify_password


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """验证用户凭据，成功返回 User，失败返回 None"""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_user(db: AsyncSession, username: str, password: str, email: str = None, nickname: str = None) -> User:
    """创建新用户"""
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        nickname=nickname or username,
        role="user",
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def create_access_token(user_id: str, username: str, role: str) -> str:
    """创建 JWT 访问令牌"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, username: str) -> str:
    """创建 JWT 刷新令牌"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 JWT 令牌，返回 payload"""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def change_password(db: AsyncSession, user_id: str, old_password: str, new_password: str) -> bool:
    """修改用户密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    if not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    await db.commit()
    return True


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """根据 ID 获取用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """根据用户名获取用户"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, page: int = 1, page_size: int = 20, username: str = None, role: str = None) -> tuple[int, list[User]]:
    """分页获取用户列表"""
    query = select(User).where(User.is_deleted == False)
    count_query = select(func.count()).select_from(User).where(User.is_deleted == False)

    if username:
        query = query.where(User.username.contains(username))
        count_query = count_query.where(User.username.contains(username))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    return total, users
