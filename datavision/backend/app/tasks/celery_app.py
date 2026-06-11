"""
Celery 应用配置 - 异步任务队列
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "datavision",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.scheduled_tasks"],
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 分钟超时
    task_soft_time_limit=540,  # 9 分钟软超时
    worker_max_tasks_per_child=500,
    worker_prefetch_multiplier=4,
    beat_schedule={},
)
