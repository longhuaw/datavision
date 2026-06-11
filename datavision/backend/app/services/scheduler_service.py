"""
定时任务调度服务
"""
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger("datavision.scheduler")


async def get_pending_pushes(db: AsyncSession) -> list:
    """获取所有待执行的推送任务"""
    from app.models.dashboard import ScheduledPush
    result = await db.execute(
        select(ScheduledPush).where(ScheduledPush.enabled == True)
    )
    return list(result.scalars().all())


async def record_push_result(db: AsyncSession, push_id: str, success: bool, error: str = None):
    """记录推送执行结果"""
    from app.models.dashboard import ScheduledPush
    result = await db.execute(select(ScheduledPush).where(ScheduledPush.id == push_id))
    push = result.scalar_one_or_none()
    if push:
        push.last_run_at = datetime.now()
        push.last_status = "success" if success else "failed"
        if error:
            push.last_error = error
        await db.commit()
