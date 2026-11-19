"""任务模型。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

#: 任务的合法状态与优先级（与数据库 CHECK 约束保持一致）
TASK_STATUSES = ("todo", "done")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")
#: 优先级从高到低的排序权重（用于“按优先级排序”）
PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


class Task(Base, TimestampMixin):
    """任务：属于唯一用户（一对多），删除用户时级联删除。"""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_tasks_user_id_users"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Task id={self.id} user={self.user_id} title={self.title!r} status={self.status}>"
