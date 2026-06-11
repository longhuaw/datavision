"""
数据源模型 - 支持多种外部数据源接入
"""
from sqlalchemy import Column, String, JSON, Integer, DateTime, Text
from app.models.base import BaseModel, Base, UUIDMixin, TimestampMixin


class DataSource(BaseModel):
    """数据源配置表"""
    __tablename__ = "datasources"

    name = Column(String(128), nullable=False, comment="数据源名称")
    description = Column(String(512), nullable=True, comment="描述")
    type = Column(
        String(32), nullable=False, index=True,
        comment="数据源类型: mysql/postgresql/clickhouse/sqlite/mssql/api/excel"
    )
    config = Column(JSON, nullable=False, comment="""
        连接配置JSON:
        MySQL: {"host":"","port":3306,"database":"","username":"","password":"","charset":"utf8mb4"}
        PostgreSQL: {"host":"","port":5432,"database":"","username":"","password":"","schema":"public"}
        API: {"base_url":"","method":"GET","headers":{},"auth_type":"bearer","auth_config":{}}
        Excel: {"file_path":"","sheet_name":""}
    """)
    status = Column(String(16), default="active", index=True, comment="状态: active/error/disabled")
    version = Column(Integer, default=1, comment="配置版本号")
    created_by = Column(String(32), nullable=True, comment="创建人ID")
    icon = Column(String(64), nullable=True, comment="图标")
    tags = Column(JSON, nullable=True, comment="标签列表")

    def __repr__(self):
        return f"<DataSource {self.name} [{self.type}]>"


class DataSourceMetadata(Base, UUIDMixin, TimestampMixin):
    """数据源元数据缓存表 - 缓存采集到的表结构信息"""
    __tablename__ = "datasource_metadata"

    datasource_id = Column(String(32), nullable=False, unique=True, index=True, comment="关联数据源ID")
    tables_info = Column(JSON, nullable=True, comment="""
        表结构信息JSON:
        [
          {
            "table_name": "orders",
            "columns": [
              {"name":"id","type":"int","nullable":false,"primary_key":true,"comment":"订单ID"},
              {"name":"amount","type":"decimal(10,2)","nullable":false,"comment":"金额"}
            ],
            "row_count_estimate": 100000
          }
        ]
    """)
    last_sync_at = Column(DateTime, nullable=True, comment="最后一次同步时间")
    sync_status = Column(String(16), default="pending", comment="同步状态: pending/syncing/success/failed")
    sync_error = Column(Text, nullable=True, comment="同步错误信息")

    def __repr__(self):
        return f"<DataSourceMetadata ds_id={self.datasource_id}>"
