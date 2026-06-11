"""
数据集模型 - 基于数据源创建的虚拟表/视图
"""
from sqlalchemy import Column, String, JSON, Integer, Text, Boolean
from app.models.base import BaseModel, Base, UUIDMixin, TimestampMixin


class Dataset(BaseModel):
    """数据集表"""
    __tablename__ = "datasets"

    name = Column(String(128), nullable=False, comment="数据集名称")
    description = Column(String(512), nullable=True, comment="描述")
    datasource_id = Column(String(32), nullable=False, index=True, comment="关联数据源ID")
    datasource_name = Column(String(128), nullable=True, comment="数据源名称(冗余)")
    sql_text = Column(Text, nullable=True, comment="自定义SQL查询语句")
    schema_info = Column(JSON, nullable=True, comment="""
        字段Schema信息:
        [{"name":"id","type":"int","alias":"ID","is_dimension":true,"is_metric":false}]
    """)
    config = Column(JSON, nullable=True, comment="""
        数据集配置:
        {"mode":"sql","tables":["orders","users"],"joins":[],"aggregations":[]}
    """)
    cache_ttl = Column(Integer, default=300, comment="缓存过期时间(秒), 0=不缓存")
    row_count = Column(Integer, nullable=True, comment="预估行数")
    status = Column(String(16), default="draft", comment="状态: draft/published/archived")
    created_by = Column(String(32), nullable=True, comment="创建人ID")
    category = Column(String(64), nullable=True, comment="分类标签")
    tags = Column(JSON, nullable=True, comment="标签列表")

    def __repr__(self):
        return f"<Dataset {self.name}>"


class DatasetColumn(Base, UUIDMixin, TimestampMixin):
    """数据集字段配置表 - 每个字段的展示和行为配置"""
    __tablename__ = "dataset_columns"

    dataset_id = Column(String(32), nullable=False, index=True, comment="关联数据集ID")
    column_name = Column(String(128), nullable=False, comment="原始字段名")
    alias = Column(String(128), nullable=True, comment="字段别名(显示名)")
    data_type = Column(String(32), nullable=False, comment="数据类型: string/int/float/date/datetime/boolean")
    is_virtual = Column(Boolean, default=False, comment="是否为虚拟计算字段")
    virtual_expr = Column(Text, nullable=True, comment="虚拟字段的SQL表达式")
    is_dimension = Column(Boolean, default=False, comment="是否为维度(用于分组/筛选)")
    is_metric = Column(Boolean, default=False, comment="是否为度量(用于聚合计算)")
    default_aggregation = Column(String(16), nullable=True, comment="默认聚合方式: sum/count/avg/max/min/distinct")
    format_config = Column(JSON, nullable=True, comment="""
        格式化配置: {"prefix":"¥","suffix":"","decimal_places":2,"thousand_separator":true}
    """)
    semantic_type = Column(String(32), nullable=True, comment="语义类型: geo/city/currency/percentage/url/image")
    sort_order = Column(Integer, default=0, comment="排序顺序")

    def __repr__(self):
        return f"<DatasetColumn {self.column_name} [{self.data_type}]>"
