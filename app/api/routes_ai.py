"""AI 接口：任务拆解（预览→确认）与每日计划。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AIService, CurrentUser, get_ai_service
from app.schemas.ai import (
    BreakdownRequest,
    BreakdownResponse,
    ConfirmRequest,
    ConfirmResponse,
    DailyPlanResponse,
)
from app.schemas.task import TaskOut

router = APIRouter()


@router.post(
    "/breakdown",
    response_model=BreakdownResponse,
    summary="AI 拆解目标（仅返回预览，不写入数据库）",
    responses={
        400: {"description": "AI 未配置"},
        502: {"description": "AI 服务错误或返回格式无法解析"},
        504: {"description": "AI 服务超时"},
    },
)
def breakdown(
    data: BreakdownRequest,
    user: CurrentUser,
    service: AIService = Depends(get_ai_service),
) -> BreakdownResponse:
    """把目标拆解为子任务预览；用户可在前端修改后调用 confirm 保存。"""
    return BreakdownResponse(goal=data.goal, items=service.breakdown(data.goal))


@router.post(
    "/breakdown/confirm",
    response_model=ConfirmResponse,
    summary="确认拆解结果并批量保存为任务",
)
def confirm_breakdown(
    data: ConfirmRequest,
    user: CurrentUser,
    service: AIService = Depends(get_ai_service),
) -> ConfirmResponse:
    """把用户确认（可能已修改）的子任务批量保存为当前用户的任务。"""
    tasks = service.confirm_breakdown(user.id, data.items)
    return ConfirmResponse(created=len(tasks), tasks=[TaskOut.model_validate(t) for t in tasks])


@router.post(
    "/daily-plan",
    response_model=DailyPlanResponse,
    summary="基于真实未完成任务生成 AI 每日计划",
    responses={
        400: {"description": "AI 未配置，或当前没有未完成任务"},
        502: {"description": "AI 服务错误或返回格式无法解析"},
        504: {"description": "AI 服务超时"},
    },
)
def daily_plan(
    user: CurrentUser,
    service: AIService = Depends(get_ai_service),
) -> DailyPlanResponse:
    """读取当前用户真实未完成任务，交给模型排期；只接受真实任务 id。"""
    return service.daily_plan(user.id)
