"""
看板模型 - 看板、布局组件、分享、定时推送
"""
from sqlalchemy import Column, String, JSON, Integer, DateTime, Boolean, Text
from app.models.base import BaseModel, Base, UUIDMixin, TimestampMixin


class Dashboard(BaseModel):
    """看板表"""
    __tablename__ = "dashboards"

    title = Column(String(256), nullable=False, comment="看板标题")
    description = Column(String(1024), nullable=True, comment="描述")
    theme = Column(String(32), default="default", comment="主题: default/dark/tech_blue/business_green/midnight")
    width = Column(Integer, default=1920, comment="画布宽度(px)")
    height = Column(Integer, default=1080, comment="画布高度(px)")
    background = Column(String(512), nullable=True, comment="背景图或背景色")
    is_published = Column(Boolean, default=False, comment="是否已发布")
    publish_url = Column(String(128), nullable=True, unique=True, comment="发布URL标识")
    password_protected = Column(Boolean, default=False, comment="是否需要密码访问")
    password_hash = Column(String(256), nullable=True, comment="访问密码哈希")
    refresh_interval = Column(Integer, default=60, comment="全局刷新间隔(秒)")
    created_by = Column(String(32), nullable=True, comment="创建人ID")
    category = Column(String(64), nullable=True, comment="分类")
    tags = Column(JSON, nullable=True, comment="标签列表")
    config = Column(JSON, nullable=True, comment="""
        看板全局配置:
        {"show_header":true,"show_footer":false,"grid_snap":true,"grid_size":20}
    """)

    def __repr__(self):
        return f"<Dashboard {self.title}>"


class DashboardComponent(Base, UUIDMixin, TimestampMixin):
    """看板布局组件表 - 记录每个图表在看板上的位置和配置"""
    __tablename__ = "dashboard_components"

    dashboard_id = Column(String(32), nullable=False, index=True, comment="关联看板ID")
    chart_id = Column(String(32), nullable=False, index=True, comment="关联图表ID")
    chart_name = Column(String(128), nullable=True, comment="图表名称(冗余)")
    chart_type = Column(String(32), nullable=True, comment="图表类型(冗余)")

    # 位置和大小
    position = Column(JSON, nullable=False, comment="""
        布局位置: {"x":0,"y":0,"w":6,"h":4,"min_w":2,"min_h":2,"max_w":12,"max_h":10}
        基于12列栅格系统
    """)
    z_index = Column(Integer, default=0, comment="层级(z-index)")

    # 组件配置
    config = Column(JSON, nullable=True, comment="""
        组件联动配置:
        {
          "refresh_interval":30,
          "linkage": {
            "trigger_field":"category",
            "target_chart_ids":["chart_xxx"],
            "target_field":"category"
          },
          "show_title":true,
          "show_border":true
        }
    """)
    sort_order = Column(Integer, default=0, comment="排序顺序")

    def __repr__(self):
        return f"<DashboardComponent chart={self.chart_id} pos={self.position}>"


class ShareRecord(Base, UUIDMixin, TimestampMixin):
    """看板分享记录表"""
    __tablename__ = "share_records"

    dashboard_id = Column(String(32), nullable=False, index=True, comment="关联看板ID")
    shared_by = Column(String(32), nullable=False, comment="分享人ID")
    share_type = Column(String(16), nullable=False, comment="分享类型: link/embed")
    config = Column(JSON, nullable=True, comment="分享配置")
    token = Column(String(128), nullable=True, unique=True, comment="分享访问令牌")
    password_protected = Column(Boolean, default=False, comment="是否需要密码")
    password_hash = Column(String(256), nullable=True, comment="密码哈希")
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    last_accessed_at = Column(DateTime, nullable=True, comment="最后访问时间")
    access_count = Column(Integer, default=0, comment="访问次数")

    def __repr__(self):
        return f"<ShareRecord dashboard={self.dashboard_id} type={self.share_type}>"


class ScheduledPush(Base, UUIDMixin, TimestampMixin):
    """定时推送任务表"""
    __tablename__ = "scheduled_pushes"

    dashboard_id = Column(String(32), nullable=False, index=True, comment="关联看板ID")
    dashboard_name = Column(String(256), nullable=True, comment="看板名称(冗余)")
    channel = Column(String(16), nullable=False, comment="推送渠道: wechat/dingtalk/email/feishu/webhook")
    cron_expr = Column(String(64), nullable=False, comment="Cron表达式")
    config = Column(JSON, nullable=True, comment="""
        渠道配置:
        企业微信: {"webhook_url":"","msg_type":"markdown"}
        钉钉: {"webhook_url":"","secret":"","msg_type":"markdown"}
        邮件: {"recipients":[],"subject":"","body_template":""}
    """)
    enabled = Column(Boolean, default=True, comment="是否启用")
    last_run_at = Column(DateTime, nullable=True, comment="最后执行时间")
    last_status = Column(String(16), nullable=True, comment="最后执行状态: success/failed")
    last_error = Column(Text, nullable=True, comment="最后执行错误信息")
    created_by = Column(String(32), nullable=True, comment="创建人ID")

    def __repr__(self):
        return f"<ScheduledPush dashboard={self.dashboard_id} channel={self.channel}>"
