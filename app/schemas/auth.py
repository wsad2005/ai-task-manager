"""认证相关请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_-]+$"
_PASSWORD_HINT = "密码长度 8-72 个字符（bcrypt 上限 72 字节）"


class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=USERNAME_PATTERN,
        description="用户名：3-32 位，仅字母/数字/下划线/连字符",
    )
    password: str = Field(min_length=8, max_length=72, description=_PASSWORD_HINT)

    @field_validator("username")
    @classmethod
    def _strip_username(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("用户名不能为空白")
        return stripped

    @model_validator(mode="after")
    def _check_password_bytes(self) -> RegisterRequest:
        """bcrypt 上限 72 字节：多字节字符按字节数计算。"""
        if len(self.password.encode("utf-8")) > 72:
            raise ValueError("密码过长：最多 72 字节")
        return self


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    """用户公开信息（绝不包含密码哈希）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    """登录成功响应：访问令牌 + 用户信息。"""

    access_token: str
    token_type: str = "bearer"
    user: UserOut
