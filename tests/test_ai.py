"""AI 功能测试：全部使用 httpx.MockTransport，绝不真实调用付费 API。"""

import json

import httpx
import pytest

from app.ai.service import AIService
from app.core.config import Settings
from app.database.migrations import run_migrations
from app.database.session import Database

BASE_ENV = {
    "AI_BASE_URL": "https://ai.example.invalid/v1",  # 测试用假地址
    "AI_API_KEY": "dummy-ai-key-abcdef123456",  # 测试用假密钥
    "AI_MODEL": "dummy-model",  # 测试用假模型名
}


def make_service(handler, tmp_path) -> tuple[AIService, Database]:
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        log_level="WARNING",
        ai_base_url=BASE_ENV["AI_BASE_URL"],
        ai_api_key=BASE_ENV["AI_API_KEY"],
        ai_model=BASE_ENV["AI_MODEL"],
    )
    run_migrations(settings)  # 建目录 + 建表（与生产同一迁移路径）
    database = Database(settings)
    return AIService(settings, database, transport=httpx.MockTransport(handler)), database


def _seed_user(database: Database, user_id: str, username: str) -> None:
    """创建真实用户行：tasks.user_id 有外键约束，测试必须先有用户。"""
    from app.core.security import hash_password
    from app.models.user import User

    with database.session() as session:
        session.add(
            User(id=user_id, username=username, password_hash=hash_password("password123"))
        )


def chat_handler(content: str):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path.endswith("/chat/completions")
        assert "dummy-ai-key-abcdef123456" not in str(request.url)  # 密钥只在请求头
        assert request.headers["Authorization"] == "Bearer dummy-ai-key-abcdef123456"
        assert body["model"] == "dummy-model"
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
        )

    return handler


BREAKDOWN_JSON = json.dumps(
    {
        "items": [
            {
                "title": "复习 FastAPI 基础",
                "description": "路由、依赖注入、Pydantic",
                "priority": "high",
                "due_in_days": 7,
                "estimated_minutes": 120,
            },
            {
                "title": "完成一个练手项目",
                "description": "综合运用",
                "priority": "medium",
                "due_in_days": 21,
                "estimated_minutes": 300,
            },
        ]
    },
    ensure_ascii=False,
)


def test_breakdown_success_parses_items(tmp_path) -> None:
    service, database = make_service(chat_handler(BREAKDOWN_JSON), tmp_path)
    items = service.breakdown("准备一个月后的 Python 后端面试")
    database.dispose()
    assert len(items) == 2
    assert items[0].title == "复习 FastAPI 基础"
    assert items[0].priority == "high"
    assert items[0].order == 1
    # 相对天数换算为建议截止日期：due_in_days 相差 14 天，截止日期也应相差 14 天
    assert (items[1].suggested_due_date - items[0].suggested_due_date).days == 14


def test_breakdown_tolerates_markdown_fence(tmp_path) -> None:
    fenced = "```json\n" + BREAKDOWN_JSON + "\n```"
    service, database = make_service(chat_handler(fenced), tmp_path)
    assert len(service.breakdown("目标")) == 2
    database.dispose()


def test_breakdown_invalid_json_maps_to_response_error(tmp_path) -> None:
    service, database = make_service(chat_handler("这不是 JSON"), tmp_path)
    with pytest.raises(Exception) as excinfo:  # noqa: PT011 - 断言具体类型见下
        service.breakdown("目标")
    assert excinfo.value.code == "ai_response_error"
    database.dispose()


def test_breakdown_empty_items_maps_to_response_error(tmp_path) -> None:
    service, database = make_service(chat_handler('{"items": []}'), tmp_path)
    with pytest.raises(Exception) as excinfo:
        service.breakdown("目标")
    assert excinfo.value.code == "ai_response_error"
    database.dispose()


def test_breakdown_invalid_priority_falls_back_to_medium(tmp_path) -> None:
    payload = json.dumps(
        {"items": [{"title": "任务", "priority": "超高", "due_in_days": 3}]}, ensure_ascii=False
    )
    service, database = make_service(chat_handler(payload), tmp_path)
    items = service.breakdown("目标")
    database.dispose()
    assert items[0].priority == "medium"


def test_confirm_breakdown_creates_tasks(tmp_path) -> None:
    from datetime import date

    from app.schemas.ai import BreakdownConfirmItem

    service, database = make_service(chat_handler(BREAKDOWN_JSON), tmp_path)
    _seed_user(database, "user-1", "alice")
    tasks = service.confirm_breakdown(
        "user-1",
        [
            BreakdownConfirmItem(title="复习 FastAPI", priority="high", due_date=date(2026, 12, 1)),
            BreakdownConfirmItem(title="练手项目", priority="medium"),
        ],
    )
    database.dispose()
    assert len(tasks) == 2
    assert tasks[0].category == "AI 拆解"
    assert tasks[0].status == "todo"


def test_daily_plan_requires_pending_tasks(tmp_path) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)  # 无待办任务时绝不应调用模型
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    service, database = make_service(handler, tmp_path)
    plan = service.daily_plan("nobody")
    database.dispose()
    assert plan.source_count == 0
    assert plan.focus == []
    assert calls == []  # 证明没有发起模型调用


def test_daily_plan_filters_hallucinated_ids(tmp_path) -> None:
    from datetime import date

    service, database = make_service(chat_handler(BREAKDOWN_JSON), tmp_path)
    _seed_user(database, "user-1", "alice")
    # 预置一个真实任务
    with database.session() as session:
        from app.models.task import Task

        session.add(
            Task(
                id="real-1",
                user_id="user-1",
                title="真实任务",
                status="todo",
                priority="high",
                due_date=date.today(),
            )
        )

    plan_json = json.dumps(
        {
            "daily_goal": "推进面试准备",
            "focus": [
                {"task_id": "real-1", "reason": "优先级高", "time_slot": "09:00-10:30"},
                {
                    "task_id": "hallucinated-id",
                    "reason": "不存在的任务",
                    "time_slot": "10:30-11:00",
                },
            ],
        },
        ensure_ascii=False,
    )
    # 拆解与计划共用同一服务：这里直接用一个返回计划 JSON 的 transport
    service._transport = httpx.MockTransport(chat_handler(plan_json))  # noqa: SLF001
    plan = service.daily_plan("user-1")
    database.dispose()
    assert plan.source_count == 1
    assert [item.task_id for item in plan.focus] == ["real-1"]
    assert plan.focus[0].task_title == "真实任务"


def test_daily_plan_timeout_maps_to_ai_timeout(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    service, database = make_service(handler, tmp_path)
    _seed_user(database, "user-1", "alice")
    with database.session() as session:
        from app.models.task import Task

        session.add(Task(id="t1", user_id="user-1", title="任务", status="todo"))
    with pytest.raises(Exception) as excinfo:
        service.daily_plan("user-1")
    database.dispose()
    assert excinfo.value.code == "ai_timeout"


def test_ai_routes_require_auth(client) -> None:
    assert client.post("/api/ai/breakdown", json={"goal": "目标"}).status_code == 401
    assert client.post("/api/ai/daily-plan").status_code == 401


def test_breakdown_without_ai_config_is_clear_error(client, settings) -> None:
    # 测试设置未配置 AI：应返回 400 与明确的 ai_not_configured 提示，且不发起网络请求
    response = client.post("/api/ai/breakdown", json={"goal": "准备面试"}, headers=_headers(client))
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "ai_not_configured"
    assert "AI_BASE_URL" in body["message"]


def test_daily_plan_without_ai_config_is_clear_error(client) -> None:
    headers = _headers(client)
    # 先创建一个未完成任务：此时生成计划必须用 AI，未配置应得到明确的 400 提示
    assert client.post(
        "/api/tasks", json={"title": "有待办任务"}, headers=headers
    ).status_code == 201
    response = client.post("/api/ai/daily-plan", headers=headers)
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "ai_not_configured"
    assert "AI_BASE_URL" in body["message"]


def _headers(client) -> dict[str, str]:
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
