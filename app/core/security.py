"""密码哈希与 JWT 签发/校验。

- 密码哈希使用 bcrypt（自动加盐）；bcrypt 原生上限 72 字节，超长密码在
  Schema 层直接拒绝，避免静默截断；
- JWT 使用 HS256；密钥长度不足 32 字符会被配置校验拒绝。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.errors import TokenError


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希（自动加盐）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # 哈希格式损坏时按“不匹配”处理，而不是让请求 500
        return False


def create_access_token(
    *, user_id: str, secret_key: str, algorithm: str, expires_minutes: int
) -> str:
    """签发访问令牌：sub 为用户 id，exp 为过期时间。"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> str:
    """校验令牌并返回用户 id；任何失败都统一抛 TokenError（不泄露细节）。"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("令牌已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("令牌无效") from exc
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise TokenError("令牌无效")
    return user_id
