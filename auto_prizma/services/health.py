"""Estado real del servicio que muestra la interfaz.

- Chromium: el navegador que usa Playwright esta instalado.
- PRIZMA: la pagina de inicio de sesion responde.

Cada comprobacion se guarda en memoria unos minutos (config.HEALTH_*) para no
repetirla en cada pagina. La interfaz pinta primero lo que haya en memoria
(cached_service_status) y luego pide /estado-servicio, que comprueba lo que
haya vencido.
"""

import os
import threading
import time
import urllib.error
import urllib.request

from auto_prizma.core.config import (
    HEALTH_CHROMIUM_TTL_SECONDS,
    HEALTH_PRIZMA_TIMEOUT_SECONDS,
    HEALTH_PRIZMA_TTL_SECONDS,
    PRIZMA_HOST,
    URL_PRIZMA,
)

_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _cached(key, ttl_seconds, check):
    """Resultado de check() reutilizado durante ttl_seconds."""
    ahora = time.monotonic()
    with _CACHE_LOCK:
        entrada = _CACHE.get(key)
        if entrada and ahora - entrada["momento"] < ttl_seconds:
            return entrada["valor"]

    # Fuera del candado: la comprobacion puede tardar unos segundos.
    valor = check()

    with _CACHE_LOCK:
        _CACHE[key] = {"momento": time.monotonic(), "valor": valor}
    return valor


def clear_cache():
    """Olvida las comprobaciones guardadas (pruebas y diagnostico)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def check_chromium():
    """Comprueba que el Chromium de Playwright este instalado.

    No abre el navegador: pregunta a Playwright por la ruta del ejecutable.
    En modo headless Playwright usa "chromium_headless_shell-<revision>", que
    se instala junto al Chromium completo; si solo esta ese, tambien vale.

    Returns:
        {"ok": bool, "detalle": texto para el usuario}.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            ruta = playwright.chromium.executable_path
    except Exception as error:
        return {
            "ok": False,
            "detalle": "No se pudo consultar Playwright (" + type(error).__name__ + ")",
        }

    if ruta and os.path.isfile(ruta):
        return {"ok": True, "detalle": "Chromium instalado"}

    # .../ms-playwright/chromium-1228/chrome-win64/chrome.exe -> chromium-1228
    carpeta_revision = os.path.dirname(os.path.dirname(ruta or ""))
    nombre_revision = os.path.basename(carpeta_revision)
    if nombre_revision.startswith("chromium-"):
        carpeta_shell = os.path.join(
            os.path.dirname(carpeta_revision),
            nombre_revision.replace("chromium-", "chromium_headless_shell-", 1),
        )
        if os.path.isdir(carpeta_shell):
            return {"ok": True, "detalle": "Chromium instalado (headless)"}

    return {
        "ok": False,
        "detalle": "Chromium no esta instalado: python -m playwright install chromium",
    }


def check_prizma():
    """Comprueba que PRIZMA responda (pagina de inicio de sesion).

    Cualquier respuesta HTTP menor que 500 cuenta como disponible: un 403 o
    un 404 tambien prueban que el servidor esta arriba.

    Returns:
        {"ok": bool, "detalle": texto, "ms": milisegundos o None}.
    """
    solicitud = urllib.request.Request(
        URL_PRIZMA,
        headers={"User-Agent": "AutoPrizmaPro (estado del servicio)"},
    )
    inicio = time.monotonic()

    try:
        with urllib.request.urlopen(solicitud, timeout=HEALTH_PRIZMA_TIMEOUT_SECONDS) as respuesta:
            codigo = int(respuesta.status)
    except urllib.error.HTTPError as error:
        codigo = int(error.code)
    except Exception as error:
        return {
            "ok": False,
            "detalle": PRIZMA_HOST + " no responde (" + type(error).__name__ + ")",
            "ms": None,
        }

    ms = int((time.monotonic() - inicio) * 1000)
    if codigo >= 500:
        return {
            "ok": False,
            "detalle": PRIZMA_HOST + " respondio con error " + str(codigo),
            "ms": ms,
        }

    return {"ok": True, "detalle": PRIZMA_HOST + " responde (" + str(ms) + " ms)", "ms": ms}


def service_status():
    """Estado de Chromium y PRIZMA, comprobando lo que haya vencido."""
    chromium = _cached("chromium", HEALTH_CHROMIUM_TTL_SECONDS, check_chromium)
    prizma = _cached("prizma", HEALTH_PRIZMA_TTL_SECONDS, check_prizma)
    return {
        "ok": bool(chromium.get("ok") and prizma.get("ok")),
        "chromium": chromium,
        "prizma": prizma,
        "prizma_host": PRIZMA_HOST,
    }


def cached_service_status():
    """Lo que ya se sabe, sin comprobar nada (None si aun no se comprobo).

    Sirve para pintar la pagina al instante; el navegador pide luego el
    estado completo a /estado-servicio.
    """
    with _CACHE_LOCK:
        chromium = (_CACHE.get("chromium") or {}).get("valor")
        prizma = (_CACHE.get("prizma") or {}).get("valor")

    if chromium is None and prizma is None:
        return None

    return {
        "ok": bool(chromium and chromium.get("ok") and prizma and prizma.get("ok")),
        "chromium": chromium,
        "prizma": prizma,
        "prizma_host": PRIZMA_HOST,
    }
