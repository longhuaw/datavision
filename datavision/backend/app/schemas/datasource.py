"""数据源相关 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="数据源名称")
    description: Optional[str] = Field(default=None, max_length=512)
    type: str = Field(description="数据源类型: mysql/postgresql/clickhouse/sqlite/mssql/api/excel")
    config: dict = Field(description="连接配置")
    tags: Optional[list[str]] = Field(default=None)
    icon: Optional[str] = Field(default=None)


class DataSourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    config: Optional[dict] = Field(default=None)
    status: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)


class DataSourceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    type: str
    config: dict
    status: str
    version: int
    created_by: Optional[str] = None
    tags: Optional[list] = None
    icon: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ConnectionTestRequest(BaseModel):
    type: str = Field(description="数据源类型")
    config: dict = Field(description="连接配置")


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    tables: list = Field(default_factory=list)


class ColumnInfo(BaseModel):
    """单列元数据"""
    name: str = Field(description="列名")
    type: str = Field(description="数据类型")
    nullable: bool = Field(default=False, description="是否可为空")
    primary_key: bool = Field(default=False, description="是否主键")
    comment: Optional[str] = Field(default=None, description="列注释")
    model_config = ConfigDict(from_attributes=True)


class TableInfo(BaseModel):
    """表元数据，包含列信息"""
    table_name: str = Field(description="表名")
    columns: list[ColumnInfo] = Field(default_factory=list, description="列信息列表")
    model_config = ConfigDict(from_attributes=True)


class MetadataSyncResponse(BaseModel):
    """元数据同步响应"""
    datasource_id: str = Field(description="数据源 ID")
    tables: list[TableInfo] = Field(default_factory=list, description="同步到的表列表")
    sync_status: str = Field(description="同步状态: pending/syncing/success/failed")
    last_sync_at: Optional[str] = Field(default=None, description="最后同步时间")
    model_config = ConfigDict(from_attributes=True)
