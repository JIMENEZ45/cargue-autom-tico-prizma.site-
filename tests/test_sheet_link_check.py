"""Pruebas de la comprobacion del enlace de la matriz al pegarlo en Inicio.

integrations/google/drive.check_sheet_link y la ruta /google/validar-matriz.
Google se simula: solo se pide el titulo del documento y de sus pestanas.
"""

import httplib2
import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError

from main import app
from auto_prizma.api.routes import google as google_routes
from auto_prizma.integrations.google import drive
from auto_prizma.services.auth import _firmar_sesion

URL = "https://docs.google.com/spreadsheets/d/AbC_123/edit#gid=42"
META = {
    "properties": {"title": "Matriz Esp en Fintech"},
    "sheets": [
        {"properties": {"sheetId": 0, "title": "Portada"}},
        {"properties": {"sheetId": 42, "title": "Seminario I"}},
    ],
}


class _Sheets:
    def __init__(self, respuesta=None, error=None):
        self.respuesta = respuesta
        self.error = error
        self.pedido = None

    def spreadsheets(self):
        return self

    def get(self, **kwargs):
        self.pedido = kwargs
        return self

    def execute(self):
        if self.error:
            raise self.error
        return self.respuesta


@pytest.fixture
def google(monkeypatch):
    """Credenciales y servicio de Sheets falsos."""
    servicio = _Sheets(META)
    monkeypatch.setattr(drive, "_cargar_credenciales_google", lambda: object())
    monkeypatch.setattr(drive, "build", lambda *args, **kwargs: servicio)
    return servicio


def _error_http(estado):
    return HttpError(httplib2.Response({"status": estado}), b"{}")


def test_valid_link_reports_document_and_tab(google):
    assert drive.check_sheet_link(URL) == {
        "ok": True,
        "documento": "Matriz Esp en Fintech",
        "pestana": "Seminario I",
    }
    # Solo metadatos, nunca el contenido de la hoja.
    assert google.pedido == {
        "spreadsheetId": "AbC_123",
        "fields": "properties(title),sheets.properties(sheetId,title)",
    }


@pytest.mark.parametrize(
    ("url", "texto"),
    [
        ("https://example.com/hoja", "No es un enlace de Google Sheets"),
        ("https://docs.google.com/spreadsheets/d/AbC_123/edit", "falta #gid="),
    ],
)
def test_bad_links_are_rejected_without_calling_google(monkeypatch, url, texto):
    def no_llamar():
        raise AssertionError("no debe pedir credenciales")

    monkeypatch.setattr(drive, "_cargar_credenciales_google", no_llamar)

    resultado = drive.check_sheet_link(url)

    assert resultado["ok"] is False
    assert texto in resultado["motivo"]
    assert resultado["conectar"] is False


def test_missing_google_connection_asks_to_connect(monkeypatch):
    monkeypatch.setattr(drive, "_cargar_credenciales_google", lambda: None)

    resultado = drive.check_sheet_link(URL)

    assert resultado["ok"] is False
    assert resultado["conectar"] is True


def test_tab_that_no_longer_exists(google):
    google.respuesta = {"properties": {"title": "Matriz"}, "sheets": [{"properties": {"sheetId": 7, "title": "Otra"}}]}

    resultado = drive.check_sheet_link(URL)

    assert resultado["ok"] is False
    assert "ya no existe" in resultado["motivo"]


@pytest.mark.parametrize(
    ("estado", "texto"),
    [
        (404, "No se encontró la hoja"),
        (403, "no tiene permiso"),
        (500, "Google respondió con un error (500)"),
    ],
)
def test_google_errors_are_explained(google, estado, texto):
    google.error = _error_http(estado)

    resultado = drive.check_sheet_link(URL)

    assert resultado["ok"] is False
    assert texto in resultado["motivo"]


def test_unexpected_failure_does_not_block_the_analysis(google):
    google.error = TimeoutError("lento")

    resultado = drive.check_sheet_link(URL)

    assert resultado["ok"] is False
    assert "Puedes analizar igualmente" in resultado["motivo"]


def test_route_returns_the_check_as_json(monkeypatch):
    recibidas = []

    def comprobar(url):
        recibidas.append(url)
        return {"ok": True, "documento": "Matriz", "pestana": "Hoja"}

    monkeypatch.setattr(google_routes, "check_sheet_link", comprobar)
    client = TestClient(app)
    client.cookies.set("ap_sesion", _firmar_sesion("adminlocal"))

    respuesta = client.get("/google/validar-matriz", params={"url": URL})

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "documento": "Matriz", "pestana": "Hoja"}
    assert recibidas == [URL]
