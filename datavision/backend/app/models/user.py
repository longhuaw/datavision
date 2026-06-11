"""
用户、角色、审计日志模型
"""
from sqlalchemy import Column, String, Boolean, JSON, Text, DateTime, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, Base, UUIDMixin, TimestampMixin


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    username = Column(String(64), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")
    email = Column(String(128), unique=True, nullable=True, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    avatar = Column(String(512), nullable=True, comment="头像URL")
    nickname = Column(String(64), nullable=True, comment="昵称")
    role = Column(String(32), default="user", nullable=False, index=True, comment="角色: admin/editor/viewer/user")
    status = Column(String(16), default="active", nullable=False, comment="状态: active/disabled/pending")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(64), nullable=True, comment="最后登录IP")

    def __repr__(self):
        return f"<User {self.username}>"


class Role(BaseModel):
    """角色表"""
    __tablename__ = "roles"

    name = Column(String(64), unique=True, nullable=False, comment="角色名称")
    code = Column(String(32), unique=True, nullable=False, comment="角色编码")
    description = Column(String(256), nullable=True, comment="角色描述")
    permissions = Column(JSON, nullable=True, comment="权限配置JSON")

    def __repr__(self):
        return f"<Role {self.name}>"


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """操作审计日志"""
    __tablename__ = "audit_logs"

    user_id = Column(String(32), nullable=True, index=True, comment="操作用户ID")
    username = Column(String(64), nullable=True, comment="操作用户名")
    action = Column(String(64), nullable=False, index=True, comment="操作类型: create/update/delete/login/logout")
    resource_type = Column(String(32), nullable=False, comment="资源类型: datasource/dataset/chart/dashboard/user")
    resource_id = Column(String(32), nullable=True, comment="资源ID")
    resource_name = Column(String(128), nullable=True, comment="资源名称")
    detail = Column(JSON, nullable=True, comment="操作详情JSON")
    ip_address = Column(String(64), nullable=True, comment="请求IP")
    user_agent = Column(String(512), nullable=True, comment="User-Agent")
    status = Column(String(16), default="success", comment="操作状态: success/failure")

    def __repr__(self):
        return f"<AuditLog {self.action} {self.resource_type}>"
