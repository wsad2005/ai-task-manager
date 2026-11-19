"""API 路由汇总。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_ai import router as ai_router
from app.api.routes_auth import router as auth_router
from app.api.routes_health import router as health_router
from app.api.routes_stats import router as stats_router
from app.api.routes_tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["任务"])
api_router.include_router(stats_router, prefix="/statistics", tags=["统计"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI"])
