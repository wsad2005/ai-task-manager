"""AI 功能的请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field, computed_field, field_validator

from app.schemas.task import TaskOut, TaskPriorityLiteral


class BreakdownRequest(BaseModel):
    """拆解请求。"""

    goal: str = Field(min_length=2, max_length=1000, description="要拆解的目标描述")

    @field_validator("goal")
    @classmethod
    def _strip_goal(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("目标不能为空白")
        return stripped


class BreakdownItem(BaseModel):
    """拆解出的单个子任务（预览，未入库）。

    模型输出的是相对天数 ``due_in_days``，服务端据此换算出建议截止日期，
    避免让模型直接编造日期。
    """

    title: str
    description: str = ""
    priority: TaskPriorityLiteral = "medium"
    due_in_days: int = Field(default=0, ge=0, le=365)
    estimated_minutes: int = Field(default=60, ge=5, le=480)
    order: int = 0

    @computed_field(return_type=date)
    @property
    def suggested_due_date(self) -> date:
        """建议截止日期 = 今天 + due_in_days。"""
        return date.today() + timedelta(days=self.due_in_days)


class BreakdownResponse(BaseModel):
    """拆解预览响应（未入库）。"""

    goal: str
    items: list[BreakdownItem]


class BreakdownConfirmItem(BaseModel):
    """用户确认要保存的子任务（可已在预览中修改）。"""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: TaskPriorityLiteral = "medium"
    due_date: date | None = None
    category: str | None = Field(default="AI 拆解", max_length=64)
    tags: list[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    """批量保存确认请求。"""

    items: list[BreakdownConfirmItem] = Field(min_length=1, max_length=20)


class ConfirmResponse(BaseModel):
    """批量保存结果。"""

    created: int
    tasks: list[TaskOut]


class DailyPlanFocus(BaseModel):
    """今日重点任务（只包含真实存在的任务）。"""

    task_id: str
    task_title: str
    reason: str
    time_slot: str


class DailyPlanResponse(BaseModel):
    """AI 每日计划响应（基于真实未完成任务）。"""

    daily_goal: str
    focus: list[DailyPlanFocus]
    overdue_reminders: list[str]
    source_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
