"""任务接口：CRUD、完成/恢复、筛选排序分页。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, TaskService, get_task_service
from app.schemas.task import (
    TaskCreateRequest,
    TaskListQuery,
    TaskListResponse,
    TaskOut,
    TaskUpdateRequest,
)

router = APIRouter()


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建任务",
)
def create_task(
    data: TaskCreateRequest,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    """为当前用户创建任务。"""
    return TaskOut.model_validate(service.create(user.id, data))


@router.get(
    "",
    response_model=TaskListResponse,
    summary="任务列表（筛选/搜索/排序/分页）",
)
def list_tasks(
    user: CurrentUser,
    query: Annotated[TaskListQuery, Query()],
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """支持按状态/优先级/分类筛选、关键词搜索、逾期过滤、截止日期区间、排序与分页。"""
    total, tasks = service.list(user.id, query)
    return TaskListResponse(
        total=total,
        skip=query.skip,
        limit=query.limit,
        items=[TaskOut.model_validate(task) for task in tasks],
    )


@router.get(
    "/{task_id}",
    response_model=TaskOut,
    summary="任务详情",
    responses={404: {"description": "任务不存在或不属于当前用户"}},
)
def get_task(
    task_id: str,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    """获取当前用户的任务详情；跨用户访问返回 404。"""
    return TaskOut.model_validate(service.get(user.id, task_id))


@router.patch(
    "/{task_id}",
    response_model=TaskOut,
    summary="编辑任务（仅更新出现的字段）",
    responses={404: {"description": "任务不存在或不属于当前用户"}},
)
def update_task(
    task_id: str,
    data: TaskUpdateRequest,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    """部分更新任务字段；status 也可通过本接口修改。"""
    return TaskOut.model_validate(service.update(user.id, task_id, data))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除任务",
    responses={404: {"description": "任务不存在或不属于当前用户"}},
)
def delete_task(
    task_id: str,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> None:
    """删除当前用户的任务。"""
    service.delete(user.id, task_id)


@router.post(
    "/{task_id}/complete",
    response_model=TaskOut,
    summary="完成任务",
)
def complete_task(
    task_id: str,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    """将任务置为 done 并记录完成时间（幂等）。"""
    return TaskOut.model_validate(service.complete(user.id, task_id))


@router.post(
    "/{task_id}/restore",
    response_model=TaskOut,
    summary="恢复为未完成",
)
def restore_task(
    task_id: str,
    user: CurrentUser,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    """将任务置为 todo 并清除完成时间（幂等）。"""
    return TaskOut.model_validate(service.restore(user.id, task_id))
