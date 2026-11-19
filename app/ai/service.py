"""AI 业务服务：任务拆解与每日计划。

- 拆解只生成预览（不入库），用户确认后由 confirm_breakdown 保存为任务；
- 每日计划基于用户真实未完成任务构建 Prompt，且只接受模型引用的真实 id；
- 未配置 AI（三项环境变量不齐）时抛 AINotConfiguredError，由 API 返回 400。
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx

from app.ai.client import AIClient
from app.ai.prompts import BREAKDOWN_SYSTEM, DAILY_PLAN_SYSTEM, extract_json
from app.core.config import Settings
from app.core.errors import AINotConfiguredError, AIResponseError
from app.core.logging import get_logger
from app.database.session import Database
from app.models.base import now_local
from app.models.task import TASK_PRIORITIES, Task
from app.repositories.task_repository import TaskRepository
from app.schemas.ai import (
    BreakdownConfirmItem,
    BreakdownItem,
    DailyPlanFocus,
    DailyPlanResponse,
)
from app.schemas.task import TaskListQuery

logger = get_logger(__name__)

#: 从今天起算时允许的最大天数（防止模型输出离谱值）
_MAX_DUE_IN_DAYS = 365
#: 单次计划最多参考的未完成任务数
_MAX_PLAN_TASKS = 50


class AIService:
    """AI 业务服务。transport 仅供测试注入（httpx.MockTransport）。"""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._transport = transport

    # ------------------------------------------------------------------ 内部
    def _client(self) -> AIClient:
        """构造客户端；未配置时抛 400（不发起任何网络请求）。"""
        if not self._settings.ai_configured:
            raise AINotConfiguredError(
                "AI 未配置：请在 .env 中设置 AI_BASE_URL、AI_API_KEY、AI_MODEL 后重启服务。"
                "未配置 AI 时，任务管理功能不受影响。"
            )
        return AIClient(
            base_url=self._settings.ai_base_url or "",
            api_key=self._settings.ai_api_key or "",
            model=self._settings.ai_model or "",
            timeout=self._settings.ai_timeout_seconds,
            transport=self._transport,
        )

    # ------------------------------------------------------------------ 拆解
    def breakdown(self, goal: str) -> list[BreakdownItem]:
        """把目标拆解为子任务预览（不入库）。"""
        content = self._client().chat(
            [
                {"role": "system", "content": BREAKDOWN_SYSTEM},
                {"role": "user", "content": f"目标：{goal}"},
            ]
        )
        try:
            raw_items = extract_json(content)["items"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AIResponseError("AI 返回的任务拆解格式无法解析，请重试") from exc
        if not isinstance(raw_items, list):
            raise AIResponseError("AI 返回的 items 不是数组")

        items: list[BreakdownItem] = []
        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            priority = str(entry.get("priority", "medium"))
            items.append(
                BreakdownItem(
                    title=title[:200],
                    description=str(entry.get("description", ""))[:500],
                    priority=priority if priority in TASK_PRIORITIES else "medium",
                    due_in_days=_as_non_negative_int(entry.get("due_in_days"), 0),
                    estimated_minutes=_as_positive_int(entry.get("estimated_minutes"), 60),
                    order=len(items) + 1,
                )
            )
        if not items:
            raise AIResponseError("AI 未返回有效的子任务，请重试或换一种目标描述")
        logger.info("AI 拆解完成：%d 个子任务", len(items))
        return items[:20]

    def confirm_breakdown(
        self, user_id: str, items: list[BreakdownConfirmItem]
    ) -> list[Task]:
        """把用户确认（可能已修改）的拆解项批量保存为任务。"""
        tasks: list[Task] = []
        with self._database.session() as session:
            repository = TaskRepository(session)
            for item in items:
                task = Task(
                    id=uuid.uuid4().hex,
                    user_id=user_id,
                    title=item.title,
                    description=item.description,
                    status="todo",
                    priority=item.priority,
                    due_date=item.due_date,
                    category=item.category or "AI 拆解",
                    tags=item.tags or ["AI"],
                    completed_at=None,
                )
                repository.create(task)
                tasks.append(task)
            logger.info("AI 拆解确认：用户 %s 新增 %d 个任务", user_id, len(tasks))
        return tasks

    # ------------------------------------------------------------------ 每日计划
    def daily_plan(self, user_id: str) -> DailyPlanResponse:
        """基于用户真实未完成任务生成今日计划；无待办时不调用模型。"""
        today = now_local().date()
        plan_query = TaskListQuery(
            status="todo", sort_by="due_date", order="asc", limit=_MAX_PLAN_TASKS
        )
        with self._database.session() as session:
            _, pending = TaskRepository(session).list(user_id, plan_query)
        if not pending:
            return DailyPlanResponse(
                daily_goal="当前没有未完成的任务，先去添加几个吧。",
                focus=[],
                overdue_reminders=[],
                source_count=0,
            )

        task_map = {task.id: task for task in pending}
        listing = "\n".join(
            f"- id: {task.id} | 标题: {task.title} | 优先级: {task.priority} | "
            f"截止: {task.due_date.isoformat() if task.due_date else '无'} | "
            f"{'已逾期' if _is_overdue(task, today) else '未逾期'}"
            for task in pending
        )
        content = self._client().chat(
            [
                {"role": "system", "content": DAILY_PLAN_SYSTEM},
                {
                    "role": "user",
                    "content": f"今天是 {today.isoformat()}。我的未完成任务：\n{listing}",
                },
            ]
        )
        focus, daily_goal = self._parse_plan(content, task_map)

        overdue_reminders = [
            f"任务「{task.title}」已逾期 {(today - task.due_date).days} 天（截止 "
            f"{task.due_date.isoformat()}），建议尽快处理或调整截止日期。"
            for task in pending
            if _is_overdue(task, today)
        ]
        return DailyPlanResponse(
            daily_goal=daily_goal,
            focus=focus[:5],
            overdue_reminders=overdue_reminders,
            source_count=len(pending),
        )

    def _parse_plan(
        self, content: str, task_map: dict[str, Task]
    ) -> tuple[list[DailyPlanFocus], str]:
        """解析每日计划；只保留引用了真实任务 id 的 focus（过滤模型幻觉）。"""
        try:
            raw = extract_json(content)
            daily_goal = str(raw["daily_goal"]).strip() or "完成今天的重点任务"
            raw_focus = raw["focus"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AIResponseError("AI 返回的每日计划格式无法解析，请重试") from exc

        focus: list[DailyPlanFocus] = []
        seen: set[str] = set()
        for entry in raw_focus:
            if not isinstance(entry, dict):
                continue
            task_id = str(entry.get("task_id", ""))
            task = task_map.get(task_id)
            if task is None or task_id in seen:
                continue  # 过滤模型编造或重复的任务 id
            seen.add(task_id)
            focus.append(
                DailyPlanFocus(
                    task_id=task_id,
                    task_title=task.title,
                    reason=str(entry.get("reason", ""))[:200],
                    time_slot=str(entry.get("time_slot", ""))[:64],
                )
            )
        if not focus:
            raise AIResponseError("AI 未能给出有效的今日安排，请重试")
        return focus, daily_goal


def _is_overdue(task: Task, today: date) -> bool:
    """未完成且截止日期早于今天（按本地日历）。"""
    return task.status == "todo" and task.due_date is not None and task.due_date < today


def _as_non_negative_int(value: object, default: int) -> int:
    """宽容解析模型输出的整数：非法值回退默认，负数取 0，并限制上限。"""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(0, min(number, _MAX_DUE_IN_DAYS))


def _as_positive_int(value: object, default: int) -> int:
    """耗时分钟数：非法回退默认，限制在 5-480 分钟。"""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(5, min(number, 480))
