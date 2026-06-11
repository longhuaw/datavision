"""
通用 Pydantic 模型 - 统一响应格式、分页
"""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="响应数据")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据"""
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    items: list[T] = Field(description="数据列表")


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int = Field(description="错误状态码")
    message: str = Field(description="错误信息")
    detail: Optional[str] = Field(default=None, description="详细信息")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(description="服务状态")
    service: str = Field(description="服务名称")
    version: str = Field(description="版本号")
    timestamp: str = Field(description="时间戳")
    checks: dict = Field(description="各组件健康状态")
