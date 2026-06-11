"""
定时任务定义 - 数据刷新、截图推送等
"""
import logging
from datetime import datetime, timezone
from celery.utils.log import get_task_logger
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(name="refresh_chart_cache")
def refresh_chart_cache(chart_id: str):
    """刷新指定图表的数据缓存"""
    logger.info(f"刷新图表缓存: {chart_id}")
    # 由 scheduler_service 触发时调用


@celery_app.task(name="refresh_dataset_cache")
def refresh_dataset_cache(dataset_id: str):
    """刷新数据集缓存"""
    logger.info(f"刷新数据集缓存: {dataset_id}")


@celery_app.task(name="execute_scheduled_push")
def execute_scheduled_push(push_id: str):
    """执行定时推送任务"""
    logger.info(f"执行定时推送: {push_id}")
    # 实际推送逻辑由 publish_service 实现


@celery_app.task(name="sync_datasource_metadata")
def sync_datasource_metadata(datasource_id: str):
    """定时同步数据源元数据"""
    logger.info(f"同步数据源元数据: {datasource_id}")


@celery_app.task(name="cleanup_expired_shares")
def cleanup_expired_shares():
    """清理过期的分享记录"""
    logger.info("清理过期分享记录")


@celery_app.task(name="health_check_datasources")
def health_check_datasources():
    """定时检查所有数据源的健康状态"""
    logger.info("检查数据源健康状态")
