"""健康检查与统一错误信封测试。"""


def test_health_ok(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_unknown_route_uses_error_envelope(client) -> None:
    response = client.get("/api/definitely-not-exists")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_404"


def test_validation_error_uses_error_envelope(client) -> None:
    response = client.post("/api/auth/register", json={"username": "ab", "password": "1"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "request_validation_error"
    assert isinstance(body["detail"], list)
