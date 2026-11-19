"""统计接口测试：数据全部来自真实数据库聚合。"""

from datetime import date, timedelta

BASE_STATS = "/api/statistics"
BASE_TASKS = "/api/tasks"


def _create(client, headers, **overrides) -> dict:
    payload = {"title": "任务"}
    payload.update(overrides)
    return client.post(BASE_TASKS, json=payload, headers=headers).json()


def test_empty_statistics(client, make_user) -> None:
    headers = make_user()
    response = client.get(BASE_STATS, headers=headers).json()
    assert response["total_tasks"] == 0
    assert response["completed_tasks"] == 0
    assert response["pending_tasks"] == 0
    assert response["overdue_tasks"] == 0
    assert response["completion_rate"] == 0.0
    assert response["by_priority"] == {"urgent": 0, "high": 0, "medium": 0, "low": 0}
    assert len(response["trend"]) == 7  # 最近 7 天，全部补零


def test_statistics_counts_and_rate(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="A", priority="high")
    b = _create(client, headers, title="B", priority="high")
    _create(client, headers, title="C", priority="low")
    client.post(f"{BASE_TASKS}/{b['id']}/complete", headers=headers)

    response = client.get(BASE_STATS, headers=headers).json()
    assert response["total_tasks"] == 3
    assert response["completed_tasks"] == 1
    assert response["pending_tasks"] == 2
    assert response["completion_rate"] == round(1 / 3, 4)
    assert response["by_priority"]["high"] == 2
    assert response["by_priority"]["low"] == 1


def test_overdue_counted_only_for_todo(client, make_user) -> None:
    headers = make_user()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _create(client, headers, title="逾期未完成", due_date=yesterday)
    done_overdue = _create(client, headers, title="逾期但已完成", due_date=yesterday)
    client.post(f"{BASE_TASKS}/{done_overdue['id']}/complete", headers=headers)

    response = client.get(BASE_STATS, headers=headers).json()
    assert response["overdue_tasks"] == 1


def test_trend_reflects_today(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="今天新建")
    done = _create(client, headers, title="今天完成")
    client.post(f"{BASE_TASKS}/{done['id']}/complete", headers=headers)

    trend = client.get(BASE_STATS, headers=headers).json()["trend"]
    today = trend[-1]
    assert today["date"] == date.today().isoformat()
    assert today["created"] >= 2
    assert today["completed"] >= 1


def test_statistics_isolated_between_users(client, make_user) -> None:
    headers_a = make_user("alice")
    _create(client, headers_a, title="Alice 的任务")
    headers_b = make_user("bob")
    response = client.get(BASE_STATS, headers=headers_b).json()
    assert response["total_tasks"] == 0


def test_statistics_requires_auth(client) -> None:
    assert client.get(BASE_STATS).status_code == 401
