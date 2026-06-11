"""
请求日志中间件 — 注入 X-Request-ID 并记录结构化 JSON 请求摘要。

特性：
  - X-Request-ID (UUID4) 生成 / 透传
  - 记录: method, path, query_params, status_code, duration_ms, client_ip, user_agent
  - POST / PUT 请求体记录（截断至 1000 字符）
  - JSON 格式日志输出 (通过标准 logging + json.dumps)，兼容 structlog 生态
  - 响应头注入 X-Request-ID
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("datavision.request")

# ---------------------------------------------------------------------------
# 请求体截断上限
# ---------------------------------------------------------------------------
_MAX_BODY_LENGTH = 1000


def _truncate_body(body: str, max_len: int = _MAX_BODY_LENGTH) -> str:
    """将请求体截断至 max_len 字符，超出时追加 '...(truncated)' 标记。"""
    if len(body) <= max_len:
        return body
    return body[:max_len] + "...(truncated)"


async def _read_body(request: Request) -> str | None:
    """
    安全读取请求体（仅对 POST / PUT / PATCH）。
    读取后通过重新构造接收流将 body 重新挂回 request，保证下游路由仍能读取。
    若读取失败返回 None。
    """
    method = request.method.upper()
    if method not in ("POST", "PUT", "PATCH"):
        return None

    content_type = request.headers.get("content-type", "")
    # 只记录常见编码的请求体；multipart / 二进制流跳过
    if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
        return "[binary or multipart body – skipped]"

    try:
        body_bytes = await request.body()
    except Exception:
        return None

    try:
        body_text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "[non-UTF-8 body – skipped]"

    # 重新构造接收流，让下游路由仍能读取
    async def _receive() -> dict:
        more_body = False
        return {
            "type": "http.request",
            "body": body_bytes,
            "more_body": more_body,
        }

    request._receive = _receive  # type: ignore[assignment]

    return body_text


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI 日志中间件。

    功能：
      1. 生成 / 透传 X-Request-ID (UUID4)
      2. 记录 JSON 格式请求日志（方法、路径、查询参数、状态码、耗时、
         客户端 IP、User-Agent）
      3. POST / PUT / PATCH 请求体记录（最多 1000 字符）
      4. 将 X-Request-ID 注入响应头
    """

    async def dispatch(self, request: Request, call_next):
        # ---- 1. 生成或提取 Request ID ----
        request_id = request.headers.get(
            "X-Request-ID", str(uuid.uuid4())
        )
        request.state.request_id = request_id

        # ---- 2. 读取请求体（仅对写操作类型） ----
        body_text = await _read_body(request)

        # ---- 3. 计时并执行下游 ----
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        # ---- 4. 注入响应头 ----
        response.headers["X-Request-ID"] = request_id

        # ---- 5. 组装 JSON 日志 ----
        log_entry: Dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": request.url.query,
            "status_code": response.status_code,
            "duration_ms": round(elapsed_ms, 3),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
        }

        if body_text is not None:
            log_entry["body"] = _truncate_body(body_text)

        # ---- 6. 日志输出 (JSON 行) ----
        logger.info(json.dumps(log_entry, ensure_ascii=False))

        return response
