"""
DataVision API 路由包

每个模块提供自己的 APIRouter 实例，由 main.py 统一注册到 /api/v1 前缀下。

若某个模块尚未实现，会提供一个带文档说明的占位路由，避免启动报错。
"""
import logging

from fastapi import APIRouter

logger = logging.getLogger("datavision.api")


def _placeholder_router(name: str) -> APIRouter:
    """返回一个带占位端点的路由器，提示该模块尚未实现。"""
    router = APIRouter()

    @router.get("/", summary=f"{name} 模块（未实现）")
    async def _placeholder():
        return {
            "message": f"{name} 模块尚未实现",
            "status": "pending",
        }

    logger.warning("%s 路由模块未找到，使用占位路由", name)
    return router


# ---------------------------------------------------------------------------
# 按阶段逐步替换为真实路由
# ---------------------------------------------------------------------------
try:
    from app.api.v1.auth import router as auth_router
except ImportError:
    auth_router = _placeholder_router("auth")

try:
    from app.api.v1.users import router as users_router
except ImportError:
    users_router = _placeholder_router("users")

try:
    from app.api.v1.datasources import router as datasources_router
except ImportError:
    datasources_router = _placeholder_router("datasources")

try:
    from app.api.v1.datasets import router as datasets_router
except ImportError:
    datasets_router = _placeholder_router("datasets")

try:
    from app.api.v1.charts import router as charts_router
except ImportError:
    charts_router = _placeholder_router("charts")

try:
    from app.api.v1.dashboards import router as dashboards_router
except ImportError:
    dashboards_router = _placeholder_router("dashboards")

try:
    from app.api.v1.ai import router as ai_router
except ImportError:
    ai_router = _placeholder_router("ai")

try:
    from app.api.v1.publish import router as publish_router
except ImportError:
    publish_router = _placeholder_router("publish")

try:
    from app.api.v1.ws import router as ws_router
except ImportError:
    ws_router = _placeholder_router("ws")


__all__ = [
    "auth_router",
    "users_router",
    "datasources_router",
    "datasets_router",
    "charts_router",
    "dashboards_router",
    "ai_router",
    "publish_router",
    "ws_router",
]
