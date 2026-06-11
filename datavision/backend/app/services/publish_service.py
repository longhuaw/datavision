"""
发布分享服务 - 看板发布、分享链接、定时推送、截图生成
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.dashboard import Dashboard, ShareRecord, ScheduledPush
from app.utils.encrypt import generate_token, hash_password, verify_password

logger = logging.getLogger("datavision.publish")

# ---------------------------------------------------------------------------
# 分享链接管理
# ---------------------------------------------------------------------------


async def create_share_link(
    db: AsyncSession,
    dashboard_id: str,
    shared_by: str,
    config: Optional[dict] = None,
) -> ShareRecord:
    """创建分享链接

    config 可包含:
        - share_type: str  (默认 "link")  分享类型: link / embed
        - password: str | None  访问密码
        - expires_at: datetime | str | None  过期时间
        - allow_download: bool  是否允许下载
        - max_access: int | None  最大访问次数限制
    """
    config = config or {}

    share_type = config.get("share_type", "link")
    password = config.get("password")
    expires_at = config.get("expires_at")
    allow_download = config.get("allow_download", False)
    max_access = config.get("max_access")

    # 将 expires_at 字符串转换为 datetime
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)

    token = generate_token(16)

    record = ShareRecord(
        dashboard_id=dashboard_id,
        shared_by=shared_by,
        share_type=share_type,
        token=token,
        config={
            "allow_download": allow_download,
            "max_access": max_access,
        },
        password_protected=bool(password),
        password_hash=hash_password(password) if password else None,
        expires_at=expires_at,
    )
    db.add(record)

    # 更新看板发布状态
    result = await db.execute(
        select(Dashboard).where(Dashboard.id == dashboard_id)
    )
    dashboard = result.scalar_one_or_none()
    if dashboard:
        dashboard.is_published = True
        dashboard.publish_url = token

    await db.commit()
    await db.refresh(record)
    logger.info(
        "分享链接已创建 share_id=%s dashboard_id=%s shared_by=%s type=%s",
        record.id, dashboard_id, shared_by, share_type,
    )
    return record


async def revoke_share(db: AsyncSession, share_id: str) -> bool:
    """撤销分享链接（物理删除）"""
    result = await db.execute(
        select(ShareRecord).where(ShareRecord.id == share_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        logger.warning("撤销分享失败: share_id=%s 不存在", share_id)
        return False

    await db.delete(record)
    await db.commit()
    logger.info("分享已撤销 share_id=%s", share_id)
    return True


async def get_share_by_token(db: AsyncSession, token: str) -> Optional[ShareRecord]:
    """根据 token 获取分享记录"""
    result = await db.execute(
        select(ShareRecord).where(ShareRecord.token == token)
    )
    record = result.scalar_one_or_none()

    # 检查是否过期
    if record and record.expires_at:
        if record.expires_at.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
            return None

    return record


async def list_shares(db: AsyncSession, dashboard_id: str) -> list[ShareRecord]:
    """获取看板的所有分享记录"""
    result = await db.execute(
        select(ShareRecord)
        .where(ShareRecord.dashboard_id == dashboard_id)
        .order_by(ShareRecord.created_at.desc())
    )
    return list(result.scalars().all())


async def record_access(db: AsyncSession, share_id: str) -> None:
    """记录分享访问（递增 access_count，更新 last_accessed_at）"""
    result = await db.execute(
        select(ShareRecord).where(ShareRecord.id == share_id)
    )
    record = result.scalar_one_or_none()
    if record:
        record.access_count = (record.access_count or 0) + 1
        record.last_accessed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("分享访问记录已更新 share_id=%s count=%d", share_id, record.access_count)


async def verify_share_password(share: ShareRecord, password: str) -> bool:
    """验证分享密码"""
    if not share.password_protected or not share.password_hash:
        return True
    return verify_password(password, share.password_hash)


# ---------------------------------------------------------------------------
# 发布 / 取消发布看板
# ---------------------------------------------------------------------------


async def publish_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    password: Optional[str] = None,
) -> dict:
    """发布看板（简化版）

    返回 {"publish_url": str, "token": str}
    """
    token = generate_token(16)

    result = await db.execute(
        select(Dashboard).where(Dashboard.id == dashboard_id)
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise ValueError(f"看板不存在: {dashboard_id}")

    dashboard.is_published = True
    dashboard.publish_url = token
    if password:
        dashboard.password_protected = True
        dashboard.password_hash = hash_password(password)
    else:
        dashboard.password_protected = False
        dashboard.password_hash = None

    await db.commit()
    logger.info("看板已发布 dashboard_id=%s token=%s", dashboard_id, token)
    return {"publish_url": token, "token": token, "is_password_protected": bool(password)}


async def unpublish_dashboard(db: AsyncSession, dashboard_id: str) -> bool:
    """取消发布看板"""
    result = await db.execute(
        select(Dashboard).where(Dashboard.id == dashboard_id)
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        return False

    dashboard.is_published = False
    dashboard.publish_url = None
    dashboard.password_protected = False
    dashboard.password_hash = None

    await db.commit()
    logger.info("看板已取消发布 dashboard_id=%s", dashboard_id)
    return True


# ---------------------------------------------------------------------------
# 定时推送管理
# ---------------------------------------------------------------------------


async def create_scheduled_push(
    db: AsyncSession,
    dashboard_id: str,
    push_data: dict,
    user_id: str,
) -> ScheduledPush:
    """创建定时推送任务

    push_data 必须包含:
        - channel: str  推送渠道: webhook / dingtalk / wechat / feishu / email / callback
        - cron_expr: str  Cron 表达式
        - config: dict  渠道配置（webhook_url, msg_type, recipients 等）

    push_data 可选:
        - enabled: bool (默认 True)
        - dashboard_name: str  看板名称（冗余）
    """
    channel = push_data["channel"]
    cron_expr = push_data["cron_expr"]
    config = push_data.get("config", {})
    enabled = push_data.get("enabled", True)
    dashboard_name = push_data.get("dashboard_name")

    push = ScheduledPush(
        dashboard_id=dashboard_id,
        dashboard_name=dashboard_name,
        channel=channel,
        cron_expr=cron_expr,
        config=config,
        enabled=enabled,
        created_by=user_id,
    )
    db.add(push)
    await db.commit()
    await db.refresh(push)
    logger.info(
        "定时推送已创建 push_id=%s dashboard_id=%s channel=%s cron=%s",
        push.id, dashboard_id, channel, cron_expr,
    )
    return push


async def update_scheduled_push(
    db: AsyncSession,
    push_id: str,
    data: dict,
) -> Optional[ScheduledPush]:
    """更新定时推送配置"""
    result = await db.execute(
        select(ScheduledPush).where(ScheduledPush.id == push_id)
    )
    push = result.scalar_one_or_none()
    if not push:
        logger.warning("更新定时推送失败: push_id=%s 不存在", push_id)
        return None

    updatable_fields = ("channel", "cron_expr", "config", "enabled", "dashboard_name")
    for key in updatable_fields:
        if key in data and data[key] is not None:
            setattr(push, key, data[key])

    await db.commit()
    await db.refresh(push)
    logger.info("定时推送已更新 push_id=%s", push_id)
    return push


async def delete_scheduled_push(db: AsyncSession, push_id: str) -> bool:
    """删除定时推送任务（物理删除）"""
    result = await db.execute(
        select(ScheduledPush).where(ScheduledPush.id == push_id)
    )
    push = result.scalar_one_or_none()
    if not push:
        logger.warning("删除定时推送失败: push_id=%s 不存在", push_id)
        return False

    await db.delete(push)
    await db.commit()
    logger.info("定时推送已删除 push_id=%s", push_id)
    return True


async def list_scheduled_pushes(
    db: AsyncSession, dashboard_id: str
) -> list[ScheduledPush]:
    """获取看板的所有定时推送任务"""
    result = await db.execute(
        select(ScheduledPush)
        .where(ScheduledPush.dashboard_id == dashboard_id)
        .order_by(ScheduledPush.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# 推送执行
# ---------------------------------------------------------------------------


async def execute_push(db: AsyncSession, push_id: str) -> dict[str, Any]:
    """执行一次推送任务

    流程:
        1. 获取 ScheduledPush 记录并校验
        2. 生成看板截图（通过 generate_screenshot）
        3. 收集看板图表数据
        4. 发送到配置的渠道（webhook / callback）
        5. 更新 last_run_at 和 last_status

    返回:
        {"success": bool, "message": str}
    """
    result = await db.execute(
        select(ScheduledPush).where(ScheduledPush.id == push_id)
    )
    push = result.scalar_one_or_none()
    if not push:
        return {"success": False, "message": f"推送任务不存在: {push_id}"}

    try:
        # 1. 生成看板截图
        screenshot_url = await generate_screenshot(db, push.dashboard_id)

        # 2. 获取看板数据（懒加载，避免循环导入）
        from app.services.dashboard_service import get_dashboard_components_data_parallel
        components_data = await get_dashboard_components_data_parallel(
            db, push.dashboard_id
        )

        # 3. 构建推送载荷
        payload = {
            "dashboard_id": push.dashboard_id,
            "dashboard_name": push.dashboard_name or "",
            "screenshot_url": screenshot_url,
            "components": components_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "push_id": push_id,
        }

        # 4. 发送到配置的渠道
        channel = push.channel
        channel_config = push.config or {}

        if channel in ("webhook", "callback"):
            success, message = await _send_webhook(channel_config, payload)
        elif channel in ("dingtalk", "wechat", "feishu"):
            success, message = await _send_im_webhook(channel, channel_config, payload)
        elif channel == "email":
            success, message = await _send_email(channel_config, payload)
        else:
            success, message = False, f"不支持的推送渠道: {channel}"

        # 5. 更新执行记录
        push.last_run_at = datetime.now(timezone.utc)
        push.last_status = "success" if success else "failed"
        push.last_error = None if success else message
        await db.commit()

        logger.info(
            "推送执行完成 push_id=%s channel=%s success=%s",
            push_id, channel, success,
        )

        return {"success": success, "message": message}

    except Exception as e:
        error_msg = str(e)
        push.last_run_at = datetime.now(timezone.utc)
        push.last_status = "failed"
        push.last_error = error_msg
        await db.commit()

        logger.exception("推送执行异常 push_id=%s: %s", push_id, error_msg)
        return {"success": False, "message": error_msg}


# ---------------------------------------------------------------------------
# 渠道发送（内部辅助）
# ---------------------------------------------------------------------------


async def _send_webhook(config: dict, payload: dict) -> tuple[bool, str]:
    """通过 HTTP webhook 发送推送"""
    import aiohttp

    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return False, "webhook_url 未配置"

    headers = config.get("headers", {})
    headers.setdefault("Content-Type", "application/json")

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                webhook_url, json=payload, headers=headers
            ) as resp:
                if 200 <= resp.status < 300:
                    return True, f"webhook 发送成功, HTTP {resp.status}"
                else:
                    body = await resp.text()
                    return False, f"webhook 返回错误 {resp.status}: {body[:500]}"
    except Exception as e:
        return False, f"webhook 请求失败: {e}"


async def _send_im_webhook(
    channel: str, config: dict, payload: dict
) -> tuple[bool, str]:
    """通过企业微信 / 钉钉 / 飞书 webhook 发送消息

    将 payload 格式化为对应 IM 平台的消息格式后发送。
    """
    import aiohttp

    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return False, f"{channel} webhook_url 未配置"

    # 构建消息体
    msg_type = config.get("msg_type", "markdown")
    title = payload.get("dashboard_name", "看板推送")
    screenshot_url = payload.get("screenshot_url", "")
    generated_at = payload.get("generated_at", "")

    if channel == "dingtalk":
        body = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n![看板截图]({screenshot_url})\n\n> 生成时间: {generated_at}",
            },
        }
    elif channel == "wechat":
        body = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n![看板截图]({screenshot_url})\n\n> 生成时间: {generated_at}",
            },
        }
    elif channel == "feishu":
        body = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [
                    {"tag": "img", "img_key": screenshot_url, "alt": {"tag": "plain_text", "content": "看板截图"}},
                    {"tag": "note", "elements": [{"tag": "plain_text", "content": f"生成时间: {generated_at}"}]},
                ],
            },
        }
    else:
        body = {"msgtype": "text", "text": {"content": f"{title}\n{screenshot_url}"}}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(webhook_url, json=body) as resp:
                if 200 <= resp.status < 300:
                    return True, f"{channel} 发送成功"
                else:
                    resp_body = await resp.text()
                    return False, f"{channel} 返回错误 {resp.status}: {resp_body[:500]}"
    except Exception as e:
        return False, f"{channel} 请求失败: {e}"


async def _send_email(config: dict, payload: dict) -> tuple[bool, str]:
    """通过 SMTP 发送邮件推送

    这是一个占位实现。生产环境应集成实际的邮件发送服务
    （如 SMTP 客户端、SendGrid API 等）。
    """
    recipients = config.get("recipients", [])
    if not recipients:
        return False, "邮件收件人未配置"

    subject = config.get("subject") or f"看板推送: {payload.get('dashboard_name', '')}"
    screenshot_url = payload.get("screenshot_url", "")
    generated_at = payload.get("generated_at", "")

    # 占位: 邮件发送逻辑
    logger.info(
        "[邮件推送占位] 收件人=%s 主题=%s 截图=%s 时间=%s",
        recipients, subject, screenshot_url, generated_at,
    )

    # 生产环境实现示例:
    # import smtplib
    # from email.mime.text import MIMEText
    # from email.mime.multipart import MIMEMultipart
    # msg = MIMEMultipart()
    # msg["Subject"] = subject
    # msg["From"] = config["from"]
    # msg["To"] = ", ".join(recipients)
    # msg.attach(MIMEText(body, "html"))
    # with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
    #     server.starttls()
    #     server.login(config["smtp_user"], config["smtp_password"])
    #     server.send_message(msg)

    return True, "邮件推送已提交（占位实现）"


# ---------------------------------------------------------------------------
# 截图生成
# ---------------------------------------------------------------------------


async def generate_screenshot(
    db: AsyncSession, dashboard_id: str
) -> str:
    """生成看板截图（占位 / mock 实现）

    在生产环境中，应集成分离的截图渲染服务（如 Puppeteer、Playwright）
    来渲染看板页面并生成 PNG 截图。

    返回:
        str  截图 URL 或 base64 数据 URL
    """
    # 校验看板是否存在
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.is_deleted == False,
        )
    )
    dashboard = result.scalar_one_or_none()

    if not dashboard:
        raise ValueError(f"看板不存在: {dashboard_id}")

    # 占位: 返回一个 mock 截图 URL
    # 生产环境应调用截图服务，例如:
    #
    #   async with aiohttp.ClientSession() as session:
    #       screenshot_service_url = settings.SCREENSHOT_SERVICE_URL
    #       async with session.post(
    #           f"{screenshot_service_url}/api/screenshot",
    #           json={"dashboard_id": dashboard_id, "width": dashboard.width, "height": dashboard.height},
    #       ) as resp:
    #           result = await resp.json()
    #           return result["image_url"]
    #

    mock_url = f"/api/v1/screenshots/{dashboard_id}/placeholder.png"
    logger.info(
        "截图已生成（占位）dashboard_id=%s url=%s",
        dashboard_id, mock_url,
    )
    return mock_url


# ---------------------------------------------------------------------------
# 分享链接校验
# ---------------------------------------------------------------------------


async def validate_share_token(
    db: AsyncSession, token: str, password: Optional[str] = None
) -> Optional[ShareRecord]:
    """校验分享 token 的有效性，返回 ShareRecord 或抛出 ValueError

    校验项:
        - token 是否存在
        - 是否已过期
        - 是否需要密码（如需要则校验）
        - 是否达到最大访问次数
    """
    record = await get_share_by_token(db, token)
    if not record:
        raise ValueError("分享链接无效或已过期")

    # 密码校验
    if record.password_protected:
        if not password:
            raise ValueError("该分享需要密码访问")
        if not verify_password(password, record.password_hash):
            raise ValueError("密码错误")

    # 最大访问次数校验
    max_access = (record.config or {}).get("max_access")
    if max_access is not None and record.access_count >= max_access:
        raise ValueError("分享链接已达最大访问次数限制")

    return record


async def get_scheduled_push(db: AsyncSession, push_id: str) -> Optional[ScheduledPush]:
    """获取单个定时推送任务"""
    result = await db.execute(
        select(ScheduledPush).where(ScheduledPush.id == push_id)
    )
    return result.scalar_one_or_none()
