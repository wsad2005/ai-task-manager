"""任务仓储：过滤、排序、分页与统计聚合都在这里实现。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import String, case, func, select
from sqlalchemy.orm import Session

from app.models.task import PRIORITY_RANK, Task
from app.schemas.task import TaskListQuery

_SORT_COLUMNS = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "due_date": Task.due_date,
    "title": Task.title,
}


def _escape_like(keyword: str) -> str:
    """转义 LIKE 通配符，防止用户输入 %/_ 干扰匹配。"""
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TaskRepository:
    """任务表数据访问。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, task: Task) -> Task:
        """写入任务（调用方负责提交事务）。"""
        self._session.add(task)
        self._session.flush()
        return task

    def get(self, user_id: str, task_id: str) -> Task | None:
        """按 id 查询；强制限定 user_id 实现数据隔离。"""
        return self._session.scalar(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )

    def list(self, user_id: str, query: TaskListQuery) -> tuple[int, list[Task]]:
        """按条件过滤 + 排序 + 分页，返回 (总数, 任务列表)。"""
        conditions = [Task.user_id == user_id]
        if query.status is not None:
            conditions.append(Task.status == query.status)
        if query.priority is not None:
            conditions.append(Task.priority == query.priority)
        if query.category is not None:
            conditions.append(Task.category == query.category)
        if query.overdue:
            conditions.append(Task.status == "todo")
            conditions.append(Task.due_date < date.today())
        if query.due_before is not None:
            conditions.append(Task.due_date <= query.due_before)
        if query.due_after is not None:
            conditions.append(Task.due_date >= query.due_after)
        if query.q:
            escaped = f"%{_escape_like(query.q)}%"
            conditions.append(
                Task.title.like(escaped, escape="\\") | Task.description.like(escaped, escape="\\")
            )

        where = [*conditions]
        total = self._session.scalar(
            select(func.count()).select_from(Task).where(*where)
        ) or 0
        rows = self._session.scalars(
            select(Task)
            .where(*where)
            .order_by(*self._order_by(query.sort_by, query.order), Task.created_at.desc())
            .offset(query.skip)
            .limit(query.limit)
        ).all()
        return int(total), list(rows)

    def counts(self, user_id: str) -> dict[str, int]:
        """统计聚合：总量/已完成/待办/逾期/按优先级。"""
        today = date.today()
        total = self._session.scalar(
            select(func.count()).select_from(Task).where(Task.user_id == user_id)
        ) or 0
        completed = self._session.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.user_id == user_id, Task.status == "done")
        ) or 0
        overdue = self._session.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.status == "todo",
                Task.due_date < today,
            )
        ) or 0
        by_priority_rows = self._session.execute(
            select(Task.priority, func.count())
            .where(Task.user_id == user_id)
            .group_by(Task.priority)
        ).all()
        return {
            "total": int(total),
            "completed": int(completed),
            "pending": int(total) - int(completed),
            "overdue": int(overdue),
            "by_priority": {row[0]: int(row[1]) for row in by_priority_rows},
        }

    def trend(self, user_id: str, days: list[date]) -> dict[date, tuple[int, int]]:
        """最近若干天的 (新建数, 完成数)，按自然日聚合。"""
        created_rows = self._session.execute(
            select(func.date(Task.created_at).cast(String), func.count())
            .where(Task.user_id == user_id)
            .group_by(func.date(Task.created_at))
        ).all()
        completed_rows = self._session.execute(
            select(func.date(Task.completed_at).cast(String), func.count())
            .where(Task.user_id == user_id, Task.completed_at.is_not(None))
            .group_by(func.date(Task.completed_at))
        ).all()
        created_map = {row[0]: int(row[1]) for row in created_rows}
        completed_map = {row[0]: int(row[1]) for row in completed_rows}
        return {
            day: (created_map.get(day.isoformat(), 0), completed_map.get(day.isoformat(), 0))
            for day in days
        }

    @staticmethod
    def _order_by(sort_by: str, order: str) -> list[object]:
        """构造排序子句；priority 按语义权重（urgent 最前）。"""
        direction = "desc" if order == "desc" else "asc"
        if sort_by == "priority":
            column = case(
                dict(PRIORITY_RANK),
                value=Task.priority,
                else_=len(PRIORITY_RANK),
            )
            return [column.desc() if direction == "desc" else column.asc()]
        column = _SORT_COLUMNS.get(sort_by, Task.created_at)
        return [column.desc() if direction == "desc" else column.asc()]
