"""Pytest 公共夹具。

每个测试获得独立的临时 SQLite 数据库（tmp_path），
应用 lifespan 会对其执行 Alembic 迁移——与生产完全同一建表路径。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    """测试配置：隔离数据目录、短令牌有效期、不读本机 .env。"""
    return Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        log_level="WARNING",
        jwt_expire_minutes=60,
    )


@pytest.fixture
def client(settings):
    """带 lifespan 的 HTTP 客户端（启动时自动执行迁移）。"""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(client):
    """注册并登录一个用户，返回认证头。"""

    def _make_user(username: str = "alice", password: str = "password123") -> dict[str, str]:
        response = client.post(
            "/api/auth/register", json={"username": username, "password": password}
        )
        assert response.status_code == 201, response.text
        response = client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make_user
