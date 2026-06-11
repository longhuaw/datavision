"""
图表模型 - 图表配置、缓存、NL查询历史
"""
from sqlalchemy import Column, String, JSON, Integer, DateTime, Text, Boolean
from app.models.base import BaseModel, Base, UUIDMixin, TimestampMixin


class Chart(BaseModel):
    """图表配置表"""
    __tablename__ = "charts"

    name = Column(String(128), nullable=False, comment="图表名称")
    description = Column(String(512), nullable=True, comment="描述")
    chart_type = Column(
        String(32), nullable=False, index=True,
        comment="图表类型: line/bar/pie/scatter/heatmap/funnel/radar/sankey/map/table/gauge/treemap/wordcloud"
    )
    dataset_id = Column(String(32), nullable=False, index=True, comment="关联数据集ID")
    dataset_name = Column(String(128), nullable=True, comment="数据集名称(冗余)")

    # 图表配置：维度和度量
    config = Column(JSON, nullable=True, comment="""
        图表配置JSON:
        {
          "dimensions": [{"field":"category","alias":"品类","order":0}],
          "metrics": [{"field":"amount","aggregation":"sum","alias":"销售额","order":0}],
          "filters": [{"field":"date","operator":">=","value":"2024-01-01"}],
          "order_by": [{"field":"amount","direction":"desc"}],
          "limit": 100
        }
    """)

    # 样式配置
    style_config = Column(JSON, nullable=True, comment="""
        样式配置JSON:
        {
          "title": {"text":"销售额趋势","show":true,"fontSize":16},
          "colors": ["#1890ff","#52c41a","#faad14","#f5222d"],
          "legend": {"show":true,"position":"bottom"},
          "tooltip": {"show":true},
          "animation": {"enabled":true,"duration":1000},
          "theme": "default"
        }
    """)

    # 查询配置
    query_config = Column(JSON, nullable=True, comment="""
        查询配置: {"refresh_interval":60,"cache_enabled":true,"max_rows":10000}
    """)

    # NL2SQL 核心字段
    nl_prompt = Column(Text, nullable=True, comment="NL2SQL的原始自然语言输入")
    generated_sql = Column(Text, nullable=True, comment="NL2SQL生成的SQL语句")
    nl_confidence = Column(Integer, nullable=True, comment="NL2SQL置信度 0-100")

    thumbnail_url = Column(String(512), nullable=True, comment="缩略图URL")
    created_by = Column(String(32), nullable=True, comment="创建人ID")
    version = Column(Integer, default=1, comment="版本号")
    is_template = Column(Boolean, default=False, comment="是否为模板")
    category = Column(String(64), nullable=True, comment="分类标签")
    usage_count = Column(Integer, default=0, comment="使用次数")

    def __repr__(self):
        return f"<Chart {self.name} [{self.chart_type}]>"


class ChartCache(Base, UUIDMixin):
    """图表数据缓存表"""
    __tablename__ = "chart_cache"

    chart_id = Column(String(32), nullable=False, unique=True, index=True, comment="关联图表ID")
    data = Column(JSON, nullable=True, comment="缓存的图表数据JSON")
    cached_at = Column(DateTime, nullable=True, comment="缓存时间")
    ttl = Column(Integer, default=300, comment="缓存有效期(秒)")
    data_hash = Column(String(64), nullable=True, comment="数据哈希, 用于判断是否需要刷新")

    def __repr__(self):
        return f"<ChartCache chart_id={self.chart_id}>"


class NLQueryHistory(Base, UUIDMixin, TimestampMixin):
    """NL查询历史表 - 记录每次自然语言查询"""
    __tablename__ = "nl_query_history"

    user_id = Column(String(32), nullable=True, index=True, comment="用户ID")
    dataset_id = Column(String(32), nullable=True, comment="数据集ID")
    prompt = Column(Text, nullable=False, comment="用户输入的自然语言")
    generated_sql = Column(Text, nullable=True, comment="生成的SQL")
    chart_type = Column(String(32), nullable=True, comment="生成的图表类型")
    is_valid = Column(Boolean, nullable=True, comment="SQL是否有效")
    feedback = Column(String(16), nullable=True, comment="用户反馈: positive/negative/neutral")
    error_message = Column(Text, nullable=True, comment="错误信息")
    execution_time_ms = Column(Integer, nullable=True, comment="执行耗时(毫秒)")
    row_count = Column(Integer, nullable=True, comment="返回行数")

    def __repr__(self):
        return f"<NLQueryHistory {self.prompt[:30]}>"
