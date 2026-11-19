"""可选开发脚本：用 Playwright 抓取真实运行界面的截图（README 用图）。

前置：
    1. 先启动服务：``python -m uvicorn app.main:app --port 8000``
    2. 安装截图工具（不属于项目运行时依赖）：
       ``python -m pip install playwright && python -m playwright install chromium``

用法：
    ``python -m scripts.capture_screenshots``

脚本幂等：通过 API 复位演示数据（登录 demo-shots 用户 → 清旧任务 → 建 4 个演示任务，
其中一个已完成、一个已逾期），再经真实登录界面进入应用逐视图截图。
输出到 ``docs/screenshots/``。
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
USERNAME = "demo-shots"
PASSWORD = "demo-shots-password-123"

VIEW_DESKTOP = {"width": 1280, "height": 800}
VIEW_MOBILE = {"width": 390, "height": 844}


def seed_demo_data() -> None:
    """通过 API 复位演示数据：创建用户、清理旧任务、写入 4 个演示任务。"""
    with httpx.Client(base_url=BASE, timeout=30) as client:
        register = client.post(
            "/api/auth/register", json={"username": USERNAME, "password": PASSWORD}
        )
        print("创建演示用户:", register.status_code, "（409 = 已存在，继续登录）")
        token = client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        existing = client.get("/api/tasks", params={"limit": 100}, headers=headers).json()["items"]
        for task in existing:
            client.delete(f"/api/tasks/{task['id']}", headers=headers)
        print(f"已清理 {len(existing)} 个旧演示任务")

        today = date.today()
        demo_tasks = [
            {"title": "整理求职作品集", "priority": "urgent", "category": "求职",
             "due_date": (today - timedelta(days=1)).isoformat(), "tags": ["简历"]},
            {"title": "完成 FastAPI 学习笔记", "priority": "high", "category": "学习",
             "due_date": (today + timedelta(days=5)).isoformat(), "tags": ["python", "后端"]},
            {"title": "每周跑步三次", "priority": "low", "category": "健康",
             "due_date": (today + timedelta(days=20)).isoformat()},
            {"title": "阅读《流畅的 Python》第 1-3 章", "priority": "medium",
             "category": "学习", "status": "done"},
        ]
        for demo_task in demo_tasks:
            status = demo_task.pop("status", None)
            response = client.post("/api/tasks", json=demo_task, headers=headers)
            task_id = response.json()["id"]
            if status == "done":
                client.post(f"/api/tasks/{task_id}/complete", headers=headers)
            print("创建演示任务:", response.status_code, demo_task["title"])


def capture() -> None:
    """登录真实界面，逐视图截图。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        page = browser.new_page(viewport=VIEW_DESKTOP)
        page.goto(BASE)
        page.screenshot(path=str(OUT_DIR / "01-login.png"))
        print("已保存 01-login.png")

        page.fill("#auth-form input[name=username]", USERNAME)
        page.fill("#auth-form input[name=password]", PASSWORD)
        page.click("#auth-submit")
        page.wait_for_selector("#view-dashboard:not(.hidden)")
        page.screenshot(path=str(OUT_DIR / "02-dashboard.png"))
        print("已保存 02-dashboard.png")

        page.click('button[data-view="tasks"]')
        page.wait_for_selector(".task-item")
        page.screenshot(path=str(OUT_DIR / "03-tasks.png"), full_page=True)
        print("已保存 03-tasks.png")

        page.click("#new-task-btn")
        page.wait_for_selector("#task-dialog[open]")
        page.screenshot(path=str(OUT_DIR / "04-task-dialog.png"))
        page.click("#task-cancel")
        print("已保存 04-task-dialog.png")

        mobile = browser.new_page(viewport=VIEW_MOBILE)
        mobile.goto(BASE)
        mobile.fill("#auth-form input[name=username]", USERNAME)
        mobile.fill("#auth-form input[name=password]", PASSWORD)
        mobile.click("#auth-submit")
        mobile.wait_for_selector("#view-dashboard:not(.hidden)")
        mobile.click('button[data-view="tasks"]')
        mobile.wait_for_selector(".task-item")
        mobile.screenshot(path=str(OUT_DIR / "05-mobile.png"), full_page=True)
        print("已保存 05-mobile.png")

        browser.close()


if __name__ == "__main__":
    seed_demo_data()
    capture()
