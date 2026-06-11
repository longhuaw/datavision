"""
SQLAlchemy 基础模型 - 提供通用字段和工具方法
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


def gen_uuid():
    """生成不带横线的UUID"""
    return uuid.uuid4().hex


class TimestampMixin:
    """自动添加 created_at / updated_at 时间戳"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class UUIDMixin:
    """使用 32 位 UUID 作为主键"""
    id: Mapped[str] = mapped_column(
        CHAR(32), primary_key=True, default=gen_uuid, comment="主键ID"
    )


class SoftDeleteMixin:
    """软删除混入"""
    is_deleted: Mapped[bool] = mapped_column(
        default=False, comment="是否已删除"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="删除时间"
    )


class BaseModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    组合基类：UUID主键 + 时间戳 + 软删除
    所有业务模型继承此类
    """
    __abstract__ = True
