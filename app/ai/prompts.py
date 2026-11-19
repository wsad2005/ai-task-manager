"""Prompt 模板与 JSON 提取。

设计要点：
- 要求模型只输出纯 JSON（容忍 ```json 围栏与前后说明文字）；
- 拆解使用“相对天数 due_in_days”而不是绝对日期，避免模型编造日期；
- 每日计划只允许引用服务端提供的真实任务 id，幻觉 id 在服务端过滤。
"""

from __future__ import annotations

import json
from typing import Any

BREAKDOWN_SYSTEM = """你是任务规划助手。用户会给出一个目标，请把它拆解为可执行的子任务。
只输出纯 JSON，不要 markdown 代码块，不要任何解释文字，结构如下：
{"items": [{"title": "子任务标题(不超过100字)", "description": "具体做什么(不超过200字)",
"priority": "low|medium|high|urgent 之一", "due_in_days": 从今天起的天数(非负整数),
"estimated_minutes": 预计耗时分钟数(正整数)}]}
要求：拆解为 5-8 个子任务，按执行顺序排列；标题必须具体可执行；使用简体中文。"""

DAILY_PLAN_SYSTEM = """你是个人日程助手。你会收到用户真实的未完成任务列表
（含 id、标题、优先级、截止日期、是否逾期）。
只输出纯 JSON，不要 markdown 代码块，结构如下：
{"daily_goal": "今日总目标(一句话)", "focus": [{"task_id": "只能使用列表中出现过的 id",
"reason": "为什么今天做它(一句话)", "time_slot": "建议时间段(如 09:00-10:30)"}]}
要求：优先安排逾期和临近截止的任务；focus 数量 1-5 个；使用简体中文。"""


def extract_json(content: str) -> Any:
    """从模型输出提取 JSON 对象；容忍 ```json 围栏与前后说明文字。"""
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("输出中不包含 JSON 对象")
    return json.loads(text[start : end + 1])
