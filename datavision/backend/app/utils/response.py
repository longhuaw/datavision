"""
统一响应格式工具
所有 API 响应使用统一的结构: {"code": 200, "message": "success", "data": ...}
"""
from math import ceil
from typing import Any, Optional

from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "success", code: int = 200) -> dict:
    """成功响应，返回统一格式的字典"""
    return {"code": code, "message": message, "data": data}


def error_response(
    message: str = "error",
    code: int = 400,
    detail: Optional[Any] = None,
) -> dict:
    """
    错误响应，返回统一格式的字典

    Args:
        message: 错误消息
        code: HTTP 状态码
        detail: 可选的详细错误信息（如字段校验错误列表等）
    """
    body: dict = {"code": code, "message": message}
    if detail is not None:
        body["data"] = detail
    return body


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """
    分页响应，返回统一格式的字典

    Args:
        items: 当前页的数据列表
        total: 数据总数
        page: 当前页码
        page_size: 每页条数
    """
    total_pages = max(1, ceil(total / page_size)) if total > 0 else 1
    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def make_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
    status_code: Optional[int] = None,
    headers: Optional[dict] = None,
) -> JSONResponse:
    """
    将统一格式的字典包装为 FastAPI JSONResponse 对象。

    Args:
        data: 响应数据
        message: 提示消息
        code: 业务状态码
        status_code: HTTP 状态码（默认与 code 一致）
        headers: 自定义响应头
    """
    content = {
        "code": code,
        "message": message,
    }
    if data is not None:
        content["data"] = data

    return JSONResponse(
        content=content,
        status_code=status_code if status_code is not None else code,
        headers=headers,
    )
