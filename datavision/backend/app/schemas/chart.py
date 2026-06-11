"""图表相关 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ChartCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="图表名称")
    description: Optional[str] = None
    chart_type: str = Field(description="图表类型")
    dataset_id: str = Field(description="关联数据集ID")
    config: Optional[dict] = Field(default=None, description="图表配置(维度/度量/过滤)")
    style_config: Optional[dict] = Field(default=None, description="样式配置")
    query_config: Optional[dict] = Field(default=None, description="查询配置")
    nl_prompt: Optional[str] = Field(default=None, description="NL2SQL自然语言输入")
    category: Optional[str] = None


class ChartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    chart_type: Optional[str] = None
    config: Optional[dict] = None
    style_config: Optional[dict] = None
    query_config: Optional[dict] = None
    category: Optional[str] = None


class ChartResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    chart_type: str
    dataset_id: str
    dataset_name: Optional[str] = None
    config: Optional[dict] = None
    style_config: Optional[dict] = None
    query_config: Optional[dict] = None
    nl_prompt: Optional[str] = None
    generated_sql: Optional[str] = None
    nl_confidence: Optional[int] = None
    thumbnail_url: Optional[str] = None
    version: int = 1
    is_template: bool = False
    category: Optional[str] = None
    usage_count: int = 0
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NLQueryRequest(BaseModel):
    prompt: str = Field(min_length=1, description="自然语言查询描述")
    dataset_id: Optional[str] = Field(default=None, description="数据集ID(可选)")
    chart_type: Optional[str] = Field(default=None, description="指定图表类型(可选)")


class NLQueryResponse(BaseModel):
    prompt: str
    generated_sql: str
    chart_type: str
    confidence: float
    suggested_chart_type: Optional[str] = None


class ChartDataResponse(BaseModel):
    chart_id: str
    data: dict
    cached: bool = False
    execution_time_ms: int = 0
