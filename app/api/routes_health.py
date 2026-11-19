"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.deps import Container, get_container
from app.schemas.common import HealthResponse

router = APIRouter(tags=["健康"])


@router.get("/health", response_model=HealthResponse, summary="健康检查")
def health(container: Container = Depends(get_container)) -> HealthResponse:
    """检查应用与数据库连通性。"""
    with container.database.session() as session:
        session.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        app_version=container.settings.app_version,
        environment=container.settings.environment,
        database="ok",
    )
