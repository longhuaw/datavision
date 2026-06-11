"""
DataVision — FastAPI 应用入口
智能数据可视化低代码平台

使用方式:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("datavision")


# ---------------------------------------------------------------------------
# 数据库 & Redis — 延迟导入，避免尚未初始化配置时触发连接
# ---------------------------------------------------------------------------
def get_db_engine():
    """返回异步 SQLAlchemy 引擎（延迟创建）"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


def get_redis():
    """返回异步 Redis 连接（延迟创建）"""
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# SlowAPI 限流器 — 统一从 middleware/rate_limit 导入
# ---------------------------------------------------------------------------
from app.middleware.rate_limit import limiter


# ---------------------------------------------------------------------------
# 请求日志中间件 (X-Request-ID)
# ---------------------------------------------------------------------------
from app.middleware.logging import RequestLoggingMiddleware


# ---------------------------------------------------------------------------
# 全局异常处理
# ---------------------------------------------------------------------------
async def http_404_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "code": 404,
            "message": f"请求的资源不存在: {request.url.path}",
            "data": None,
        },
    )


async def http_500_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("服务器内部错误: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "message": "请求参数校验失败",
            "data": {"errors": errors},
        },
    )


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ----- 启动 -----
    banner = r"""
    ╔══════════════════════════════════════════════╗
    ║          DataVision  v{version}               ║
    ║     智能数据可视化低代码平台                    ║
    ╚══════════════════════════════════════════════╝
    """.format(version=settings.APP_VERSION)
    logger.info(banner)
    logger.info("正在启动 DataVision 服务 ...")

    # 验证数据库连接
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        logger.info("✓ 数据库连接验证成功")
    except Exception as e:
        logger.error("✗ 数据库连接失败: %s", e)
        # 不阻止启动 — 允许应用在没有数据库时运行（方便开发调试）
        logger.warning("数据库不可用，部分功能将无法使用")

    # 验证 Redis 连接
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        logger.info("✓ Redis 连接验证成功")
    except Exception as e:
        logger.warning("Redis 连接失败: %s — 缓存和限流可能不可用", e)

    logger.info("DataVision 启动完成 ✓")

    yield

    # ----- 关闭 -----
    logger.info("正在关闭 DataVision 服务 ...")
    logger.info("DataVision 已关闭")


# ---------------------------------------------------------------------------
# FastAPI 应用实例
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="""
DataVision 是一个智能数据可视化低代码平台。

## 核心能力

- **多数据源接入**: MySQL、PostgreSQL、ClickHouse、SQLite、SQL Server、REST API、Excel
- **图表引擎**: 柱状图、折线图、饼图、散点图、面积图、热力图、地图等 20+ 图表类型
- **NL2SQL**: 自然语言查询数据，AI 辅助生成 SQL
- **看板设计器**: 拖拽布局、组件联动、主题定制
- **发布分享**: 密码保护、有效期、公开链接

## 技术栈

FastAPI + SQLAlchemy 2.0 (async) + MySQL + Redis + JWT
    """.strip(),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# 中间件注册（顺序敏感 — 后添加的先执行）
# ---------------------------------------------------------------------------

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-ms"],
)

# 2. 请求日志 (X-Request-ID)
app.add_middleware(RequestLoggingMiddleware)

# 3. SlowAPI 限流
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# 全局异常处理器
# ---------------------------------------------------------------------------
app.add_exception_handler(404, http_404_handler)  # type: ignore[arg-type]
app.add_exception_handler(500, http_500_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)

# ---------------------------------------------------------------------------
# API 路由注册  (/api/v1/...)
# ---------------------------------------------------------------------------
from app.api import auth_router, users_router, datasources_router
from app.api import datasets_router, charts_router, dashboards_router
from app.api import ai_router, publish_router, ws_router

api_prefix = "/api/v1"

# 所有路由器已在内部定义了各自的 prefix（如 /auth, /users, /charts 等）
# main.py 统一使用 /api/v1 作为外层前缀
app.include_router(auth_router, prefix=api_prefix, tags=["认证"])
app.include_router(users_router, prefix=api_prefix, tags=["用户管理"])
app.include_router(datasources_router, prefix=api_prefix, tags=["数据源"])
app.include_router(datasets_router, prefix=api_prefix, tags=["数据集"])
app.include_router(charts_router, prefix=api_prefix, tags=["图表"])
app.include_router(dashboards_router, prefix=api_prefix, tags=["看板"])
app.include_router(ai_router, prefix=api_prefix, tags=["AI助手"])
app.include_router(publish_router, prefix=api_prefix, tags=["发布分享"])
app.include_router(ws_router, prefix=api_prefix, tags=["WebSocket"])


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check(request: Request):
    """
    返回服务健康状态。
    可用于 Kubernetes liveness / readiness probe。
    """
    import platform
    from datetime import datetime, timezone

    db_status = "unknown"
    redis_status = "unknown"

    # 检查数据库
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # 检查 Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    overall = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return {
        "status": overall,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "checks": {
            "database": db_status,
            "redis": redis_status,
        },
    }


# ---------------------------------------------------------------------------
# 根路径
# ---------------------------------------------------------------------------
@app.get("/", tags=["系统"], summary="根路径")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
