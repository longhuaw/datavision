"""
认证 API 路由 - 登录、注册、登出、令牌刷新、个人信息管理
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from app.services import auth_service
from app.middleware.auth import get_current_user, get_current_active_user
from app.utils.response import success_response

router = APIRouter(prefix="/auth")


@router.post("/login", summary="用户登录", response_model=dict)
async def login(request: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录，验证凭据并返回访问令牌与刷新令牌"""
    user = await auth_service.authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用，请联系管理员",
        )

    # 记录登录时间
    user.last_login_at = datetime.now()

    # 生成令牌
    access_token = auth_service.create_access_token(user.id, user.username, user.role)
    refresh_token = auth_service.create_refresh_token(user.id, user.username)

    await db.commit()

    return success_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 60 * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
                "avatar": user.avatar,
                "role": user.role,
                "status": user.status,
            },
        }
    )


@router.post("/register", summary="用户注册", response_model=dict)
async def register(request: UserCreate, db: AsyncSession = Depends(get_db)):
    """注册新用户账号"""
    existing = await auth_service.get_user_by_username(db, request.username)
    if existing:
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
        },
        message="注册成功",
    )


@router.post("/logout", summary="用户登出", response_model=dict)
async def logout(
    current_user=Depends(get_current_active_user),
):
    """登出当前用户，客户端应丢弃本地存储的令牌"""
    # 服务端无状态的 JWT 登出通过客户端丢弃令牌实现
    # 若需令牌黑名单，可在此处将当前令牌加入 Redis 黑名单
    return success_response(
        message="已成功登出，请清除本地令牌",
    )


@router.post("/refresh", summary="刷新令牌", response_model=dict)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用刷新令牌获取新的访问令牌与刷新令牌"""
    try:
        payload = auth_service.decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型错误，请使用刷新令牌",
            )

        user_id = payload.get("sub")
        username = payload.get("username")
        user = await auth_service.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被删除",
            )

        new_access = auth_service.create_access_token(user.id, user.username, user.role)
        new_refresh = auth_service.create_refresh_token(user.id, user.username)

        return success_response(
            data={
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "bearer",
                "expires_in": 60 * 60,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"刷新令牌无效: {str(e)}",
        )


@router.get("/me", summary="获取当前用户信息", response_model=dict)
async def get_me(current_user=Depends(get_current_active_user)):
    """获取当前登录用户的详细信息"""
    return success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "nickname": current_user.nickname,
            "email": current_user.email,
            "avatar": current_user.avatar,
            "role": current_user.role,
            "status": current_user.status,
            "last_login_at": (
                current_user.last_login_at.isoformat()
                if current_user.last_login_at
                else None
            ),
            "created_at": (
                current_user.created_at.isoformat()
                if current_user.created_at
                else None
            ),
        }
    )


@router.put("/me/password", summary="修改密码", response_model=dict)
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前登录用户的密码，需要提供原密码进行验证"""
    success = await auth_service.change_password(
        db,
        current_user.id,
        request.old_password,
        request.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误，请重试",
        )
    return success_response(message="密码修改成功")
