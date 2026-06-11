"""
WebSocket 端点 - 看板实时数据推送 与 图表实时数据推送

提供:
- WS /ws/dashboard/{dashboard_id}  — 看板实时数据流
- WS /ws/chart/{chart_id}          — 图表实时数据流
- ConnectionManager               — 活跃连接追踪与广播
"""

import asyncio
import json
import logging
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import _engine, _AsyncSessionLocal
from app.models.user import User

logger = logging.getLogger("datavision.ws")

router = APIRouter(prefix="/ws")


# ============================================================================
# WebSocket 连接管理器
# ============================================================================

class ConnectionManager:
    """
    管理活跃的 WebSocket 连接。

    按资源类型分组追踪连接（dashboard / chart），支持:
    - 按资源 ID 广播消息
    - 单连接推送
    - 连接断开自动清理
    - 订阅跟踪
    """

    def __init__(self):
        # resource_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        # websocket -> subscribed resource ids
        self._subscriptions: dict[int, set[str]] = {}

    async def connect(self, websocket: WebSocket, resource_id: str) -> None:
        """接受 WebSocket 连接并注册到资源分组"""
        await websocket.accept()
        self._connections.setdefault(resource_id, set()).add(websocket)
        # 初始化订阅
        ws_id = id(websocket)
        self._subscriptions.setdefault(ws_id, set()).add(resource_id)
        logger.info(
            "WebSocket 已连接 resource=%s total_connections=%d",
            resource_id,
            len(self._connections[resource_id]),
        )

    async def disconnect(self, websocket: WebSocket, resource_id: str) -> None:
        """断开连接并从所有分组中移除"""
        ws_id = id(websocket)

        # 从当前资源分组移除
        conns = self._connections.get(resource_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[resource_id]

        # 从所有订阅的资源分组中移除
        for rid in list(self._subscriptions.get(ws_id, set())):
            rconns = self._connections.get(rid)
            if rconns:
                rconns.discard(websocket)
                if not rconns:
                    del self._connections[rid]

        self._subscriptions.pop(ws_id, None)
        logger.info(
            "WebSocket 已断开 resource=%s remaining=%d",
            resource_id,
            len(self._connections.get(resource_id, set())),
        )

    def subscribe(self, websocket: WebSocket, resource_id: str) -> None:
        """订阅一个资源（用于跨资源场景，如前端的 subscribe 命令）"""
        ws_id = id(websocket)
        self._connections.setdefault(resource_id, set()).add(websocket)
        self._subscriptions.setdefault(ws_id, set()).add(resource_id)
        logger.debug("ws_id=%s subscribed to %s", ws_id, resource_id)

    def unsubscribe(self, websocket: WebSocket, resource_id: str) -> None:
        """取消订阅一个资源"""
        ws_id = id(websocket)
        conns = self._connections.get(resource_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[resource_id]
        subs = self._subscriptions.get(ws_id)
        if subs:
            subs.discard(resource_id)
        logger.debug("ws_id=%s unsubscribed from %s", ws_id, resource_id)

    async def send_personal(self, message: str, websocket: WebSocket) -> None:
        """向单个 WebSocket 发送文本消息"""
        try:
            await websocket.send_text(message)
        except Exception:
            logger.exception("发送消息失败")

    async def broadcast_to_resource(self, resource_id: str, message: str) -> None:
        """向订阅了某个资源的所有 WebSocket 广播消息"""
        conns = self._connections.get(resource_id, set())
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # 清理死连接
        for ws in dead:
            conns.discard(ws)

    @property
    def active_count(self) -> int:
        """当前活跃连接总数（去重）"""
        seen: set[int] = set()
        for conn_set in self._connections.values():
            for ws in conn_set:
                seen.add(id(ws))
        return len(seen)


# 全局连接管理器实例
manager = ConnectionManager()


# ============================================================================
# 认证辅助（WebSocket 专用，从 query param 提取 token）
# ============================================================================

async def _authenticate_ws_token(token: str) -> User:
    """
    从 WebSocket 的 token 查询参数解码 JWT，查询并返回当前用户。

    token 无效 / 过期 / 用户不存在时抛出 WebSocket 连接关闭码 4001。
    """
    if not token:
        raise WebSocketClose(
            code=4001,
            reason=json.dumps({"code": 401, "message": "缺少认证令牌"}),
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise WebSocketClose(
                code=4001,
                reason=json.dumps({"code": 401, "message": "令牌中缺少用户标识"}),
            )
    except jwt.ExpiredSignatureError:
        raise WebSocketClose(
            code=4001,
            reason=json.dumps({"code": 401, "message": "令牌已过期，请重新登录"}),
        )
    except jwt.InvalidTokenError as e:
        raise WebSocketClose(
            code=4001,
            reason=json.dumps({"code": 401, "message": f"无效的认证令牌: {e}"}),
        )

    # 查询用户
    async with _AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if not user:
        raise WebSocketClose(
            code=4001,
            reason=json.dumps({"code": 401, "message": "用户不存在或已被删除"}),
        )

    return user


# ============================================================================
# 自定义异常 — 用于在 WebSocket 握手阶段关闭连接
# ============================================================================

class WebSocketClose(Exception):
    """携带关闭码和消息的异常，在 WebSocket 端点中捕获后调用 websocket.close()"""

    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason


# ============================================================================
# 看板 WebSocket 端点
# ============================================================================

@router.websocket("/dashboard/{dashboard_id}")
async def dashboard_ws(
    websocket: WebSocket,
    dashboard_id: str,
    token: str = Query(..., description="JWT 认证令牌"),
):
    """
    看板实时数据 WebSocket。

    认证通过 token 查询参数传递（WebSocket 不支持自定义头）。
    连接成功后:
    - 按 refresh_interval 周期推送看板所有组件的最新数据
    - 监听客户端控制消息: refresh / subscribe / unsubscribe

    消息格式 (服务端 → 客户端):
    ```json
    {
      "type": "dashboard_data",
      "dashboard_id": "...",
      "timestamp": "...",
      "data": [
        {"component_id": "...", "chart_id": "...", "chart_type": "...", "data": {...}},
        ...
      ]
    }
    ```

    控制消息格式 (客户端 → 服务端):
    ```json
    {"action": "refresh"}          // 立即拉取最新数据
    {"action": "subscribe", "resource_id": "chart_xxx"}   // 订阅额外资源
    {"action": "unsubscribe", "resource_id": "chart_xxx"} // 取消订阅
    ```
    """
    # 1. 认证
    try:
        user = await _authenticate_ws_token(token)
    except WebSocketClose as e:
        await websocket.close(code=e.code, reason=e.reason)
        return

    # 2. 获取看板配置（refresh_interval）
    refresh_interval = 60  # 默认 60 秒
    dashboard_title = ""
    async with _AsyncSessionLocal() as db:
        from app.models.dashboard import Dashboard

        result = await db.execute(
            select(Dashboard).where(
                Dashboard.id == dashboard_id,
                Dashboard.is_deleted == False,
            )
        )
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            await websocket.close(
                code=4004,
                reason=json.dumps({"code": 404, "message": "看板不存在"}),
            )
            return
        refresh_interval = max(dashboard.refresh_interval or 60, 5)  # 最少 5 秒
        dashboard_title = dashboard.title

    # 3. 接受连接并注册
    await manager.connect(websocket, dashboard_id)
    logger.info(
        "看板 WebSocket 已建立 dashboard_id=%s user=%s interval=%ds",
        dashboard_id, user.id, refresh_interval,
    )

    try:
        # 4. 连接成功，发送初始确认消息
        await manager.send_personal(
            json.dumps({
                "type": "connected",
                "dashboard_id": dashboard_id,
                "dashboard_title": dashboard_title,
                "refresh_interval": refresh_interval,
                "user": user.username,
                "message": "连接成功",
            }, ensure_ascii=False),
            websocket,
        )

        # 5. 立即推送第一波数据
        await _push_dashboard_data(websocket, dashboard_id)

        # 6. 控制消息接收任务
        async def receive_control_messages() -> None:
            """持续接收客户端发来的控制消息"""
            while True:
                try:
                    raw = await websocket.receive_text()
                    _handle_control_message(websocket, raw, dashboard_id)
                except WebSocketDisconnect:
                    break
                except Exception:
                    logger.exception("接收控制消息异常")
                    break

        # 启动控制消息监听（不阻塞主循环）
        control_task = asyncio.create_task(receive_control_messages())

        # 7. 主循环 — 按间隔推送看板数据
        while True:
            try:
                await asyncio.sleep(refresh_interval)
                # 检查连接是否还活着
                if websocket.client_state.name == "DISCONNECTED":
                    break
                await _push_dashboard_data(websocket, dashboard_id)
            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("推送看板数据异常 dashboard_id=%s", dashboard_id)
                break

        # 清理控制消息任务
        control_task.cancel()
        try:
            await control_task
        except asyncio.CancelledError:
            pass

    except WebSocketDisconnect:
        logger.info("客户端断开连接 dashboard_id=%s", dashboard_id)
    except Exception:
        logger.exception("看板 WebSocket 异常 dashboard_id=%s", dashboard_id)
    finally:
        await manager.disconnect(websocket, dashboard_id)


# ============================================================================
# 图表 WebSocket 端点
# ============================================================================

@router.websocket("/chart/{chart_id}")
async def chart_ws(
    websocket: WebSocket,
    chart_id: str,
    token: str = Query(..., description="JWT 认证令牌"),
):
    """
    图表实时数据 WebSocket。

    认证通过 token 查询参数传递。
    连接成功后:
    - 按图表配置的 refresh_interval 周期推送图表最新数据
    - 监听客户端控制消息: refresh / subscribe / unsubscribe

    消息格式 (服务端 → 客户端):
    ```json
    {
      "type": "chart_data",
      "chart_id": "...",
      "timestamp": "...",
      "data": {"columns": [...], "rows": [...]}
    }
    ```
    """
    # 1. 认证
    try:
        user = await _authenticate_ws_token(token)
    except WebSocketClose as e:
        await websocket.close(code=e.code, reason=e.reason)
        return

    # 2. 获取图表配置
    refresh_interval = 60
    chart_name = ""
    async with _AsyncSessionLocal() as db:
        from app.models.chart import Chart

        result = await db.execute(
            select(Chart).where(Chart.id == chart_id, Chart.is_deleted == False)
        )
        chart = result.scalar_one_or_none()
        if not chart:
            await websocket.close(
                code=4004,
                reason=json.dumps({"code": 404, "message": "图表不存在"}),
            )
            return
        query_config = chart.query_config or {}
        refresh_interval = max(query_config.get("refresh_interval", 60), 5)
        chart_name = chart.name

    # 3. 接受连接并注册
    await manager.connect(websocket, chart_id)
    logger.info(
        "图表 WebSocket 已建立 chart_id=%s user=%s interval=%ds",
        chart_id, user.id, refresh_interval,
    )

    try:
        # 4. 发送确认消息
        await manager.send_personal(
            json.dumps({
                "type": "connected",
                "chart_id": chart_id,
                "chart_name": chart_name,
                "refresh_interval": refresh_interval,
                "user": user.username,
                "message": "连接成功",
            }, ensure_ascii=False),
            websocket,
        )

        # 5. 立即推送第一波数据
        await _push_chart_data(websocket, chart_id)

        # 6. 控制消息接收任务
        async def receive_control_messages() -> None:
            while True:
                try:
                    raw = await websocket.receive_text()
                    _handle_control_message(websocket, raw, chart_id)
                except WebSocketDisconnect:
                    break
                except Exception:
                    logger.exception("接收控制消息异常")
                    break

        control_task = asyncio.create_task(receive_control_messages())

        # 7. 主循环
        while True:
            try:
                await asyncio.sleep(refresh_interval)
                if websocket.client_state.name == "DISCONNECTED":
                    break
                await _push_chart_data(websocket, chart_id)
            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("推送图表数据异常 chart_id=%s", chart_id)
                break

        control_task.cancel()
        try:
            await control_task
        except asyncio.CancelledError:
            pass

    except WebSocketDisconnect:
        logger.info("客户端断开连接 chart_id=%s", chart_id)
    except Exception:
        logger.exception("图表 WebSocket 异常 chart_id=%s", chart_id)
    finally:
        await manager.disconnect(websocket, chart_id)


# ============================================================================
# 控制消息处理
# ============================================================================

def _handle_control_message(
    websocket: WebSocket,
    raw: str,
    current_resource_id: str,
) -> None:
    """
    解析并执行客户端发来的控制命令。

    支持的命令:
    - refresh: 立即推送当前资源的最新数据
    - subscribe: 订阅额外的资源 ID
    - unsubscribe: 取消订阅某个资源 ID
    """
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("收到无效 JSON 控制消息: %s", raw[:200])
        return

    action = msg.get("action", "").strip().lower()
    if not action:
        return

    if action == "refresh":
        logger.debug("收到 refresh 请求 resource=%s", current_resource_id)
        # 标记刷新 — 由主循环在下一次迭代中处理，
        # 也可以在这里触发即时的数据推送
        asyncio.create_task(_handle_refresh(websocket, current_resource_id, msg))

    elif action == "subscribe":
        resource_id = msg.get("resource_id")
        if resource_id:
            manager.subscribe(websocket, resource_id)
            logger.info("客户端订阅 resource=%s", resource_id)

    elif action == "unsubscribe":
        resource_id = msg.get("resource_id")
        if resource_id:
            manager.unsubscribe(websocket, resource_id)
            logger.info("客户端取消订阅 resource=%s", resource_id)

    else:
        logger.debug("未知控制命令: %s", action)


async def _handle_refresh(
    websocket: WebSocket,
    resource_id: str,
    msg: dict,
) -> None:
    """立即推送最新数据以响应 refresh 控制命令"""
    try:
        if resource_id.startswith("chart_"):
            await _push_chart_data(websocket, resource_id)
        else:
            await _push_dashboard_data(websocket, resource_id)
    except Exception:
        logger.exception("refresh 处理失败 resource=%s", resource_id)


# ============================================================================
# 数据推送逻辑
# ============================================================================

async def _push_dashboard_data(websocket: WebSocket, dashboard_id: str) -> None:
    """查询看板中所有图表的最新数据并推送给客户端"""
    from datetime import datetime, timezone

    from app.services.dashboard_service import get_dashboard_components_data_parallel

    try:
        async with _AsyncSessionLocal() as db:
            results = await get_dashboard_components_data_parallel(
                db=db,
                dashboard_id=dashboard_id,
                cache_manager=None,
                force_refresh=False,
            )
        payload = json.dumps({
            "type": "dashboard_data",
            "dashboard_id": dashboard_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": results,
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)
    except ValueError:
        # 看板不存在
        payload = json.dumps({
            "type": "error",
            "dashboard_id": dashboard_id,
            "message": "看板不存在或已被删除",
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)
    except Exception:
        logger.exception("获取看板数据失败 dashboard_id=%s", dashboard_id)
        payload = json.dumps({
            "type": "error",
            "dashboard_id": dashboard_id,
            "message": "获取看板数据失败",
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)


async def _push_chart_data(websocket: WebSocket, chart_id: str) -> None:
    """查询单个图表的最新数据并推送给客户端"""
    from datetime import datetime, timezone

    from app.services.chart_service import get_chart_data

    try:
        async with _AsyncSessionLocal() as db:
            data = await get_chart_data(
                db=db,
                chart_id=chart_id,
                cache_manager=None,
                force_refresh=False,
            )
        payload = json.dumps({
            "type": "chart_data",
            "chart_id": chart_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "columns": data.get("columns", []),
                "rows": data.get("rows", []),
            },
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)
    except ValueError:
        payload = json.dumps({
            "type": "error",
            "chart_id": chart_id,
            "message": "图表不存在或已被删除",
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)
    except Exception:
        logger.exception("获取图表数据失败 chart_id=%s", chart_id)
        payload = json.dumps({
            "type": "error",
            "chart_id": chart_id,
            "message": "获取图表数据失败",
        }, ensure_ascii=False)
        await manager.send_personal(payload, websocket)
