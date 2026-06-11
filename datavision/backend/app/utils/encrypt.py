"""
加密工具 - 密码哈希、令牌生成、敏感信息脱敏
"""
import secrets
import hashlib
from passlib.context import CryptContext

# bcrypt 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希"""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """验证密码是否匹配哈希"""
    return pwd_context.verify(password, hashed)


def generate_token(length: int = 32) -> str:
    """生成 URL 安全的随机令牌"""
    return secrets.token_urlsafe(length)


def mask_sensitive(config: dict, keys: list = None) -> dict:
    """对配置中的敏感字段进行脱敏处理"""
    if keys is None:
        keys = ["password", "secret", "api_key", "token", "private_key"]
    masked = dict(config)
    for key in keys:
        if key in masked and masked[key]:
            val = str(masked[key])
            if len(val) > 4:
                masked[key] = val[:2] + "*" * (len(val) - 4) + val[-2:]
            else:
                masked[key] = "****"
    return masked


def md5_hash(text: str) -> str:
    """MD5 哈希（用于非安全场景，如数据指纹）"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()
