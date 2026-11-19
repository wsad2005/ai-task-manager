"""统计相关响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """单日趋势点：当日新建与完成的任务数。"""

    date: str  # YYYY-MM-DD
    created: int
    completed: int


class StatisticsResponse(BaseModel):
    """来自真实数据库的统计结果。"""

    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    completion_rate: float
    by_priority: dict[str, int]
    trend: list[TrendPoint]
    generated_at: datetime
