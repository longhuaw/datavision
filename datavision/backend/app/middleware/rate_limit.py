"""
速率限制中间件 - 基于 slowapi

分层限流策略:

    1. 全局默认      100 requests/minute per IP
    2. 认证端点      10  requests/minute per IP  (login / register — 防暴力破解)
    3. API 端点      1000 requests/minute per authenticated user
    4. AI 端点       20  requests/minute per authenticated user  (控制 LLM 成本)

使用方式:

    # 在路由上应用限流（装饰器模式）
    from app.middleware.rate_limit import limiter

    @router.post("/login")
    @limiter.limit("10/minute")
    async def login(...): ...

    # 在 main.py 中
    from app.middleware.rate_limit import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


# ---------------------------------------------------------------------------
# 自定义 key 函数：已认证用户按 user_id 限流，否则按 IP
# ---------------------------------------------------------------------------

def _get_user_id_or_ip(request: Request) -> str:
    """
    优先使用已认证用户的 ID 作为限流键，未认证则回退到客户端 IP。

    slowapi 在匹配 limit 规则时调用此函数生成限流键。
    返回值相同的请求共享同一个速率限制计数器。
    """
    try:
        user = request.state._starlette_user  # type: ignore[attr-defined]
    except AttributeError:
        user = getattr(request.state, "user", None)

    if user is not None:
        user_id = getattr(user, "id", None)
        if user_id is not None:
            return str(user_id)

    # get_remote_address 会尝试 X-Forwarded-For 等代理头
    return get_remote_address(request)


# ---------------------------------------------------------------------------
# 限流标签（可通过 limiter.limit(tag) 组合使用）
# ---------------------------------------------------------------------------

# 认证端点限流
AUTH_LIMIT = "10/minute"

# API 端点限流（已认证用户）
API_LIMIT = "1000/minute"

# AI 端点限流（已认证用户，控制 LLM 调用成本）
AI_LIMIT = "20/minute"

# 全局默认限流
GLOBAL_LIMIT = "100/minute"


# ---------------------------------------------------------------------------
# 全局限流器实例
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=_get_user_id_or_ip,
    default_limits=[GLOBAL_LIMIT],
    headers_enabled=True,          # 在响应头中返回限流信息
    strategy="fixed-window",       # 固定窗口：每个时间窗口独立计数
)
