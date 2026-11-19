"""任务相关请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

TaskStatusLiteral = Literal["todo", "done"]
TaskPriorityLiteral = Literal["low", "medium", "high", "urgent"]
SortFieldLiteral = Literal["created_at", "updated_at", "due_date", "priority", "title"]
OrderLiteral = Literal["asc", "desc"]

_MAX_TAGS = 20
_TAG_MAX_LENGTH = 32


class TagListValidatorMixin(BaseModel):
    """tags 公共校验：去重、限长、限量。"""

    @field_validator("tags", check_fields=False)
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned: list[str] = []
        for tag in value:
            text = tag.strip()
            if not text:
                continue
            if len(text) > _TAG_MAX_LENGTH:
                raise ValueError(f"单个标签最长 {_TAG_MAX_LENGTH} 个字符")
            if text not in cleaned:
                cleaned.append(text)
        if len(cleaned) > _MAX_TAGS:
            raise ValueError(f"标签最多 {_MAX_TAGS} 个")
        return cleaned


class TaskCreateRequest(TagListValidatorMixin, BaseModel):
    """创建任务请求。"""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: TaskPriorityLiteral = "medium"
    due_date: date | None = None
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("标题不能为空白")
        return stripped

    @field_validator("category")
    @classmethod
    def _clean_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskUpdateRequest(TagListValidatorMixin, BaseModel):
    """编辑任务请求：仅更新出现的字段（None = 不修改）。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: TaskPriorityLiteral | None = None
    due_date: date | None = None
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None
    status: TaskStatusLiteral | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("标题不能为空白")
        return stripped

    @field_validator("category")
    @classmethod
    def _clean_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TaskOut(BaseModel):
    """任务响应：overdue 为服务端计算的逾期标记。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: TaskStatusLiteral
    priority: TaskPriorityLiteral
    due_date: date | None
    category: str | None
    tags: list[str]
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field(return_type=bool)
    @property
    def overdue(self) -> bool:
        """未完成且截止日期早于今天 = 逾期。"""
        return self.status != "done" and self.due_date is not None and self.due_date < date.today()


class TaskListResponse(BaseModel):
    """分页任务列表。"""

    total: int
    skip: int
    limit: int
    items: list[TaskOut]


class TaskListQuery(BaseModel):
    """任务列表的查询参数（GET /api/tasks）。"""

    status: TaskStatusLiteral | None = None
    priority: TaskPriorityLiteral | None = None
    category: str | None = Field(default=None, max_length=64)
    q: str | None = Field(default=None, max_length=100, description="标题/描述关键词")
    overdue: bool | None = None
    due_before: date | None = None
    due_after: date | None = None
    sort_by: SortFieldLiteral = "created_at"
    order: OrderLiteral = "desc"
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def _check_q(self) -> TaskListQuery:
        if self.q is not None:
            self.q = self.q.strip() or None
        if self.category is not None:
            self.category = self.category.strip() or None
        return self
