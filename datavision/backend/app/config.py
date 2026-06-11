"""
DataVision 应用配置 — 基于 pydantic-settings，从 .env 文件加载。

所有配置项均可通过环境变量 / .env 文件覆盖。
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ==================== 应用配置 ====================
    APP_NAME: str = Field("DataVision", description="应用名称")
    APP_VERSION: str = Field("1.0.0", description="应用版本")
    DEBUG: bool = Field(False, description="调试模式")
    SECRET_KEY: str = Field("change-me-to-a-random-secret-key", description="应用密钥")

    # ==================== 数据库配置 ====================
    MYSQL_HOST: str = Field("localhost", description="MySQL 主机地址")
    MYSQL_PORT: int = Field(3306, description="MySQL 端口")
    MYSQL_USER: str = Field("datavision", description="MySQL 用户名")
    MYSQL_PASSWORD: str = Field("datavision123", description="MySQL 密码")
    MYSQL_DATABASE: str = Field("datavision", description="数据库名称")

    @property
    def DATABASE_URL(self) -> str:
        """异步 MySQL 连接 URL (aiomysql / asyncmy)"""
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    # ==================== Redis 配置 ====================
    REDIS_HOST: str = Field("localhost", description="Redis 主机地址")
    REDIS_PORT: int = Field(6379, description="Redis 端口")
    REDIS_PASSWORD: str = Field("", description="Redis 密码，空字符串表示无密码")
    REDIS_DB: int = Field(0, description="Redis 数据库编号")

    @property
    def REDIS_URL(self) -> str:
        """Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
                f"/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ==================== JWT 配置 ====================
    JWT_SECRET_KEY: str = Field("change-me-jwt-secret-key", description="JWT 签名密钥")
    JWT_ALGORITHM: str = Field("HS256", description="JWT 签名算法")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, description="访问令牌过期时间(分钟)")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, description="刷新令牌过期时间(天)")

    # ==================== LLM 配置 (NL2SQL) ====================
    LLM_PROVIDER: str = Field("openai", description="LLM 提供商: openai | local | custom")
    LLM_API_KEY: str = Field("sk-your-api-key-here", description="LLM API Key")
    LLM_MODEL: str = Field("gpt-4o", description="LLM 模型名称")
    LLM_BASE_URL: str = Field(
        "https://api.openai.com/v1", description="LLM API 基础地址"
    )

    # ==================== 文件存储 ====================
    UPLOAD_DIR: str = Field("./uploads", description="文件上传目录")
    MAX_UPLOAD_SIZE_MB: int = Field(10, description="最大上传大小(MB)")

    # ==================== CORS 配置 ====================
    CORS_ORIGINS: List[str] = Field(
        ["http://localhost:5173", "http://localhost:3000"],
        description="允许的跨域来源列表",
    )

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = Field("INFO", description="日志级别")
    LOG_DIR: str = Field("./logs", description="日志文件目录")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# 单例 —— 其他模块通过 `from app.config import settings` 引用
settings = Settings()
