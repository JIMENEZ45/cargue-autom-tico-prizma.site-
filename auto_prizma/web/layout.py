"""Marco comun de todas las paginas: barra lateral, barra superior y recursos compartidos.

- render_page(): paginas con sesion (menu lateral, estado del servicio,
  tema claro/oscuro y menu del usuario).
- render_public_page(): paginas sin sesion (login).

El aspecto comun vive en static/app.css y el comportamiento comun (tema,
menus, copiar, tablas, estado del servicio) en static/app.js. Cada pagina
solo agrega su contenido y, si lo necesita, su CSS/JS propio.
"""

import html
import os

from auto_prizma.core.config import (
    APP_CSS_PATH,
    APP_JS_PATH,
    PRIZMA_ES_PRODUCCION,
    PRIZMA_HOST,
)
from auto_prizma.integrations.google.oauth import google_token_exists
from auto_prizma.services.auth import _nombre_visible, _usuario_actual
from auto_prizma.services.health import cached_service_status
from auto_prizma.web.icons import icon

APP_NAME = "Cargue Prizma Pro"

# (clave, texto, ruta, icono) en el orden del menu lateral.
NAV_ITEMS = (
    ("inicio", "Inicio", "/", "inicio"),
    ("test", "Test", "/tests", "test"),
    ("auditor", "Auditor", "/auditor", "escudo"),
    ("moodle", "Cargue Moodle", "/moodle", "moodle"),
    ("cargue", "Cargue actual", "/cargue-actual", "subir"),
    ("cursos", "Cursos", "/cursos", "libro"),
    ("historial", "Historial", "/historial", "historial"),
    ("reportes", "Reportes", "/reportes", "reportes"),
)

# Se ejecuta antes de pintar para que el tema oscuro no parpadee.
_THEME_BOOT = (
    '<script>try{if(localStorage.getItem("autoPrizmaTema")==="dark")'
    'document.documentElement.setAttribute("data-theme","dark")}catch(e){}</script>'
)


def _e(valor):
    return html.escape(str(valor or ""), quote=True)


def asset_url(path, public_path):
    """URL del recurso con su fecha de modificacion, para que el navegador
    descargue la version nueva despues de cada cambio."""
    try:
        version = str(int(os.path.getmtime(path)))
    except OSError:
        version = "0"
    return public_path + "?v=" + version


# ============================================================
# ESTADO DEL SERVICIO
# ============================================================

_TEXTOS_ESTADO = {
    # (indicador, estado): texto. Los mismos textos usa static/app.js.
    ("linea", "ok"): "Servicio activo",
    ("linea", "error"): "Servicio con problemas",
    ("linea", "pendiente"): "Comprobando servicio",
    ("chromium", "ok"): "Chromium",
    ("chromium", "error"): "No disponible",
    ("chromium", "pendiente"): "Comprobando",
    ("prizma", "ok"): "Estable",
    ("prizma", "error"): "Sin respuesta",
    ("prizma", "pendiente"): "Comprobando",
    ("pastilla-chromium", "ok"): "Chromium activo",
    ("pastilla-chromium", "error"): "Chromium no disponible",
    ("pastilla-chromium", "pendiente"): "Comprobando Chromium",
    ("pastilla-prizma", "ok"): "Servicio estable",
    ("pastilla-prizma", "error"): "PRIZMA sin respuesta",
    ("pastilla-prizma", "pendiente"): "Comprobando PRIZMA",
}


def _estado(item):
    """ok / error / pendiente a partir de un resultado de services.health."""
    if not item:
        return "pendiente"
    return "ok" if item.get("ok") else "error"


def _initial_status():
    """Estados y detalles conocidos (sin comprobar nada)."""
    estado = cached_service_status() or {}
    chromium = estado.get("chromium")
    prizma = estado.get("prizma")
    linea = "pendiente"
    if chromium and prizma:
        linea = "ok" if estado.get("ok") else "error"
    elif (chromium and not chromium.get("ok")) or (prizma and not prizma.get("ok")):
        linea = "error"
    return {
        "linea": (linea, ""),
        "chromium": (_estado(chromium), (chromium or {}).get("detalle", "")),
        "prizma": (_estado(prizma), (prizma or {}).get("detalle", "")),
    }


def _service_card():
    estado = _initial_status()
    linea, _ = estado["linea"]
    chromium, detalle_chromium = estado["chromium"]
    prizma, detalle_prizma = estado["prizma"]
    return (
        '<div class="estado-servicio" data-estado-servicio>'
        '<div class="servicio-linea" data-servicio="linea" data-estado="' + linea + '">'
        '<i class="punto"></i><span data-texto>' + _TEXTOS_ESTADO[("linea", linea)] + "</span></div>"
        '<div class="servicio-mini"><span>Navegador</span>'
        '<span class="chip" data-servicio="chromium" data-estado="' + chromium + '" title="' + _e(detalle_chromium) + '">'
        '<span data-texto>' + _TEXTOS_ESTADO[("chromium", chromium)] + "</span></span></div>"
        '<div class="servicio-mini"><span>Conexión</span>'
        '<span class="chip" data-servicio="prizma" data-estado="' + prizma + '" title="' + _e(detalle_prizma) + '">'
        '<span data-texto>' + _TEXTOS_ESTADO[("prizma", prizma)] + "</span></span></div>"
        "</div>"
    )


def status_pills(google_connected):
    """Indicadores de Inicio: Google (real, del servidor), Chromium y PRIZMA.

    Chromium y PRIZMA se pintan con lo que haya en memoria y static/app.js
    los actualiza con /estado-servicio.
    """
    if google_connected:
        google = (
            '<span class="pastilla" data-estado="ok" title="Tu cuenta de Google está conectada (solo lectura)">'
            + icon("google") + '<span>Google conectado</span><i class="punto"></i></span>'
        )
    else:
        google = (
            '<a class="pastilla" data-estado="aviso" href="/google/conectar" '
            'title="Necesario para leer la matriz por link">'
            + icon("google") + '<span>Conectar Google</span><i class="punto"></i></a>'
        )

    estado = _initial_status()
    chromium, detalle_chromium = estado["chromium"]
    prizma, detalle_prizma = estado["prizma"]
    return (
        '<div class="pastillas">'
        + google
        + '<span class="pastilla" data-servicio="pastilla-chromium" data-estado="' + chromium
        + '" title="' + _e(detalle_chromium) + '">' + icon("chromium", "icono icono-chromium")
        + '<span data-texto>' + _TEXTOS_ESTADO[("pastilla-chromium", chromium)] + '</span><i class="punto"></i></span>'
        + '<span class="pastilla" data-servicio="pastilla-prizma" data-estado="' + prizma
        + '" title="' + _e(detalle_prizma) + '">' + icon("wifi", "icono icono-wifi")
        + '<span data-texto>' + _TEXTOS_ESTADO[("pastilla-prizma", prizma)] + '</span><i class="punto"></i></span>'
        + "</div>"
    )


# ============================================================
# PIEZAS DEL MARCO
# ============================================================

def environment_notice():
    """Aviso visible cuando la app apunta a un PRIZMA que no es produccion.

    En produccion devuelve "" para no alterar la pagina.
    """
    if PRIZMA_ES_PRODUCCION:
        return ""

    return (
        '<div class="aviso-ambiente" role="status">' + icon("matraz")
        + "<span><strong>Ambiente de pruebas de PRIZMA:</strong> " + html.escape(PRIZMA_HOST)
        + ". Los cargues de esta instancia no van a producción.</span></div>"
    )


def _initials(nombre):
    partes = [parte for parte in str(nombre or "").split() if parte]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    if partes:
        return partes[0][0].upper()
    return "?"


def _theme_button():
    return (
        '<button type="button" class="boton-tema" data-tema-toggle '
        'aria-label="Cambiar a tema oscuro" title="Cambiar a tema oscuro">'
        + icon("luna", "icono icono-luna") + icon("sol", "icono icono-sol") + "</button>"
    )


def _user_menu():
    usuario = _usuario_actual() or ""
    nombre = _nombre_visible(usuario) or usuario or "Usuario"
    google = ""
    if google_token_exists(usuario):
        google = (
            '<form method="post" action="/google/desconectar">'
            '<button type="submit" role="menuitem">' + icon("google") + "Desconectar Google</button></form>"
        )

    return (
        '<div class="menu-usuario" data-menu>'
        '<button type="button" class="boton-usuario" data-menu-boton aria-haspopup="menu" '
        'aria-expanded="false" aria-label="Menú de ' + _e(nombre) + '">'
        '<span class="avatar" aria-hidden="true">' + _e(_initials(nombre)) + "</span>"
        + icon("chevron") + "</button>"
        '<div class="menu-desplegable" role="menu" data-menu-lista hidden>'
        '<div class="menu-cabecera"><strong>' + _e(nombre) + "</strong><span>" + _e(usuario) + "</span></div>"
        + google
        + "</div></div>"
    )


def _sidebar(active):
    enlaces = []
    for clave, texto, ruta, nombre_icono in NAV_ITEMS:
        actual = clave == active
        enlaces.append(
            '<a class="nav-item' + (" activo" if actual else "") + '" href="' + ruta + '"'
            + (' aria-current="page"' if actual else "") + ">"
            + icon(nombre_icono) + "<span>" + html.escape(texto) + "</span></a>"
        )

    return (
        '<aside class="sidebar">'
        '<a class="marca" href="/">'
        '<img src="/auto-prizma-logo.png" alt="" width="46" height="46">'
        '<span class="marca-texto"><strong>' + APP_NAME + "</strong><small>Cargue Prizma</small></span></a>"
        '<nav class="nav" aria-label="Menú principal">' + "".join(enlaces) + "</nav>"
        + _service_card()
        + "</aside>"
    )


def _head(title, page_css):
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        "<title>" + html.escape(title) + " - " + APP_NAME + "</title>"
        '<link rel="icon" type="image/png" href="/auto-prizma-logo.png">'
        + _THEME_BOOT
        + '<link rel="stylesheet" href="' + asset_url(APP_CSS_PATH, "/app.css") + '">'
        + ("<style>" + page_css + "</style>" if page_css else "")
        + "</head>"
    )


def _scripts(page_js):
    return (
        '<script src="' + asset_url(APP_JS_PATH, "/app.js") + '"></script>'
        + ("<script>" + page_js + "</script>" if page_js else "")
    )


# ============================================================
# PAGINAS
# ============================================================

def render_page(title, content, *, active="", page_css="", page_js="", after_main=""):
    """Pagina completa con el marco comun.

    Args:
        title: titulo de la pestana del navegador (sin el nombre de la app).
        content: HTML del contenido principal.
        active: clave de NAV_ITEMS que se marca en el menu ("" = ninguna).
        page_css / page_js: estilos y script propios de la pagina.
        after_main: HTML que va fuera del contenido (dialogos, cargadores).
    """
    return (
        _head(title, page_css)
        + '<body><div class="app">'
        + _sidebar(active)
        + '<div class="principal"><header class="barra-superior">'
        + _theme_button() + _user_menu()
        + '</header><main class="contenido" id="contenido">'
        + environment_notice()
        + content
        + "</main></div></div>"
        + after_main
        + _scripts(page_js)
        + "</body></html>"
    )


def render_public_page(title, content, *, page_css="", page_js=""):
    """Pagina sin sesion (login): sin menu lateral ni menu de usuario."""
    return (
        _head(title, page_css)
        + '<body class="pagina-publica"><header class="barra-superior barra-publica">'
        + _theme_button()
        + "</header><main class=\"contenido-publico\">"
        + environment_notice()
        + content
        + "</main>"
        + _scripts(page_js)
        + "</body></html>"
    )
