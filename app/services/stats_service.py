"""统计服务：全部数据来自真实数据库聚合。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.core.config import Settings
from app.database.session import Database
from app.repositories.task_repository import TaskRepository
from app.schemas.stats import StatisticsResponse, TrendPoint

#: 优先级的展示顺序（高 -> 低）
_PRIORITY_ORDER = ("urgent", "high", "medium", "low")
_TREND_DAYS = 7


class StatsService:
    """任务统计。"""

    def __init__(self, settings: Settings, database: Database) -> None:
        self._settings = settings
        self._database = database

    def summary(self, user_id: str) -> StatisticsResponse:
        """汇总用户的任务统计与最近 7 天趋势。"""
        today = date.today()
        with self._database.session() as session:
            repository = TaskRepository(session)
            counts = repository.counts(user_id)
            trend_days = [
                today - timedelta(days=offset) for offset in range(_TREND_DAYS - 1, -1, -1)
            ]
            raw_trend = repository.trend(user_id, trend_days)

        total = counts["total"]
        completed = counts["completed"]
        by_priority = {name: counts["by_priority"].get(name, 0) for name in _PRIORITY_ORDER}
        trend = [
            TrendPoint(date=day.isoformat(), created=created, completed=completed_count)
            for day, (created, completed_count) in raw_trend.items()
        ]
        return StatisticsResponse(
            total_tasks=total,
            completed_tasks=completed,
            pending_tasks=counts["pending"],
            overdue_tasks=counts["overdue"],
            completion_rate=round(completed / total, 4) if total else 0.0,
            by_priority=by_priority,
            trend=sorted(trend, key=lambda point: point.date),
            generated_at=datetime.now(UTC),
        )
