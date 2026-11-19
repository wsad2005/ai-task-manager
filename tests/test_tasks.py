"""任务 CRUD、筛选排序分页、完成/恢复与数据隔离测试。"""

from datetime import date, timedelta

BASE = "/api/tasks"


def _create(client, headers, **overrides) -> dict:
    payload = {"title": "任务", "description": "描述"}
    payload.update(overrides)
    response = client.post(BASE, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_task_with_defaults(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers, title="写周报")
    assert task["title"] == "写周报"
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["tags"] == []
    assert task["overdue"] is False
    assert task["completed_at"] is None


def test_get_task_detail(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers)
    response = client.get(f"{BASE}/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == task["id"]


def test_patch_updates_only_given_fields(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers, description="旧描述", priority="low")
    response = client.patch(
        f"{BASE}/{task['id']}", json={"priority": "urgent"}, headers=headers
    )
    body = response.json()
    assert body["priority"] == "urgent"
    assert body["description"] == "旧描述"  # 未提供字段保持不变


def test_patch_cannot_blank_title(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers)
    response = client.patch(f"{BASE}/{task['id']}", json={"title": "   "}, headers=headers)
    assert response.status_code == 422


def test_delete_then_get_404(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers)
    assert client.delete(f"{BASE}/{task['id']}", headers=headers).status_code == 204
    assert client.get(f"{BASE}/{task['id']}", headers=headers).status_code == 404


def test_complete_and_restore(client, make_user) -> None:
    headers = make_user()
    task = _create(client, headers)
    done = client.post(f"{BASE}/{task['id']}/complete", headers=headers).json()
    assert done["status"] == "done"
    assert done["completed_at"] is not None
    restored = client.post(f"{BASE}/{task['id']}/restore", headers=headers).json()
    assert restored["status"] == "todo"
    assert restored["completed_at"] is None


def test_user_data_isolation(client, make_user) -> None:
    headers_a = make_user("alice")
    headers_b = make_user("bob")
    task = _create(client, headers_a, title="Alice 的任务")

    # Alice 正常访问
    assert client.get(f"{BASE}/{task['id']}", headers=headers_a).status_code == 200
    # Bob 的列表为空，且无法查看、修改、删除 Alice 的任务（统一 404，不泄露存在性）
    assert client.get(BASE, headers=headers_b).json()["total"] == 0
    assert client.get(f"{BASE}/{task['id']}", headers=headers_b).status_code == 404
    assert client.patch(
        f"{BASE}/{task['id']}", json={"title": "篡改"}, headers=headers_b
    ).status_code == 404
    assert client.delete(f"{BASE}/{task['id']}", headers=headers_b).status_code == 404


def test_list_requires_auth(client) -> None:
    assert client.get(BASE).status_code == 401


def test_filters_by_status_and_priority(client, make_user) -> None:
    headers = make_user()
    a = _create(client, headers, title="A", priority="low")
    client.post(f"{BASE}/{a['id']}/complete", headers=headers)
    _create(client, headers, title="B", priority="urgent")
    _create(client, headers, title="C", priority="urgent")

    done = client.get(f"{BASE}?status=done", headers=headers).json()
    assert done["total"] == 1 and done["items"][0]["title"] == "A"
    urgent_todo = client.get(
        f"{BASE}?status=todo&priority=urgent", headers=headers
    ).json()
    assert urgent_todo["total"] == 2


def test_search_keyword_with_wildcard_escaping(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="进度 50%报告")
    _create(client, headers, title="进度 50X报告")

    hit = client.get(f"{BASE}?q=50%", headers=headers).json()
    assert hit["total"] == 1  # % 被转义，不会匹配 50X
    hit_underscore = client.get(f"{BASE}?q=50_报", headers=headers).json()
    assert hit_underscore["total"] == 0  # _ 同样被转义


def test_search_description_too(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="任务一", description="关键词藏在描述里")
    assert client.get(f"{BASE}?q=藏在描述", headers=headers).json()["total"] == 1


def test_overdue_filter_and_flag(client, make_user) -> None:
    headers = make_user()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _create(client, headers, title="已逾期", due_date=yesterday)
    _create(
        client,
        headers,
        title="未逾期",
        due_date=(date.today() + timedelta(days=3)).isoformat(),
    )

    response = client.get(f"{BASE}?overdue=true", headers=headers).json()
    assert response["total"] == 1
    assert response["items"][0]["title"] == "已逾期"
    assert response["items"][0]["overdue"] is True


def test_due_date_range_filter(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="这周", due_date=date.today().isoformat())
    _create(client, headers, title="下月", due_date=(date.today() + timedelta(days=30)).isoformat())
    response = client.get(
        f"{BASE}?due_before={date.today().isoformat()}", headers=headers
    ).json()
    assert response["total"] == 1
    assert response["items"][0]["title"] == "这周"


def test_pagination_and_sort(client, make_user) -> None:
    headers = make_user()
    for index in range(5):
        _create(client, headers, title=f"任务{index}")

    page = client.get(f"{BASE}?skip=1&limit=2&sort_by=created_at&order=asc", headers=headers).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert [item["title"] for item in page["items"]] == ["任务1", "任务2"]


def test_sort_by_priority(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="低", priority="low")
    _create(client, headers, title="紧急", priority="urgent")
    _create(client, headers, title="中", priority="medium")
    response = client.get(f"{BASE}?sort_by=priority&order=asc", headers=headers).json()
    assert [item["priority"] for item in response["items"]] == ["urgent", "medium", "low"]


def test_filter_by_category(client, make_user) -> None:
    headers = make_user()
    _create(client, headers, title="工作", category="work")
    _create(client, headers, title="生活", category="life")
    response = client.get(f"{BASE}?category=work", headers=headers).json()
    assert response["total"] == 1
    assert response["items"][0]["title"] == "工作"
