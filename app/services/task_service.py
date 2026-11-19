"""任务服务：CRUD、完成/恢复与数据隔离。"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.database.session import Database
from app.models.base import now_local
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreateRequest, TaskListQuery, TaskUpdateRequest


class TaskService:
    """任务业务。所有查询都强制携带 user_id，实现用户数据隔离。"""

    def __init__(self, settings: Settings, database: Database) -> None:
        self._settings = settings
        self._database = database

    def create(self, user_id: str, data: TaskCreateRequest) -> Task:
        """创建任务。"""
        with self._database.session() as session:
            task = Task(
                id=uuid.uuid4().hex,
                user_id=user_id,
                title=data.title,
                description=data.description,
                status="todo",
                priority=data.priority,
                due_date=data.due_date,
                category=data.category,
                tags=data.tags or [],
            )
            return TaskRepository(session).create(task)

    def get(self, user_id: str, task_id: str) -> Task:
        """获取单个任务；跨用户访问一律 404（不泄露存在性）。"""
        with self._database.session() as session:
            task = TaskRepository(session).get(user_id, task_id)
            if task is None:
                raise NotFoundError(f"任务不存在：{task_id}")
            return task

    def list(self, user_id: str, query: TaskListQuery) -> tuple[int, list[Task]]:
        """按条件查询任务列表。"""
        with self._database.session() as session:
            return TaskRepository(session).list(user_id, query)

    def update(self, user_id: str, task_id: str, data: TaskUpdateRequest) -> Task:
        """编辑任务：仅更新请求中出现的字段（None = 不修改）。"""
        with self._database.session() as session:
            repository = TaskRepository(session)
            task = repository.get(user_id, task_id)
            if task is None:
                raise NotFoundError(f"任务不存在：{task_id}")
            changes = data.model_dump(exclude_unset=True, exclude_none=True)
            if "status" in changes and changes["status"] != task.status:
                task.completed_at = now_local() if changes["status"] == "done" else None
            for field, value in changes.items():
                setattr(task, field, value)
            task.updated_at = now_local()
            session.flush()
            return task

    def delete(self, user_id: str, task_id: str) -> None:
        """删除任务。"""
        with self._database.session() as session:
            repository = TaskRepository(session)
            task = repository.get(user_id, task_id)
            if task is None:
                raise NotFoundError(f"任务不存在：{task_id}")
            session.delete(task)
            session.flush()

    def complete(self, user_id: str, task_id: str) -> Task:
        """完成任务：置 done 并记录完成时间（幂等）。"""
        with self._database.session() as session:
            task = self._get(session, user_id, task_id)
            if task.status != "done":
                task.status = "done"
                task.completed_at = now_local()
                task.updated_at = now_local()
            return task

    def restore(self, user_id: str, task_id: str) -> Task:
        """恢复未完成：置 todo 并清除完成时间（幂等）。"""
        with self._database.session() as session:
            task = self._get(session, user_id, task_id)
            if task.status != "todo":
                task.status = "todo"
                task.completed_at = None
                task.updated_at = now_local()
            return task

    @staticmethod
    def _get(session: Session, user_id: str, task_id: str) -> Task:
        task = TaskRepository(session).get(user_id, task_id)
        if task is None:
            raise NotFoundError(f"任务不存在：{task_id}")
        return task
