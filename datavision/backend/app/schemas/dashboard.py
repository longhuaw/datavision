"""看板相关 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DashboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256, description="看板标题")
    description: Optional[str] = Field(default=None, max_length=1024)
    theme: str = Field(default="default", description="主题")
    width: int = Field(default=1920, ge=800, le=7680)
    height: int = Field(default=1080, ge=600, le=4320)
    background: Optional[str] = None
    refresh_interval: int = Field(default=60, ge=10, le=3600)
    category: Optional[str] = None
    tags: Optional[list[str]] = None


class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    background: Optional[str] = None
    refresh_interval: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None


class ComponentCreate(BaseModel):
    chart_id: str
    position: dict = Field(description="位置: {x, y, w, h}")
    z_index: int = Field(default=0)
    config: Optional[dict] = None
    sort_order: int = Field(default=0)


class ComponentUpdate(BaseModel):
    position: Optional[dict] = None
    z_index: Optional[int] = None
    config: Optional[dict] = None
    sort_order: Optional[int] = None


class ComponentResponse(BaseModel):
    id: str
    chart_id: str
    chart_name: Optional[str] = None
    chart_type: Optional[str] = None
    position: dict
    z_index: int = 0
    config: Optional[dict] = None
    sort_order: int = 0
    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    theme: str = "default"
    width: int = 1920
    height: int = 1080
    background: Optional[str] = None
    is_published: bool = False
    publish_url: Optional[str] = None
    password_protected: bool = False
    refresh_interval: int = 60
    category: Optional[str] = None
    tags: Optional[list] = None
    components: list[ComponentResponse] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class DashboardPublishRequest(BaseModel):
    password: Optional[str] = None
    expires_at: Optional[str] = None
