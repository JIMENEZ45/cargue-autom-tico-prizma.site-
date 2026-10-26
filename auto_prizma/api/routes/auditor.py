"""Auditor de recursos: cruza la matriz de recursos del curso con el ZIP.

Es la version web del auditor local `curso-checker`
(~/Documents/curso-checker). La logica de cruce (prefijos de tema,
nombres truncados, copias "(1)", similitud, titulos internos H5P) vive en
auto_prizma/auditor/procesar.py, copiada TAL CUAL del proyecto original.
Aqui solo se suben la matriz (CSV) y los recursos (ZIP) y se pinta el
dictamen. Solo audita: no modifica archivos ni carga nada a PRIZMA.
"""

import glob
import html
import os
import re
import shutil
import uuid
import zipfile

from fastapi import File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from auto_prizma.auditor.procesar import ejecutar_auditoria
from auto_prizma.core.application import app
from auto_prizma.core.config import AUDITORIA_DIR, TEMP_DIR
from auto_prizma.web.icons import icon
from auto_prizma.web.layout import render_page


def _e(valor):
    return html.escape(str(valor or ""))


def _ubicacion(item):
    partes = []
    if str(item.get("fila") or ""):
        partes.append("Fila " + str(item["fila"]))
    if str(item.get("unidad") or ""):
        partes.append(str(item["unidad"]))
    if str(item.get("semana") or ""):
        partes.append(str(item["semana"]))
    return " · ".join(_e(p) for p in partes)


def _fila_recurso(item):
    """Fila de un recurso auditado (badge de estado + detalle)."""
    estado = str(item.get("estado") or "")
    etiquetas = {
        "ok": ("badge-ok", "OK"),
        "alerta": ("badge-alerta", "Alerta"),
        "faltante": ("badge-faltante", "Faltante"),
        "fuera-de-alcance": ("badge-na", "Fuera de alcance"),
    }
    clase, texto = etiquetas.get(estado, ("badge-na", estado))
    sugerido = item.get("sugerencia") or {}
    extra = ""
    if sugerido.get("archivo"):
        extra = (
            '<p class="aud-sugerencia">Quizás es: <code>'
            + _e(sugerido["archivo"])
            + "</code> (similitud "
            + _e(f"{round((sugerido.get('similitud') or 0) * 100)}%)")
            + "</p>"
        )
    archivo = ""
    if item.get("archivo"):
        archivo = (
            '<p class="aud-archivo">' + icon("documento") + " <code>"
            + _e(item["archivo"]) + "</code></p>"
        )
    return (
        '<li class="aud-recurso">'
        + '<span class="aud-badge ' + clase + '">' + texto + "</span>"
        + "<div>"
        + "<strong>" + _e(item.get("nombre")) + "</strong>"
        + '<span class="aud-ubicacion">' + _ubicacion(item) + "</span>"
        + archivo
        + '<p class="aud-detalle">' + _e(item.get("detalle")) + "</p>"
        + extra
        + "</div></li>"
    )


# ============================================================
# PAGINA
# ============================================================

def _historial_auditorias():
    if not os.path.isdir(AUDITORIA_DIR):
        return ""
    rutas = sorted(
        glob.glob(os.path.join(AUDITORIA_DIR, "auditoria_*.md")),
        reverse=True,
    )[:10]
    if not rutas:
        return ""
    items = ""
    for ruta in rutas:
        nombre = os.path.basename(ruta)
        fecha = _e(nombre[len("auditoria_"):-len(".md")].rsplit("_", 1)[0])
        items += (
            '<li><a href="/auditor/reporte/' + _e(nombre) + '">'
            + icon("descargar") + "Auditoría " + fecha + "</a></li>"
        )
    return (
        '<section class="panel"><h2>Auditorías anteriores</h2>'
        '<ul class="aud-historial">' + items + "</ul></section>"
    )


def _pagina_formulario(error="", advertencias=()):
    aviso = ""
    if error:
        aviso = (
            '<div class="aviso error" role="alert">' + icon("alerta-circulo")
            + "<div><strong>No se pudo auditar</strong><p>" + _e(error)
            + "</p></div></div>"
        )
    if advertencias:
        avisos_html = "".join(
            "<li>" + _e(a) + "</li>" for a in advertencias if a
        )
        if avisos_html:
            aviso += (
                '<div class="aviso ambar" role="status">' + icon("alerta")
                + "<div><strong>Avisos de la auditoría</strong><ul>"
                + avisos_html + "</ul></div></div>"
            )

    contenido = (
        '<section class="panel">'
        "<h2>Auditor de recursos del curso</h2>"
        "<p>Cruza la <strong>matriz de recursos</strong> del curso (CSV exportado "
        "de Excel) con el <strong>ZIP de archivos</strong> y verifica, recurso por "
        "recurso, que el nombre y —en los H5P— el título interno calcen con la "
        "matriz. <strong>Solo audita</strong>: no modifica archivos ni carga nada "
        "a PRIZMA.</p>"
        '<form class="aud-form" method="post" action="/auditor" '
        'enctype="multipart/form-data">'
        "<label>Matriz de recursos (CSV)"
        '<input type="file" name="matriz" accept=".csv,.txt" required>'
        "</label>"
        "<label>ZIP con los archivos del curso"
        '<input type="file" name="recursos" accept=".zip" required>'
        "</label>"
        "<label>Syllabus (opcional: .docx, .pdf o .txt)"
        '<input type="file" name="syllabus">'
        "</label>"
        '<button class="boton" type="submit">' + icon("escudo")
        + "Auditar</button>"
        "</form></section>"
        + _historial_auditorias()
    )
    return render_page(
        "Auditor de recursos",
        aviso + contenido,
        active="auditor",
        page_css=_CSS,
    )


def _pagina_resultado(res, nombre_matriz):
    conteo = res["conteo"]
    corregir = [
        r for r in res["resultados"] if r["estado"] in ("alerta", "faltante")
    ]
    oks = [r for r in res["resultados"] if r["estado"] == "ok"]
    fuera = [
        r for r in res["resultados"] if r["estado"] == "fuera-de-alcance"
    ]

    if corregir:
        veredicto = (
            '<div class="aviso error" role="alert">' + icon("alerta-circulo")
            + "<div><strong>Hay "
            + str(len(corregir))
            + " recurso(s) por corregir</strong><p>Revisa las alertas y los "
            "faltantes; el reporte completo se puede descargar abajo.</p></div></div>"
        )
    else:
        veredicto = (
            '<div class="aviso ok" role="status">' + icon("check-circulo")
            + "<div><strong>Todo calza</strong><p>Los "
            + str(conteo["ok"])
            + " recurso(s) auditables de la matriz tienen su archivo "
            "(nombre y título interno OK).</p></div></div>"
        )

    fichas = (
        '<div class="aud-resumen">'
        + _ficha("OK", conteo["ok"], "ok")
        + _ficha("Alerta", conteo["alerta"], "alerta")
        + _ficha("Faltante", conteo["faltante"], "faltante")
        + _ficha("Fuera de alcance", conteo["fuera-de-alcance"], "na")
        + _ficha("Huérfanos (sin fila)", len(res["huerfanos"]), "na")
        + _ficha("Archivos en el ZIP", res["total_archivos"], "na")
        + "</div>"
    )

    seccion_corregir = ""
    if corregir:
        seccion_corregir = (
            '<section class="panel"><h2>Por corregir ('
            + str(len(corregir))
            + ")</h2><ul class='aud-lista'>"
            + "".join(_fila_recurso(r) for r in corregir)
            + "</ul></section>"
        )

    def _plegable(titulo, items):
        if not items:
            return ""
        return (
            '<details class="panel aud-detalle-panel"><summary>'
            + titulo + " (" + str(len(items)) + ")</summary><ul class='aud-lista'>"
            + "".join(_fila_recurso(r) for r in items)
            + "</ul></details>"
        )

    secciones_extra = (
        _plegable("Correctos (OK)", oks)
        + _plegable("Fuera de alcance (video/otros, no se auditan)", fuera)
    )

    huerfanos = ""
    if res["huerfanos"]:
        huerfanos = (
            '<details class="panel aud-detalle-panel"><summary>Huérfanos ('
            + str(len(res["huerfanos"]))
            + ") — archivos sin fila en la matriz</summary><ul class='aud-lista'>"
            + "".join(
                "<li class='aud-recurso'><span class='aud-badge badge-na'>—"
                "</span><div><code>" + _e(rel) + "</code></div></li>"
                for rel in res["huerfanos"]
            )
            + "</ul></details>"
        )

    revision = ""
    if res["archivos_detalle"]:
        filas = "".join(
            "<tr><td>" + ("✓" if f.get("abre") == "ok" else "✗") + "</td>"
            "<td><code>" + _e(f.get("archivo")) + "</code></td>"
            "<td>" + _e(f.get("ext")) + "</td>"
            "<td>" + _e(f.get("nota")) + "</td></tr>"
            for f in res["archivos_detalle"]
        )
        revision = (
            '<details class="panel aud-detalle-panel">'
            "<summary>Revisión 1 a 1 — todos los archivos ("
            + str(len(res["archivos_detalle"]))
            + ")</summary><div class='tabla-scroll'><table class='tabla'>"
            "<thead><tr><th>Abre</th><th>Archivo</th><th>Ext</th>"
            "<th>Al abrir / título</th></tr></thead><tbody>"
            + filas + "</tbody></table></div></details>"
        )

    advertencias = ""
    if res["advertencias"]:
        advertencias = (
            '<details class="panel aud-detalle-panel"><summary>Advertencias ('
            + str(len(res["advertencias"])) + ")</summary><ul>"
            + "".join("<li>" + _e(a) + "</li>" for a in res["advertencias"])
            + "</ul></details>"
        )

    syllabus = ""
    sy = res.get("syllabus")
    if sy:
        if sy.get("error"):
            cuerpo = "No se pudo leer: " + str(sy["error"])
            clase, ico = "error", "alerta-circulo"
        elif sy.get("ok"):
            cuerpo = "El syllabus es consistente con la matriz."
            clase, ico = "ok", "check-circulo"
        else:
            cuerpo = (
                str(sy.get("avisos", 0))
                + " aviso(s): revisa el reporte para el detalle."
            )
            clase, ico = "ambar", "alerta"
        syllabus = (
            '<div class="aviso ' + clase + '" role="status">' + icon(ico)
            + "<div><strong>Syllabus: " + _e(sy.get("nombre") or "")
            + "</strong><p>" + html.escape(cuerpo) + "</p></div></div>"
        )

    nombre_reporte = os.path.basename(res["reporte_md"])
    contenido = (
        '<section class="panel aud-cabecera">'
        "<h2>Auditoría de <code>" + _e(nombre_matriz) + "</code></h2>"
        "<p>" + icon("zip") + " " + str(res["total_archivos"])
        + " archivo(s) en el ZIP · " + str(res["total_auditables"])
        + " recurso(s) auditables en la matriz</p>"
        '<a class="boton" href="/auditor/reporte/' + _e(nombre_reporte) + '">'
        + icon("descargar") + "Descargar reporte (.md)</a>"
        '<a class="boton" href="/auditor">Nueva auditoría</a>'
        "</section>"
        + veredicto + fichas + syllabus + seccion_corregir
        + secciones_extra + huerfanos + revision + advertencias
    )
    return render_page(
        "Auditor de recursos",
        contenido,
        active="auditor",
        page_css=_CSS,
    )


def _ficha(texto, valor, clase):
    return (
        '<span class="aud-ficha aud-ficha--' + clase + '">'
        + "<strong>" + str(valor) + "</strong>" + _e(texto) + "</span>"
    )


_CSS = r"""
.aud-form { display: grid; gap: 14px; max-width: 520px; margin-top: 8px; }
.aud-form label { display: grid; gap: 6px; font-weight: 700; font-size: 14px; }
.aud-resumen { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
.aud-ficha { border: 1px solid var(--borde, #d8d8d8); border-radius: 10px;
  padding: 8px 14px; display: flex; gap: 6px; align-items: baseline;
  font-size: 13px; }
.aud-ficha strong { font-size: 16px; }
.aud-ficha--ok strong { color: #15803d; }
.aud-ficha--alerta strong { color: #b45309; }
.aud-ficha--faltante strong { color: #b91c1c; }
.aud-lista { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.aud-recurso { display: flex; gap: 10px; align-items: flex-start;
  border-bottom: 1px solid var(--borde-suave, #eee); padding-bottom: 8px; }
.aud-recurso > div { min-width: 0; }
.aud-ubicacion { margin-left: 8px; font-size: 12px; opacity: .7; }
.aud-archivo { margin: 2px 0; font-size: 13px; }
.aud-detalle { margin: 2px 0 0; font-size: 13px; opacity: .85; }
.aud-sugerencia { margin: 2px 0 0; font-size: 13px; }
.aud-badge { flex: none; font-size: 11px; font-weight: 800; border-radius: 8px;
  padding: 3px 8px; text-transform: uppercase; letter-spacing: .3px; }
.badge-ok { background: #dcfce7; color: #15803d; }
.badge-alerta { background: #fef3c7; color: #b45309; }
.badge-faltante { background: #fee2e2; color: #b91c1c; }
.badge-na { background: #f1f5f9; color: #64748b; }
.aud-detalle-panel summary { cursor: pointer; font-weight: 700; }
.aud-historial { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.aud-cabecera .boton { margin-right: 8px; }
[data-theme="dark"] .badge-ok { background: #14532d; color: #bbf7d0; }
[data-theme="dark"] .badge-alerta { background: #78350f; color: #fde68a; }
[data-theme="dark"] .badge-faltante { background: #7f1d1d; color: #fecaca; }
[data-theme="dark"] .badge-na { background: #1e293b; color: #94a3b8; }
"""


# ============================================================
# RUTAS
# ============================================================

@app.get("/auditor", response_class=HTMLResponse)
def pagina_auditor():
    return _pagina_formulario()


@app.post("/auditor", response_class=HTMLResponse)
async def auditar_curso(
    matriz: UploadFile = File(...),
    recursos: UploadFile = File(...),
    syllabus: UploadFile | None = File(default=None),
):
    nombre_matriz = os.path.basename(matriz.filename or "matriz.csv")
    if not nombre_matriz.lower().endswith((".csv", ".txt")):
        return _pagina_formulario(
            error="La matriz debe ser un CSV. Si es de Excel: "
            "Archivo → Guardar como → CSV UTF-8."
        )

    texto_matriz = (await matriz.read()).decode("utf-8-sig", errors="replace")

    os.makedirs(TEMP_DIR, exist_ok=True)
    ruta_zip = os.path.join(TEMP_DIR, "auditoria_" + uuid.uuid4().hex + ".zip")
    res = None
    try:
        with open(ruta_zip, "wb") as fh:
            shutil.copyfileobj(recursos.file, fh)
        if not zipfile.is_zipfile(ruta_zip):
            return _pagina_formulario(
                error="El archivo de recursos no es un ZIP válido."
            )
        syllabus_bytes = await syllabus.read() if syllabus else None
        res = ejecutar_auditoria(
            ruta_zip,
            None,
            AUDITORIA_DIR,
            matriz_texto=texto_matriz,
            matriz_nombre=nombre_matriz,
            syllabus=syllabus_bytes,
            syllabus_nombre=os.path.basename(syllabus.filename or "")
            if syllabus else "",
        )
    finally:
        if os.path.exists(ruta_zip):
            os.remove(ruta_zip)

    if not res.get("ok"):
        return _pagina_formulario(
            error=res.get("error") or "Error desconocido al auditar.",
            advertencias=res.get("advertencias") or [],
        )
    return _pagina_resultado(res, nombre_matriz)


@app.get("/auditor/reporte/{nombre}", response_class=HTMLResponse)
def descargar_reporte(nombre):
    if re.fullmatch(r"auditoria_[0-9_]+\.md", nombre or "") is None:
        return HTMLResponse("Reporte no encontrado", status_code=404)
    ruta = os.path.join(AUDITORIA_DIR, nombre)
    if not os.path.isfile(ruta):
        return HTMLResponse("Reporte no encontrado", status_code=404)
    return FileResponse(
        ruta,
        media_type="text/markdown; charset=utf-8",
        filename=nombre,
    )
