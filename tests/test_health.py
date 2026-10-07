"""Pruebas del estado real del servicio (services/health.py y /estado-servicio).

No se abre Chromium ni se llama a PRIZMA: Playwright y urllib se simulan.
"""

import urllib.error

import playwright.sync_api
import pytest
from fastapi.testclient import TestClient

from main import app
from auto_prizma.api.routes import health as health_routes
from auto_prizma.services import health
from auto_prizma.services.auth import _firmar_sesion


@pytest.fixture(autouse=True)
def cache_limpio():
    health.clear_cache()
    yield
    health.clear_cache()


def _session_client():
    client = TestClient(app)
    client.cookies.set("ap_sesion", _firmar_sesion("adminlocal"))
    return client


# ============================================================
# PRIZMA
# ============================================================

class _Respuesta:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_prizma_ok_when_login_page_answers(monkeypatch):
    llamadas = []

    def abrir(solicitud, timeout):
        llamadas.append((solicitud.full_url, timeout))
        return _Respuesta(200)

    monkeypatch.setattr(health.urllib.request, "urlopen", abrir)

    resultado = health.check_prizma()

    assert resultado["ok"] is True
    assert "responde" in resultado["detalle"]
    assert llamadas == [(health.URL_PRIZMA, health.HEALTH_PRIZMA_TIMEOUT_SECONDS)]


def test_prizma_client_error_still_means_the_server_is_up(monkeypatch):
    def abrir(solicitud, timeout):
        raise urllib.error.HTTPError(solicitud.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(health.urllib.request, "urlopen", abrir)

    assert health.check_prizma()["ok"] is True


def test_prizma_server_error_is_reported(monkeypatch):
    monkeypatch.setattr(health.urllib.request, "urlopen", lambda solicitud, timeout: _Respuesta(503))

    resultado = health.check_prizma()

    assert resultado["ok"] is False
    assert "503" in resultado["detalle"]


def test_prizma_without_answer_is_reported(monkeypatch):
    def abrir(solicitud, timeout):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(health.urllib.request, "urlopen", abrir)

    resultado = health.check_prizma()

    assert resultado["ok"] is False
    assert "no responde (URLError)" in resultado["detalle"]


# ============================================================
# CHROMIUM
# ============================================================

def _playwright_falso(monkeypatch, ruta=None, error=None):
    class _Chromium:
        @property
        def executable_path(self):
            if error:
                raise error
            return ruta

    class _Playwright:
        chromium = _Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(playwright.sync_api, "sync_playwright", lambda: _Playwright())


def test_chromium_ok_when_executable_exists(monkeypatch, tmp_path):
    ejecutable = tmp_path / "ms-playwright" / "chromium-1228" / "chrome-win64" / "chrome.exe"
    ejecutable.parent.mkdir(parents=True)
    ejecutable.write_bytes(b"")
    _playwright_falso(monkeypatch, str(ejecutable))

    assert health.check_chromium() == {"ok": True, "detalle": "Chromium instalado"}


def test_chromium_headless_shell_also_counts(monkeypatch, tmp_path):
    ejecutable = tmp_path / "ms-playwright" / "chromium-1228" / "chrome-win64" / "chrome.exe"
    (tmp_path / "ms-playwright" / "chromium_headless_shell-1228").mkdir(parents=True)
    _playwright_falso(monkeypatch, str(ejecutable))

    assert health.check_chromium()["ok"] is True


def test_chromium_missing_is_reported(monkeypatch, tmp_path):
    _playwright_falso(monkeypatch, str(tmp_path / "ms-playwright" / "chromium-1228" / "chrome-win64" / "chrome.exe"))

    resultado = health.check_chromium()

    assert resultado["ok"] is False
    assert "playwright install chromium" in resultado["detalle"]


def test_chromium_playwright_failure_is_reported(monkeypatch):
    _playwright_falso(monkeypatch, error=RuntimeError("driver"))

    resultado = health.check_chromium()

    assert resultado == {"ok": False, "detalle": "No se pudo consultar Playwright (RuntimeError)"}


# ============================================================
# MEMORIA Y RUTA
# ============================================================

def test_status_is_cached_until_cleared(monkeypatch):
    llamadas = {"chromium": 0, "prizma": 0}

    def chromium():
        llamadas["chromium"] += 1
        return {"ok": True, "detalle": "Chromium instalado"}

    def prizma():
        llamadas["prizma"] += 1
        return {"ok": False, "detalle": "admin.prizma.site no responde (URLError)", "ms": None}

    monkeypatch.setattr(health, "check_chromium", chromium)
    monkeypatch.setattr(health, "check_prizma", prizma)

    assert health.cached_service_status() is None

    primero = health.service_status()
    segundo = health.service_status()

    assert primero == segundo
    assert primero["ok"] is False
    assert llamadas == {"chromium": 1, "prizma": 1}
    assert health.cached_service_status()["prizma"]["ok"] is False

    health.clear_cache()
    health.service_status()
    assert llamadas == {"chromium": 2, "prizma": 2}


def test_status_route_returns_json_for_the_session(monkeypatch):
    estado = {"ok": True, "chromium": {"ok": True}, "prizma": {"ok": True}, "prizma_host": "admin.prizma.site"}
    monkeypatch.setattr(health_routes, "service_status", lambda: estado)

    respuesta = _session_client().get("/estado-servicio")

    assert respuesta.status_code == 200
    assert respuesta.json() == estado
    assert respuesta.headers["cache-control"] == "no-store"


def test_status_route_requires_session():
    respuesta = TestClient(app).get("/estado-servicio", headers={"Accept": "application/json"})

    assert respuesta.status_code == 401
