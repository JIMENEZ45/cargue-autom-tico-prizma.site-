"""Pruebas del marco comun de las paginas (web/layout.py y static/app.css/app.js)."""

import os
import re

import pytest
from fastapi.testclient import TestClient

from main import app
from auto_prizma.integrations.google.oauth import _ruta_token_google
from auto_prizma.services.auth import _firmar_sesion
from auto_prizma.web.layout import NAV_ITEMS


def _session_client():
    client = TestClient(app)
    client.cookies.set("ap_sesion", _firmar_sesion("adminlocal"))
    return client


@pytest.mark.parametrize(
    "ruta",
    ["/", "/tests", "/moodle", "/cargue-actual", "/historial", "/reportes", "/cambiar-clave"],
)
def test_every_page_uses_the_common_frame(ruta, monkeypatch):
    if ruta == "/moodle":
        monkeypatch.setattr(
            "auto_prizma.api.routes.moodle_resources._request_is_local",
            lambda _request: True,
        )
    respuesta = _session_client().get(ruta)
    html = respuesta.text

    assert respuesta.status_code == 200
    assert 'class="sidebar"' in html
    for _clave, _texto, href, _icono in NAV_ITEMS:
        assert f'href="{href}"' in html
    # Una sola opcion marcada, y es la de la pagina.
    assert html.count('aria-current="page"') == 1
    assert f'<a class="nav-item activo" href="{ruta}" aria-current="page">' in html
    assert re.search(r'href="/app\.css\?v=\d+"', html)
    assert re.search(r'src="/app\.js\?v=\d+"', html)
    assert "estilos-responsive.css" not in html and "tema.js" not in html
    assert "data-tema-toggle" in html
    assert 'data-servicio="linea"' in html


def test_login_is_public_and_has_no_menu():
    respuesta = TestClient(app).get("/login")

    assert respuesta.status_code == 200
    assert "/app.css?v=" in respuesta.text
    assert 'class="sidebar"' not in respuesta.text
    assert "data-tema-toggle" in respuesta.text


@pytest.mark.parametrize(
    ("ruta", "tipo"),
    [("/app.css", "text/css"), ("/app.js", "application/javascript")],
)
def test_common_assets_are_public(ruta, tipo):
    respuesta = TestClient(app).get(ruta)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith(tipo)


@pytest.mark.parametrize("ruta", ["/estilos-responsive.css", "/tema.js"])
def test_old_assets_no_longer_exist(ruta):
    assert _session_client().get(ruta).status_code == 404


def test_user_menu_shows_initials_and_google_disconnect_only_with_token():
    client = _session_client()
    html = client.get("/reportes").text

    assert '<span class="avatar" aria-hidden="true">AL</span>' in html  # "Admin local"
    assert "Desconectar Google" not in html

    ruta = _ruta_token_google("adminlocal")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    try:
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write("{}")
        html = client.get("/reportes").text
        assert "Desconectar Google" in html
        assert 'action="/google/desconectar"' in html
    finally:
        os.remove(ruta)


def test_home_keeps_the_form_contract_and_status_pills():
    html = _session_client().get("/").text

    for nombre in [
        "modo_matriz", "google_sheet_url", "matriz_archivo", "recursos", "ovi", "ova", "retos",
        "test_evaluativo", "formato_recurso", "modo_test", "test_archivo_docx",
        "test_google_doc_url", "test_datos_academicos", "test_semestre",
    ]:
        assert f'name="{nombre}"' in html
    assert 'action="/analizar"' in html
    assert 'data-servicio="pastilla-chromium"' in html
    assert 'data-servicio="pastilla-prizma"' in html
    assert 'href="/google/conectar"' in html  # sin token: invita a conectar Google
    assert 'id="dialogo-guia"' in html
