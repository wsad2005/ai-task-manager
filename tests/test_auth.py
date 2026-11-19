"""认证测试：注册、登录、令牌校验与失败路径。"""

from datetime import UTC, datetime, timedelta

import jwt


def test_register_success(client) -> None:
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": "password123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username(client) -> None:
    payload = {"username": "alice", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_taken"


def test_register_rejects_short_password(client) -> None:
    response = client.post("/api/auth/register", json={"username": "alice", "password": "short"})
    assert response.status_code == 422


def test_register_rejects_over_72_bytes_password(client) -> None:
    # bcrypt 硬上限 72 字节：27 个中文 = 81 字节，应被校验拒绝而非静默截断
    response = client.post(
        "/api/auth/register", json={"username": "alice", "password": "密" * 27}
    )
    assert response.status_code == 422


def test_register_rejects_invalid_username(client) -> None:
    response = client.post(
        "/api/auth/register", json={"username": "bad name!", "password": "password123"}
    )
    assert response.status_code == 422


def test_login_success_returns_token(client) -> None:
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    response = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"


def test_login_wrong_password(client) -> None:
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    response = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_user_same_error_as_wrong_password(client) -> None:
    response = client.post("/api/auth/login", json={"username": "ghost", "password": "password123"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"  # 不泄露用户是否存在


def test_me_requires_token(client) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_error"


def test_me_with_valid_token(client, settings) -> None:
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    ).json()["access_token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_with_garbage_token(client) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_with_expired_token(client, settings) -> None:
    # 用测试配置的密钥手工构造过期令牌
    expired = jwt.encode(
        {"sub": "someone", "exp": datetime.now(UTC) - timedelta(minutes=5)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "过期" in response.json()["error"]["message"]


def test_me_with_token_of_deleted_user(client, settings) -> None:
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    # 模拟用户被删除：令牌仍有效但 sub 不存在
    forged = jwt.encode({"sub": "deleted-user", "exp": datetime.now(UTC) + timedelta(hours=1)},
                        settings.secret_key, algorithm=settings.jwt_algorithm)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
