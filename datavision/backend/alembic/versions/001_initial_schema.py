"""初始数据库架构

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import CHAR

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== 用户与权限 ====================
    op.create_table(
        'users',
        sa.Column('id', CHAR(32), primary_key=True, comment='主键ID'),
        sa.Column('username', sa.String(64), unique=True, nullable=False, index=True, comment='用户名'),
        sa.Column('password_hash', sa.String(256), nullable=False, comment='密码哈希'),
        sa.Column('email', sa.String(128), unique=True, nullable=True, comment='邮箱'),
        sa.Column('phone', sa.String(20), nullable=True, comment='手机号'),
        sa.Column('avatar', sa.String(512), nullable=True, comment='头像URL'),
        sa.Column('nickname', sa.String(64), nullable=True, comment='昵称'),
        sa.Column('role', sa.String(32), nullable=False, default='user', index=True, comment='角色'),
        sa.Column('status', sa.String(16), nullable=False, default='active', comment='状态'),
        sa.Column('last_login_at', sa.DateTime, nullable=True, comment='最后登录时间'),
        sa.Column('last_login_ip', sa.String(64), nullable=True, comment='最后登录IP'),
        sa.Column('is_deleted', sa.Boolean, default=False, comment='是否已删除'),
        sa.Column('deleted_at', sa.DateTime, nullable=True, comment='删除时间'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), comment='更新时间'),
    )

    op.create_table(
        'roles',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('name', sa.String(64), unique=True, nullable=False, comment='角色名称'),
        sa.Column('code', sa.String(32), unique=True, nullable=False, comment='角色编码'),
        sa.Column('description', sa.String(256), nullable=True, comment='角色描述'),
        sa.Column('permissions', sa.JSON, nullable=True, comment='权限配置'),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('user_id', sa.String(32), nullable=True, index=True, comment='用户ID'),
        sa.Column('username', sa.String(64), nullable=True, comment='用户名'),
        sa.Column('action', sa.String(64), nullable=False, index=True, comment='操作类型'),
        sa.Column('resource_type', sa.String(32), nullable=False, comment='资源类型'),
        sa.Column('resource_id', sa.String(32), nullable=True, comment='资源ID'),
        sa.Column('resource_name', sa.String(128), nullable=True, comment='资源名称'),
        sa.Column('detail', sa.JSON, nullable=True, comment='操作详情'),
        sa.Column('ip_address', sa.String(64), nullable=True, comment='请求IP'),
        sa.Column('user_agent', sa.String(512), nullable=True, comment='User-Agent'),
        sa.Column('status', sa.String(16), default='success', comment='操作状态'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ==================== 数据源 ====================
    op.create_table(
        'datasources',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False, comment='数据源名称'),
        sa.Column('description', sa.String(512), nullable=True, comment='描述'),
        sa.Column('type', sa.String(32), nullable=False, index=True, comment='数据源类型'),
        sa.Column('config', sa.JSON, nullable=False, comment='连接配置'),
        sa.Column('status', sa.String(16), default='active', index=True, comment='状态'),
        sa.Column('version', sa.Integer, default=1, comment='版本号'),
        sa.Column('created_by', sa.String(32), nullable=True, comment='创建人ID'),
        sa.Column('icon', sa.String(64), nullable=True, comment='图标'),
        sa.Column('tags', sa.JSON, nullable=True, comment='标签'),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'datasource_metadata',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('datasource_id', sa.String(32), nullable=False, unique=True, index=True),
        sa.Column('tables_info', sa.JSON, nullable=True, comment='表结构信息'),
        sa.Column('last_sync_at', sa.DateTime, nullable=True, comment='最后同步时间'),
        sa.Column('sync_status', sa.String(16), default='pending', comment='同步状态'),
        sa.Column('sync_error', sa.Text, nullable=True, comment='同步错误'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ==================== 数据集 ====================
    op.create_table(
        'datasets',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False, comment='数据集名称'),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('datasource_id', sa.String(32), nullable=False, index=True),
        sa.Column('datasource_name', sa.String(128), nullable=True),
        sa.Column('sql_text', sa.Text, nullable=True, comment='自定义SQL'),
        sa.Column('schema_info', sa.JSON, nullable=True, comment='字段Schema'),
        sa.Column('config', sa.JSON, nullable=True, comment='配置'),
        sa.Column('cache_ttl', sa.Integer, default=300, comment='缓存TTL(秒)'),
        sa.Column('row_count', sa.Integer, nullable=True, comment='预估行数'),
        sa.Column('status', sa.String(16), default='draft'),
        sa.Column('created_by', sa.String(32), nullable=True),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('tags', sa.JSON, nullable=True),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'dataset_columns',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('dataset_id', sa.String(32), nullable=False, index=True),
        sa.Column('column_name', sa.String(128), nullable=False),
        sa.Column('alias', sa.String(128), nullable=True),
        sa.Column('data_type', sa.String(32), nullable=False),
        sa.Column('is_virtual', sa.Boolean, default=False),
        sa.Column('virtual_expr', sa.Text, nullable=True),
        sa.Column('is_dimension', sa.Boolean, default=False),
        sa.Column('is_metric', sa.Boolean, default=False),
        sa.Column('default_aggregation', sa.String(16), nullable=True),
        sa.Column('format_config', sa.JSON, nullable=True),
        sa.Column('semantic_type', sa.String(32), nullable=True),
        sa.Column('sort_order', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ==================== 图表 ====================
    op.create_table(
        'charts',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('chart_type', sa.String(32), nullable=False, index=True),
        sa.Column('dataset_id', sa.String(32), nullable=False, index=True),
        sa.Column('dataset_name', sa.String(128), nullable=True),
        sa.Column('config', sa.JSON, nullable=True, comment='图表配置(维度/度量)'),
        sa.Column('style_config', sa.JSON, nullable=True, comment='样式配置'),
        sa.Column('query_config', sa.JSON, nullable=True, comment='查询配置'),
        sa.Column('nl_prompt', sa.Text, nullable=True, comment='NL2SQL输入'),
        sa.Column('generated_sql', sa.Text, nullable=True, comment='生成的SQL'),
        sa.Column('nl_confidence', sa.Integer, nullable=True, comment='NL置信度'),
        sa.Column('thumbnail_url', sa.String(512), nullable=True),
        sa.Column('created_by', sa.String(32), nullable=True),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('is_template', sa.Boolean, default=False),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('usage_count', sa.Integer, default=0),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'chart_cache',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('chart_id', sa.String(32), nullable=False, unique=True, index=True),
        sa.Column('data', sa.JSON, nullable=True),
        sa.Column('cached_at', sa.DateTime, nullable=True),
        sa.Column('ttl', sa.Integer, default=300),
        sa.Column('data_hash', sa.String(64), nullable=True),
    )

    op.create_table(
        'nl_query_history',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('user_id', sa.String(32), nullable=True, index=True),
        sa.Column('dataset_id', sa.String(32), nullable=True),
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('generated_sql', sa.Text, nullable=True),
        sa.Column('chart_type', sa.String(32), nullable=True),
        sa.Column('is_valid', sa.Boolean, nullable=True),
        sa.Column('feedback', sa.String(16), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=True),
        sa.Column('row_count', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # ==================== 看板 ====================
    op.create_table(
        'dashboards',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('description', sa.String(1024), nullable=True),
        sa.Column('theme', sa.String(32), default='default'),
        sa.Column('width', sa.Integer, default=1920),
        sa.Column('height', sa.Integer, default=1080),
        sa.Column('background', sa.String(512), nullable=True),
        sa.Column('is_published', sa.Boolean, default=False),
        sa.Column('publish_url', sa.String(128), nullable=True, unique=True),
        sa.Column('password_protected', sa.Boolean, default=False),
        sa.Column('password_hash', sa.String(256), nullable=True),
        sa.Column('refresh_interval', sa.Integer, default=60),
        sa.Column('created_by', sa.String(32), nullable=True),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('tags', sa.JSON, nullable=True),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'dashboard_components',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('dashboard_id', sa.String(32), nullable=False, index=True),
        sa.Column('chart_id', sa.String(32), nullable=False, index=True),
        sa.Column('chart_name', sa.String(128), nullable=True),
        sa.Column('chart_type', sa.String(32), nullable=True),
        sa.Column('position', sa.JSON, nullable=False),
        sa.Column('z_index', sa.Integer, default=0),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('sort_order', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'share_records',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('dashboard_id', sa.String(32), nullable=False, index=True),
        sa.Column('shared_by', sa.String(32), nullable=False),
        sa.Column('share_type', sa.String(16), nullable=False),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('token', sa.String(128), nullable=True, unique=True),
        sa.Column('password_protected', sa.Boolean, default=False),
        sa.Column('password_hash', sa.String(256), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('last_accessed_at', sa.DateTime, nullable=True),
        sa.Column('access_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'scheduled_pushes',
        sa.Column('id', CHAR(32), primary_key=True),
        sa.Column('dashboard_id', sa.String(32), nullable=False, index=True),
        sa.Column('dashboard_name', sa.String(256), nullable=True),
        sa.Column('channel', sa.String(16), nullable=False),
        sa.Column('cron_expr', sa.String(64), nullable=False),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('last_run_at', sa.DateTime, nullable=True),
        sa.Column('last_status', sa.String(16), nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('created_by', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('scheduled_pushes')
    op.drop_table('share_records')
    op.drop_table('dashboard_components')
    op.drop_table('dashboards')
    op.drop_table('nl_query_history')
    op.drop_table('chart_cache')
    op.drop_table('charts')
    op.drop_table('dataset_columns')
    op.drop_table('datasets')
    op.drop_table('datasource_metadata')
    op.drop_table('datasources')
    op.drop_table('audit_logs')
    op.drop_table('roles')
    op.drop_table('users')
