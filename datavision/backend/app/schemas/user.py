"""
用户认证相关 Pydantic 模型
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class UserCreate(BaseModel):
    """创建用户 / 注册"""
    username: str = Field(min_length=3, max_length=32, description="用户名")
    password: str = Field(min_length=6, max_length=128, description="密码")
    email: Optional[str] = Field(default=None, max_length=128, description="邮箱")
    nickname: Optional[str] = Field(default=None, max_length=64, description="昵称")


class UserLogin(BaseModel):
    """用户登录"""
    username: str = Field(min_length=1, description="用户名")
    password: str = Field(min_length=1, description="密码")


class UserUpdate(BaseModel):
    """更新用户信息"""
    email: Optional[str] = Field(default=None, max_length=128)
    nickname: Optional[str] = Field(default=None, max_length=64)
    avatar: Optional[str] = Field(default=None, max_length=512)
    status: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    status: str
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
