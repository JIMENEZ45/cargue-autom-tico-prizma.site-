"""Pruebas del ambiente de PRIZMA configurable (AUTO_PRIZMA_URL_PRIZMA).

Sin la variable se usa produccion (admin.prizma.site); con ella, por ejemplo
el ambiente de pruebas admin.prizma.solutions, y la app lo muestra en pantalla.
"""

import os
import subprocess
import sys

import pytest

from auto_prizma.automation.prizma import engine
from auto_prizma.core import config
from auto_prizma.web import views


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, "https://admin.prizma.site"),
        ("", "https://admin.prizma.site"),
        ("   ", "https://admin.prizma.site"),
        ("https://admin.prizma.solutions", "https://admin.prizma.solutions"),
        ("https://admin.prizma.solutions/", "https://admin.prizma.solutions"),
        ("admin.prizma.solutions", "https://admin.prizma.solutions"),
        ("http://localhost:3000", "http://localhost:3000"),
    ],
)
def test_resolver_url_prizma(valor, esperado):
    assert config._resolver_url_prizma(valor) == esperado


def _config_en_proceso_nuevo(tmp_path, url=None):
    """Importa la configuracion en otro proceso (se lee al importar)."""
    entorno = dict(os.environ, AUTO_PRIZMA_DATA_DIR=str(tmp_path))
    entorno.pop("AUTO_PRIZMA_URL_PRIZMA", None)
    if url is not None:
        entorno["AUTO_PRIZMA_URL_PRIZMA"] = url
    salida = subprocess.run(
        [sys.executable, "-c",
         "from auto_prizma.core import config as c; "
         "print(c.URL_PRIZMA, c.PRIZMA_HOST, c.PRIZMA_ES_PRODUCCION)"],
        capture_output=True, text=True, env=entorno, check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return salida.stdout.split()


def test_without_variable_uses_production(tmp_path):
    assert _config_en_proceso_nuevo(tmp_path) == [
        "https://admin.prizma.site/inicio-sesion", "admin.prizma.site", "True",
    ]


def test_with_variable_uses_test_environment(tmp_path):
    assert _config_en_proceso_nuevo(tmp_path, "admin.prizma.solutions/") == [
        "https://admin.prizma.solutions/inicio-sesion", "admin.prizma.solutions", "False",
    ]


def test_engine_uses_configured_login_url():
    assert engine.URL_PRIZMA == config.URL_PRIZMA


def test_test_environment_banner_only_outside_production(monkeypatch):
    monkeypatch.setattr(views, "PRIZMA_ES_PRODUCCION", True)
    assert "Ambiente de pruebas de PRIZMA" not in views.generar_html()

    monkeypatch.setattr(views, "PRIZMA_ES_PRODUCCION", False)
    monkeypatch.setattr(views, "PRIZMA_HOST", "admin.prizma.solutions")
    pagina = views.generar_html()
    assert "Ambiente de pruebas de PRIZMA:</strong> admin.prizma.solutions" in pagina
