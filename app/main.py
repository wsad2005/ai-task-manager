"""FastAPI 应用入口。

启动顺序：读配置 → 确保目录 → 执行数据库迁移（幂等）→ 装配容器与路由 → 挂载前端（存在时）。
从不删除或重建数据库。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import PROJECT_ROOT, Settings
from app.core.handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.database.migrations import run_migrations

logger = get_logger(__name__)

FRONTEND_DIR = PROJECT_ROOT / "frontend"

DESCRIPTION = """
AI 智能任务管理系统：JWT 认证、任务 CRUD 与多维筛选、真实数据库统计，
以及可选的 AI 任务拆解与每日计划（OpenAI 兼容接口，未配置时普通功能完整可用）。

**接口文档**：`/docs`（Swagger UI）、`/redoc`、`/openapi.json`。
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂；测试通过传入自定义 Settings 使用隔离数据库。"""
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings.ensure_directories()
        run_migrations(resolved_settings)
        from app.api.deps import Container

        container = Container(resolved_settings)
        app.state.container = container
        logger.info("%s v%s 已启动", resolved_settings.app_name, resolved_settings.app_version)
        try:
            yield
        finally:
            container.dispose()

    app = FastAPI(
        title="AI Task Manager API",
        description=DESCRIPTION,
        version=resolved_settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=resolved_settings.api_prefix)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """挂载原生前端（frontend/ 目录存在时）：``/`` 返回首页。"""
    if not FRONTEND_DIR.exists():  # pragma: no cover - P3 之前仓库暂无 frontend
        logger.info("未找到 frontend 目录，跳过页面挂载：%s", FRONTEND_DIR)
        return

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")


app = create_app()
