"""Uso local sin login: AUTO_PRIZMA_SIN_LOGIN solo vale desde el mismo equipo."""

from fastapi.testclient import TestClient

from main import app


def _client(host):
    # TestClient permite fijar la IP de origen de la petición.
    return TestClient(app, client=(host, 50000))


def test_without_the_variable_login_is_still_required(monkeypatch):
    monkeypatch.delenv("AUTO_PRIZMA_SIN_LOGIN", raising=False)
    response = _client("127.0.0.1").get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_local_request_enters_without_login_as_the_configured_user(monkeypatch):
    monkeypatch.setenv("AUTO_PRIZMA_SIN_LOGIN", "adminlocal")
    client = _client("127.0.0.1")

    assert client.get("/", follow_redirects=False).status_code == 200
    login = client.get("/login", follow_redirects=False)
    assert login.status_code == 303 and login.headers["location"] == "/"


def test_remote_request_still_requires_login_even_with_the_variable(monkeypatch):
    monkeypatch.setenv("AUTO_PRIZMA_SIN_LOGIN", "adminlocal")
    response = _client("10.0.0.7").get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert _client("10.0.0.7").get("/estado/x", headers={"Accept": "application/json"}).status_code == 401


def test_unknown_user_does_not_open_the_app(monkeypatch):
    monkeypatch.setenv("AUTO_PRIZMA_SIN_LOGIN", "no-existe")
    response = _client("127.0.0.1").get("/", follow_redirects=False)
    assert response.status_code == 303
