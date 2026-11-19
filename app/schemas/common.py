"""通用响应模型。"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误信封：``{"error": {"code", "message", "detail"?}}``。"""

    error: dict[str, object]


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    app_version: str
    environment: str
    database: str
