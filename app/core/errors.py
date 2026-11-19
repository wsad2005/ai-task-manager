"""异常体系与 HTTP 映射。

每个异常携带机器可读的 ``code``、对应的 ``status_code`` 与人类可读的 ``message``，
由 app/core/handlers.py 统一转换成 ``{"error": {...}}`` 响应。
约定：异常消息不包含密码、密钥等秘密信息。
"""

from __future__ import annotations


class AppError(Exception):
    """所有业务异常的基类。"""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, detail: object = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ValidationError(AppError):
    """业务级输入不合法（FastAPI 参数校验之外的场景）。"""

    status_code = 422
    code = "validation_error"


class UsernameTakenError(AppError):
    """注册时用户名已存在。"""

    status_code = 409
    code = "username_taken"


class InvalidCredentialsError(AppError):
    """用户名或密码错误（不区分具体原因，避免用户枚举）。"""

    status_code = 401
    code = "invalid_credentials"


class TokenError(AppError):
    """缺少、无效或过期的令牌。"""

    status_code = 401
    code = "token_error"


class NotFoundError(AppError):
    """资源不存在（跨用户访问也返回 404，避免泄露存在性）。"""

    status_code = 404
    code = "not_found"


class AIError(AppError):
    """AI 功能基础异常。"""

    status_code = 502
    code = "ai_error"


class AINotConfiguredError(AIError):
    """AI 未配置（缺 BASE_URL / API_KEY / MODEL 任一项）。"""

    status_code = 400
    code = "ai_not_configured"


class AITimeoutError(AIError):
    """AI 服务响应超时。"""

    status_code = 504
    code = "ai_timeout"


class AIQuotaError(AIError):
    """AI 服务额度不足或限流。"""

    status_code = 502
    code = "ai_quota"


class AIResponseError(AIError):
    """AI 返回内容无法解析或不符合约定。"""

    status_code = 502
    code = "ai_response_error"
