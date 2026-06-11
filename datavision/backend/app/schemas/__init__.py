"""
DataVision Pydantic Schemas - 请求/响应数据校验模型

统一导出所有 schema 类，方便其他模块引用:
    from app.schemas import UserCreate, ChartResponse, DashboardCreate, ...
"""

from app.schemas.common import (
    APIResponse,
    PaginatedData,
    ErrorResponse,
    HealthCheckResponse,
)

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
)

from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    ColumnInfo,
    TableInfo,
    MetadataSyncResponse,
)

from app.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
)

from app.schemas.chart import (
    ChartCreate,
    ChartUpdate,
    ChartResponse,
    NLQueryRequest,
    NLQueryResponse,
    ChartDataResponse,
)

from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    DashboardResponse,
    ComponentCreate,
    ComponentUpdate,
    ComponentResponse,
    DashboardPublishRequest,
)


__all__ = [
    # Common
    "APIResponse",
    "PaginatedData",
    "ErrorResponse",
    "HealthCheckResponse",
    # User / Auth
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "TokenResponse",
    "RefreshTokenRequest",
    "ChangePasswordRequest",
    # Datasource
    "DataSourceCreate",
    "DataSourceUpdate",
    "DataSourceResponse",
    "ConnectionTestRequest",
    "ConnectionTestResponse",
    "ColumnInfo",
    "TableInfo",
    "MetadataSyncResponse",
    # Dataset
    "DatasetCreate",
    "DatasetUpdate",
    "DatasetResponse",
    "DatasetPreviewResponse",
    # Chart
    "ChartCreate",
    "ChartUpdate",
    "ChartResponse",
    "NLQueryRequest",
    "NLQueryResponse",
    "ChartDataResponse",
    # Dashboard
    "DashboardCreate",
    "DashboardUpdate",
    "DashboardResponse",
    "ComponentCreate",
    "ComponentUpdate",
    "ComponentResponse",
    "DashboardPublishRequest",
]
