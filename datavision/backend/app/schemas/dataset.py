"""数据集相关 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    datasource_id: str = Field(description="关联数据源ID")
    sql_text: Optional[str] = Field(default=None, description="自定义SQL查询")
    config: Optional[dict] = Field(default=None)
    cache_ttl: int = Field(default=300, ge=0, description="缓存TTL(秒)")
    category: Optional[str] = Field(default=None, max_length=64)
    tags: Optional[list[str]] = Field(default=None)


class DatasetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    sql_text: Optional[str] = Field(default=None)
    config: Optional[dict] = Field(default=None)
    cache_ttl: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    datasource_id: str
    datasource_name: Optional[str] = None
    sql_text: Optional[str] = None
    schema_info: Optional[list] = None
    config: Optional[dict] = None
    cache_ttl: int = 300
    row_count: Optional[int] = None
    status: str = "draft"
    category: Optional[str] = None
    tags: Optional[list] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class DatasetPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    total_rows: int
    execution_time_ms: int
