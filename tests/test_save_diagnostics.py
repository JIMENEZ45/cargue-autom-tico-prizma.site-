"""Pruebas del diagnostico cuando PRIZMA no confirma el guardado (sin PATCH).

ERROR_PATCH_NO_CONFIRMADO ahora incluye que observo el motor: alertas
visibles, respuestas HTTP no-GET y peticiones fallidas durante el guardado.
"""

from types import SimpleNamespace

from auto_prizma.automation.prizma import engine


class _Elemento:
    def __init__(self, texto, visible=True):
        self.texto = texto
        self.visible = visible

    def is_visible(self):
        return self.visible

    def inner_text(self, timeout=None):
        return self.texto


class _Locator:
    def __init__(self, elementos):
        self.elementos = elementos

    def count(self):
        return len(self.elementos)

    def nth(self, indice):
        return self.elementos[indice]


class _Pagina:
    def __init__(self, elementos=()):
        self.elementos = list(elementos)
        self.selector = None

    def locator(self, selector):
        self.selector = selector
        return _Locator(self.elementos)


def test_diagnostico_without_any_signal_suggests_form_validation():
    diagnostico = engine._diagnostico_guardado_sin_patch(_Pagina(), [], {})

    assert "no envio ninguna peticion de guardado" in diagnostico


def test_diagnostico_reports_visible_alerts_once_and_skips_hidden():
    pagina = _Pagina([
        _Elemento("El archivo supera el\n tamaño máximo permitido"),
        _Elemento("El archivo supera el tamaño máximo permitido"),
        _Elemento("Mensaje oculto", visible=False),
        _Elemento("Este campo es requerido"),
    ])

    diagnostico = engine._diagnostico_guardado_sin_patch(pagina, [], {})

    assert diagnostico == (
        "PRIZMA mostro: El archivo supera el tamaño máximo permitido | "
        "Este campo es requerido"
    )
    assert pagina.selector == engine._SELECTORES_ALERTAS_PRIZMA


def test_diagnostico_reports_http_responses_and_failed_requests_without_query():
    respuestas = [
        {"metodo": "POST", "status": 413, "url": "https://api.prizma.site/files/upload?token=SECRETO"},
    ]
    captura = {
        "fallidas": [
            {"metodo": "PATCH", "url": "https://api.prizma.site/academic/activity/77", "motivo": "net::ERR_TIMED_OUT"},
        ],
    }

    diagnostico = engine._diagnostico_guardado_sin_patch(_Pagina(), respuestas, captura)

    assert diagnostico == (
        "respuestas: POST 413 /files/upload; "
        "peticiones fallidas: PATCH /academic/activity/77 (net::ERR_TIMED_OUT)"
    )
    assert "SECRETO" not in diagnostico


def test_diagnostico_survives_page_errors():
    class _PaginaRota:
        def locator(self, selector):
            raise RuntimeError("Target page, context or browser has been closed")

    diagnostico = engine._diagnostico_guardado_sin_patch(_PaginaRota(), [], {})

    assert "no envio ninguna peticion" in diagnostico


def test_registrar_fallo_only_records_non_get_while_capturing():
    captura = {"activa": True}
    fallida = SimpleNamespace(method="patch", url="https://x/academic/activity/1", failure="net::ERR_ABORTED")
    lectura = SimpleNamespace(method="GET", url="https://x/listado", failure="net::ERR_ABORTED")

    engine._registrar_fallo_prizma(fallida, captura)
    engine._registrar_fallo_prizma(lectura, captura)
    engine._registrar_fallo_prizma(fallida, {"activa": False})

    assert captura["fallidas"] == [
        {"metodo": "PATCH", "url": "https://x/academic/activity/1", "motivo": "net::ERR_ABORTED"},
    ]


# Mensajes reales de Playwright 1.61 (reproducidos con Chromium local).
ERROR_CLIC_TAPADO = """Locator.click: Timeout 10000ms exceeded.
Call log:
  - waiting for get_by_role("button", name="Editar", exact=True)
    - locator resolved to <button type="submit">Editar</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="MuiBox-root css-15m6u24"></div> intercepts pointer events
    - retrying click action"""

ERROR_CLIC_DESHABILITADO = """Locator.click: Timeout 10000ms exceeded.
Call log:
  - waiting for get_by_role("button", name="Editar", exact=True)
    - locator resolved to <button disabled type="submit">Editar</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action"""

ERROR_SIN_RESPUESTA = 'Timeout 45000ms exceeded while waiting for event "response"'


def test_resumir_error_clic_detects_overlay_blocking_the_button():
    assert engine._resumir_error_clic(ERROR_CLIC_TAPADO) == (
        '<div class="MuiBox-root css-15m6u24"></div> intercepts pointer events'
    )


def test_resumir_error_clic_detects_disabled_button():
    assert engine._resumir_error_clic(ERROR_CLIC_DESHABILITADO) == "element is not enabled"


def test_resumir_error_clic_is_empty_when_click_worked_but_no_response():
    assert engine._resumir_error_clic(ERROR_SIN_RESPUESTA) == ""


def test_diagnostico_puts_blocked_click_first():
    diagnostico = engine._diagnostico_guardado_sin_patch(
        _Pagina(),
        [],
        {},
        detalle_clic="element is not enabled",
    )

    assert diagnostico == "el clic en Guardar no se completo (element is not enabled)"


def test_guardar_captura_diagnostico_writes_png_in_job_temp_folder(tmp_path):
    rutas = []

    class _PaginaConCaptura:
        def screenshot(self, path, full_page, timeout):
            rutas.append(path)
            with open(path, "wb") as archivo:
                archivo.write(b"png")

    ruta = engine._guardar_captura_diagnostico(
        _PaginaConCaptura(),
        str(tmp_path / "trabajo"),
        {"fila_excel": 34},
    )

    assert rutas and rutas[0].endswith("sin_patch_fila_34.png")
    assert (tmp_path / "trabajo" / "sin_patch_fila_34.png").read_bytes() == b"png"
    assert ruta.endswith("sin_patch_fila_34.png")


def test_guardar_captura_diagnostico_never_raises(tmp_path):
    class _PaginaRota:
        def screenshot(self, **kwargs):
            raise RuntimeError("Target closed")

    assert engine._guardar_captura_diagnostico(_PaginaRota(), str(tmp_path / "x"), {}) == ""
    assert engine._guardar_captura_diagnostico(_PaginaRota(), "", {}) == ""


def test_patch_no_confirmado_is_not_structural_error():
    # El detalle agregado no debe disparar el reinicio de sesion por si solo.
    error = "ERROR_PATCH_NO_CONFIRMADO: PRIZMA no envio ninguna peticion de guardado"

    assert engine._es_error_estructural_prizma(error) is False
