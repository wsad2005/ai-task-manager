"""统一异常处理：把各类异常收敛成 ``{"error": {...}}`` 响应。

前端只需要处理一种错误结构；同时保留正确的 HTTP 状态码，
5xx 记 error 日志、4xx 记 info 日志。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _payload(code: str, message: str, detail: object = None) -> dict[str, object]:
    body: dict[str, object] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "业务异常 %s %s -> %s(%s): %s",
                request.method,
                request.url.path,
                exc.code,
                exc.status_code,
                exc.message,
            )
        else:
            logger.info(
                "业务异常 %s %s -> %s: %s",
                request.method,
                request.url.path,
                exc.code,
                exc.message,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = jsonable_encoder(exc.errors(), custom_encoder={})
        # errors() 的 ctx 可能包含不可序列化对象，只保留可读字段
        simplified = [
            {"loc": item.get("loc"), "msg": item.get("msg"), "type": item.get("type")}
            for item in errors
        ]
        return JSONResponse(
            status_code=422,
            content=_payload(
                "request_validation_error",
                "请求参数不合法",
                simplified,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(f"http_{exc.status_code}", str(exc.detail)),
        )
