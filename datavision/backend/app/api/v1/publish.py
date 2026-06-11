"""
发布分享 API — 分享链接管理、已发布看板查看、定时推送管理

公开端点（无需认证）：
- GET  /view/{token}          查看已发布的看板（含组件和数据）
- POST /view/{token}/verify   校验受保护看板的访问密码

鉴权端点（需要登录）：
- GET    /shares/{dashboard_id}       列出看板的所有分享记录
- POST   /shares/{dashboard_id}       创建分享链接 → ShareRecord
- DELETE /shares/{share_id}           撤销分享
- GET    /pushes/{dashboard_id}       列出看板的定时推送任务
- POST   /pushes/{dashboard_id}       创建定时推送任务
- PUT    /pushes/{push_id}            更新推送配置
- DELETE /pushes/{push_id}            删除推送任务
- POST   /pushes/{push_id}/execute    手动触发推送
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.dependencies import get_db, get_redis
from app.middleware.auth import get_current_active_user
from app.models.user import User
from app.services import publish_service, dashboard_service
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/publish", tags=["发布分享"])


# ===========================================================================
# 辅助函数
# ===========================================================================

def _share_to_dict(record) -> dict:
    """将 ShareRecord ORM 对象转换为字典"""
    return {
        "id": record.id,
        "dashboard_id": record.dashboard_id,
        "shared_by": record.shared_by,
        "share_type": record.share_type,
        "token": record.token,
        "password_protected": record.password_protected,
        "config": record.config,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "access_count": record.access_count,
        "last_accessed_at": record.last_accessed_at.isoformat() if record.last_accessed_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _push_to_dict(push) -> dict:
    """将 ScheduledPush ORM 对象转换为字典（脱敏敏感配置）"""
    config = dict(push.config) if push.config else {}
    # 脱敏 webhook_url 中的 secret / key 等敏感参数
    if "webhook_url" in config:
        url = config["webhook_url"]
        # 简单脱敏：隐藏 URL 中的敏感查询参数
        for sensitive_key in ("secret", "sign", "token", "key", "access_token"):
            import re
            url = re.sub(
                rf"({sensitive_key}=)([^&\s]+)",
                r"\1****",
                url,
                flags=re.IGNORECASE,
            )
        config["webhook_url"] = url

    return {
        "id": push.id,
        "dashboard_id": push.dashboard_id,
        "dashboard_name": push.dashboard_name,
        "channel": push.channel,
        "cron_expr": push.cron_expr,
        "config": config,
        "enabled": push.enabled,
        "last_run_at": push.last_run_at.isoformat() if push.last_run_at else None,
        "last_status": push.last_status,
        "last_error": push.last_error,
        "created_by": push.created_by,
        "created_at": push.created_at.isoformat() if push.created_at else None,
        "updated_at": push.updated_at.isoformat() if push.updated_at else None,
    }


# ===========================================================================
# 公开端点：已发布看板查看
# ===========================================================================

@router.get("/view/{token}", summary="查看已发布的看板")
async def view_published_dashboard(
    token: str,
    password: str = Query(default=None, description="访问密码（受密码保护的看板需要）"),
    db: AsyncSession = Depends(get_db),
):
    """
    通过发布令牌查看看板内容（公开访问，无需登录）。

    返回看板信息、所有组件数据。
    可通过 ?password=xxx 提供密码访问受密码保护的看板。
    """
    try:
        result = await dashboard_service.get_published_dashboard(
            db, token, password=password
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    dashboard = result["dashboard"]
    components = result["components"]

    return success_response(data={
        "dashboard": {
            "id": dashboard.id,
            "title": dashboard.title,
            "description": dashboard.description,
            "theme": dashboard.theme,
            "width": dashboard.width,
            "height": dashboard.height,
            "background": dashboard.background,
            "refresh_interval": dashboard.refresh_interval,
            "password_protected": dashboard.password_protected,
            "config": dashboard.config,
            "created_at": dashboard.created_at.isoformat() if dashboard.created_at else None,
        },
        "components": [{
            "id": c.id,
            "chart_id": c.chart_id,
            "chart_name": c.chart_name,
            "chart_type": c.chart_type,
            "position": c.position,
            "z_index": c.z_index,
            "config": c.config,
            "sort_order": c.sort_order,
        } for c in components],
    })


@router.post("/view/{token}/verify", summary="校验看板访问密码")
async def verify_dashboard_password(
    token: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    校验已发布看板的访问密码。

    请求体: {"password": "..."}
    成功返回 {"verified": true}，失败返回 403 或 404。
    """
    password = body.get("password", "")
    try:
        result = await dashboard_service.get_published_dashboard(
            db, token, password=password
        )
        return success_response(data={"verified": True}, message="密码验证成功")
    except ValueError as e:
        error_msg = str(e)
        if "密码" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg,
        )


# ===========================================================================
# 鉴权端点：分享管理
# ===========================================================================

@router.get("/shares/{dashboard_id}", summary="列出看板的所有分享记录")
async def list_shares(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """获取指定看板的所有分享记录列表。"""
    records = await publish_service.list_shares(db, dashboard_id)
    return success_response(data=[_share_to_dict(r) for r in records])


@router.post("/shares/{dashboard_id}", summary="创建分享链接", status_code=201)
async def create_share(
    dashboard_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    为看板创建新的分享链接。

    请求体示例:
    {
        "share_type": "link",        // 分享类型: link / embed
        "password": "optional_pwd",  // 可选，访问密码
        "expires_at": "2026-12-31T23:59:59",  // 可选，过期时间
        "allow_download": false,     // 可选，是否允许下载
        "max_access": 100            // 可选，最大访问次数
    }
    """
    try:
        record = await publish_service.create_share_link(
            db,
            dashboard_id=dashboard_id,
            shared_by=current_user.id,
            config=body,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建分享失败: {str(e)}",
        )

    return success_response(
        data=_share_to_dict(record),
        message="分享链接创建成功",
        code=201,
    )


@router.delete("/shares/{share_id}", summary="撤销分享")
async def revoke_share(
    share_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """撤销（删除）指定的分享链接。"""
    ok = await publish_service.revoke_share(db, share_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享记录不存在",
        )
    return success_response(message="分享已撤销")


# ===========================================================================
# 鉴权端点：定时推送管理
# ===========================================================================

@router.get("/pushes/{dashboard_id}", summary="列出看板的定时推送任务")
async def list_scheduled_pushes(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """获取指定看板的所有定时推送任务列表。"""
    pushes = await publish_service.list_scheduled_pushes(db, dashboard_id)
    return success_response(data=[_push_to_dict(p) for p in pushes])


@router.post("/pushes/{dashboard_id}", summary="创建定时推送任务", status_code=201)
async def create_scheduled_push(
    dashboard_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    为看板创建定时推送任务。

    请求体示例:
    {
        "channel": "dingtalk",          // 推送渠道: wechat / dingtalk / email / feishu / webhook
        "cron_expr": "0 9 * * *",       // Cron 表达式（每天早上9点）
        "config": {                     // 渠道配置
            "webhook_url": "https://...",
            "msg_type": "markdown"
        },
        "enabled": true,                // 是否启用（默认 true）
        "dashboard_name": "销售看板"     // 可选，看板名称（冗余）
    }
    """
    # 基本校验
    if "channel" not in body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="缺少必填字段: channel",
        )
    if "cron_expr" not in body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="缺少必填字段: cron_expr",
        )

    valid_channels = {"wechat", "dingtalk", "email", "feishu", "webhook"}
    if body["channel"] not in valid_channels:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"无效的推送渠道: {body['channel']}，支持: {', '.join(sorted(valid_channels))}",
        )

    try:
        push = await publish_service.create_scheduled_push(
            db,
            dashboard_id=dashboard_id,
            push_data=body,
            user_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建推送任务失败: {str(e)}",
        )

    return success_response(
        data=_push_to_dict(push),
        message="定时推送任务创建成功",
        code=201,
    )


@router.put("/pushes/{push_id}", summary="更新推送配置")
async def update_scheduled_push(
    push_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    更新指定推送任务的配置（部分更新）。

    请求体可包含任意需要更新的字段: channel, cron_expr, config, enabled, dashboard_name
    """
    # 校验渠道（如果提供）
    if "channel" in body and body["channel"] is not None:
        valid_channels = {"wechat", "dingtalk", "email", "feishu", "webhook"}
        if body["channel"] not in valid_channels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"无效的推送渠道: {body['channel']}",
            )

    push = await publish_service.update_scheduled_push(db, push_id, body)
    if not push:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="推送任务不存在",
        )

    return success_response(
        data=_push_to_dict(push),
        message="推送配置更新成功",
    )


@router.delete("/pushes/{push_id}", summary="删除推送任务")
async def delete_scheduled_push(
    push_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """删除指定的定时推送任务。"""
    ok = await publish_service.delete_scheduled_push(db, push_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="推送任务不存在",
        )
    return success_response(message="推送任务已删除")


@router.post("/pushes/{push_id}/execute", summary="手动触发推送")
async def execute_scheduled_push(
    push_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """
    手动立即执行一次推送任务（不等待 Cron 调度）。

    执行结果会记录到推送任务的 last_run_at / last_status / last_error 字段。
    """
    result = await publish_service.execute_push(db, push_id)

    if result["success"]:
        return success_response(
            data=result,
            message="推送执行成功",
        )
    else:
        return error_response(
            message=result.get("message", "推送执行失败"),
            code=500,
        )
