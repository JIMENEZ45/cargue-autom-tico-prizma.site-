"""Pruebas del arranque del navegador visible ("ver navegador") en tests evaluativos.

Cubren el caso headless=False, que antes fallaba con NameError porque
automation.py usaba sys.platform sin importar sys.
"""

import sys
from unittest.mock import MagicMock, patch

from auto_prizma.evaluative_tests.automation import PrizmaTestAutomator
from auto_prizma.evaluative_tests.models import DocumentTest


def _ejecutar_con_playwright_simulado(automator):
    """Ejecuta un cargue simulado y devuelve (resultado, mock de chromium.launch)."""
    automator._tomar_captura = MagicMock(return_value="")
    automator.login = MagicMock(return_value=True)
    automator.navegar_a_crear_test = MagicMock()
    automator.seleccionar_mui = MagicMock(return_value=True)
    automator.inyectar_json_test = MagicMock(return_value=True)

    with patch("auto_prizma.evaluative_tests.automation.sync_playwright") as mock_sp:
        mock_p = MagicMock()
        mock_sp.return_value.__enter__.return_value = mock_p

        resultado = automator.ejecutar_cargue(
            usuario_prizma="usuario",
            clave_prizma="clave",
            tests=[DocumentTest(title="Test visible", sections=[])],
            cascada={},
            solo_simulacion=True,
        )

    return resultado, mock_p.chromium.launch


def test_headful_on_windows_opens_visible_browser(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    automator = PrizmaTestAutomator(headless=False)

    resultado, launch = _ejecutar_con_playwright_simulado(automator)

    assert resultado["ok"] is True
    kwargs = launch.call_args.kwargs
    assert kwargs["headless"] is False
    assert "--start-maximized" in kwargs["args"]


def test_headful_without_display_falls_back_to_headless(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    automator = PrizmaTestAutomator(headless=False)

    resultado, launch = _ejecutar_con_playwright_simulado(automator)

    assert resultado["ok"] is True
    assert launch.call_args.kwargs["headless"] is True
    assert any("DISPLAY" in log.get("mensaje", str(log)) for log in automator.logs)
