"""Estado por curso: actividades que ya estan en PRIZMA y las que faltan.

Cruza data/estado_cursos.json (acumulado entre cargues) y muestra, por curso,
cuantas actividades quedaron subidas y cual es la causa humana de las que
faltan, con un atajo para reintentar solo esas.
"""

from datetime import datetime
import html

from fastapi.responses import HTMLResponse

from auto_prizma.core.application import app
from auto_prizma.core.config import ZONA_HORARIA_COLOMBIA
from auto_prizma.services.auth import _usuario_actual
from auto_prizma.services.course_state import resumen_cursos, total_faltantes
from auto_prizma.web.icons import icon
from auto_prizma.web.layout import render_page


def _e(valor):
    return html.escape(str(valor or ""))


def _fecha_corta(fecha_iso):
    """'22 oct 2026' a partir de un ISO, o '' si no se puede leer."""
    try:
        fecha = datetime.fromisoformat(str(fecha_iso or ""))
    except ValueError:
        return ""
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=ZONA_HORARIA_COLOMBIA)
    fecha = fecha.astimezone(ZONA_HORARIA_COLOMBIA)
    return fecha.strftime("%d %b %Y").lstrip("0")


def _ubicacion(item):
    hoja = str(item.get("hoja") or "").strip()
    fila = str(item.get("fila") or "").strip()
    partes = [p for p in (hoja, ("fila " + fila) if fila else "") if p]
    return " · ".join(partes)


def _motivo_html(item):
    """Causa en lenguaje humano; el codigo queda chiquito abajo."""
    motivo = str(item.get("motivo") or "").strip()
    codigo = str(item.get("codigo") or "").strip()

    if not motivo and not codigo:
        return '<span class="motivo-vacio">Sin detalle registrado</span>'

    html_salida = _e(motivo or codigo)
    if motivo and codigo and codigo != motivo:
        html_salida += '<small class="motivo-codigo">' + _e(codigo) + "</small>"
    return html_salida


def _fila_faltante(item):
    return (
        "<tr>"
        '<td class="celda-fuerte">' + _e(item.get("nombre")) + "</td>"
        '<td class="col-estrecha">' + _e(_ubicacion(item)) + "</td>"
        '<td class="col-motivo">' + _motivo_html(item) + "</td>"
        "</tr>"
    )


def _fila_subida(item):
    fecha = _fecha_corta(item.get("ok_en"))
    texto = "Subida" + (" el " + fecha if fecha else "")
    ultimo_error = str(item.get("motivo") or "").strip()
    extra = ""
    if item.get("estado") == "error" and ultimo_error:
        extra = ' <small class="intento-fallido">· último intento falló: ' + _e(ultimo_error) + "</small>"
    return (
        "<li><span>" + _e(item.get("nombre")) + "</span>"
        '<small class="estado-subida">' + _e(texto) + extra + "</small></li>"
    )


def _tarjeta_curso(resumen):
    total = int(resumen.get("total") or 0)
    subidas = int(resumen.get("subidas") or 0)
    faltantes = int(resumen.get("faltantes") or 0)
    pct = int(round(100 * subidas / total)) if total else 100
    actualizado = _fecha_corta(resumen.get("actualizado"))

    if faltantes:
        cuerpo_faltantes = (
            '<div class="tabla-scroll"><table class="tabla">'
            "<thead><tr><th>Actividad</th><th>Ubicación</th><th>Por qué falta</th></tr></thead>"
            "<tbody>" + "".join(_fila_faltante(i) for i in resumen.get("detalle_faltantes") or []) + "</tbody>"
            "</table></div>"
        )
        boton = (
            '<a class="boton" href="/">' + icon("play")
            + "Reintentar las " + str(faltantes) + " pendientes</a>"
        )
        clase_estado = "con-faltantes"
        resumen_estado = str(faltantes) + " pendiente" + ("s" if faltantes != 1 else "")
    else:
        cuerpo_faltantes = (
            '<p class="curso-completo">' + icon("check-circulo")
            + " Todas las actividades de este curso ya quedaron en PRIZMA.</p>"
        )
        boton = ""
        clase_estado = "completo"
        resumen_estado = "Curso completo"

    detalle_subidas = resumen.get("detalle_subidas") or []
    subidas_html = ""
    if detalle_subidas:
        subidas_html = (
            "<details class=\"subidas-detalle\"><summary>Ver las " + str(subidas)
            + " ya subidas</summary><ul>"
            + "".join(_fila_subida(i) for i in detalle_subidas)
            + "</ul></details>"
        )

    return (
        '<section class="panel curso-estado ' + clase_estado + '">'
        '<div class="curso-estado-cabecera">'
        '<span class="icono-tile grande">' + icon("libro") + "</span>"
        '<div class="curso-estado-titulo">'
        "<h2>" + _e(resumen.get("curso")) + "</h2>"
        "<p>" + _e(resumen.get("programa"))
        + (" · actualizado " + actualizado if actualizado else "")
        + "</p></div>"
        '<div class="curso-estado-progreso">'
        "<strong>" + str(subidas) + " de " + str(total) + "</strong>"
        "<span>" + _e(resumen_estado) + "</span>"
        "</div></div>"
        '<div class="barra-progreso"><span style="width:' + str(pct) + '%"></span></div>'
        + cuerpo_faltantes
        + subidas_html
        + ('<div class="curso-estado-acciones">' + boton + "</div>" if boton else "")
        + "</section>"
    )


def _pagina_cursos(resumenes, pendientes):
    cabecera = (
        '<header class="encabezado"><div class="encabezado-titulo">'
        '<span class="icono-tile grande">' + icon("libro") + "</span>"
        "<div><h1>Cursos</h1><p>Qué actividades de cada curso ya están en PRIZMA y cuáles faltan.</p></div>"
        "</div></header>"
    )

    if not resumenes:
        return cabecera + (
            '<section class="panel estado-vacio">'
            + icon("info")
            + "<div><h2>Todavía no hay cargues registrados</h2>"
            "<p>Cuando hagas un cargue, aquí verás el avance por curso: qué actividades "
            "ya quedaron y por qué falta cada una.</p>"
            '<a class="boton" href="/">Ir a Inicio</a></div></section>'
        )

    banner = ""
    if pendientes:
        banner = (
            '<div class="aviso info" role="status">' + icon("info")
            + "<div><strong>Hay " + str(pendientes) + " actividad(es) pendientes</strong>"
            "<p>En <a href=\"/\">Inicio</a>, vuelve a subir la matriz y el ZIP del curso: "
            "las pendientes se marcan solas y las ya subidas quedan sin marca.</p></div></div>"
        )

    tarjetas = "".join(_tarjeta_curso(r) for r in resumenes)

    return cabecera + banner + '<div class="lista-cursos">' + tarjetas + "</div>"


_CSS_CURSOS = r"""
.lista-cursos { display: grid; gap: 18px; }
.curso-estado-cabecera { display: flex; gap: 16px; align-items: center; }
.curso-estado-titulo { min-width: 0; flex: 1; }
.curso-estado-titulo h2 { margin: 0 0 4px; font-size: 18px; font-weight: 800; }
.curso-estado-titulo p { margin: 0; color: var(--muted); font-size: 13px; }
.curso-estado-progreso { text-align: right; }
.curso-estado-progreso strong { display: block; font-size: 20px; }
.curso-estado-progreso span { font-size: 12px; color: var(--muted); }
.barra-progreso { height: 8px; border-radius: 6px; background: var(--panel-2, rgba(127,127,127,.18)); margin: 14px 0 6px; overflow: hidden; }
.barra-progreso span { display: block; height: 100%; background: var(--exito, #2e9e5b); border-radius: 6px; }
.curso-estado.con-faltantes .barra-progreso span { background: var(--alerta, #d9822b); }
.curso-estado .tabla { margin-top: 12px; }
.curso-estado .col-motivo { overflow-wrap: anywhere; min-width: 220px; }
.motivo-codigo { display: block; color: var(--muted); font-size: 11px; font-family: monospace; margin-top: 4px; }
.motivo-vacio { color: var(--muted); font-style: italic; }
.curso-completo { display: flex; align-items: center; gap: 8px; color: var(--exito, #2e9e5b); font-weight: 600; margin: 12px 0 0; }
.curso-estado-acciones { margin-top: 16px; display: flex; justify-content: flex-end; }
.subidas-detalle { margin-top: 14px; font-size: 13px; }
.subidas-detalle summary { cursor: pointer; color: var(--muted); }
.subidas-detalle ul { list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 6px; }
.subidas-detalle li { display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--linea, rgba(127,127,127,.15)); }
.subidas-detalle li span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.estado-subida { color: var(--exito, #2e9e5b); white-space: nowrap; }
.intento-fallido { color: var(--muted); font-weight: 400; }
.estado-vacio { display: flex; gap: 16px; align-items: flex-start; }
.estado-vacio h2 { margin: 0 0 6px; font-size: 17px; }
.estado-vacio p { margin: 0 0 14px; color: var(--muted); }
"""


@app.get("/cursos", response_class=HTMLResponse)
def cursos_estado():
    resumenes = resumen_cursos(_usuario_actual())
    pendientes = total_faltantes(_usuario_actual())
    return HTMLResponse(
        render_page(
            "Cursos",
            _pagina_cursos(resumenes, pendientes),
            active="cursos",
            page_css=_CSS_CURSOS,
        )
    )
