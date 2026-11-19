"""统计接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, StatsService, get_stats_service
from app.schemas.stats import StatisticsResponse

router = APIRouter()


@router.get(
    "",
    response_model=StatisticsResponse,
    summary="任务统计（总量/完成/逾期/完成率/优先级分布/近 7 天趋势）",
)
def statistics(
    user: CurrentUser,
    service: StatsService = Depends(get_stats_service),
) -> StatisticsResponse:
    """全部数据来自当前用户在数据库中的真实任务聚合。"""
    return service.summary(user.id)
