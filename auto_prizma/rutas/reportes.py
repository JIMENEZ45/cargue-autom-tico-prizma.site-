"""Historial de cargues, reportes guardados y descarga de reportes.
"""

from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    FileResponse,
)
from motor_prizma import normalizar_texto
import csv
import os
import html
from datetime import datetime

from auto_prizma.aplicacion import app
from auto_prizma.config import RESULTADOS_DIR
from auto_prizma.sesiones import (
    _es_de,
    _normalizar_usuario,
    _usuario_actual,
)
from auto_prizma.trabajos import (
    TRABAJOS,
    ZONA_HORARIA_COLOMBIA,
    _cargar_historial,
)


# ============================================================
# HISTORIAL Y REPORTES
# ============================================================

def _formatear_fecha_hora(fecha_iso):
    try:
        fecha = datetime.fromisoformat(fecha_iso)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=ZONA_HORARIA_COLOMBIA)
        else:
            fecha = fecha.astimezone(ZONA_HORARIA_COLOMBIA)
    except Exception:
        return "—", "—"

    fecha_texto = fecha.strftime("%d/%m/%Y")
    hora = fecha.strftime("%I:%M").lstrip("0") or "0:00"
    sufijo = "a. m." if fecha.hour < 12 else "p. m."
    return fecha_texto, f"{hora} {sufijo}"


def _historial_del_usuario(usuario=None):
    """Solo los registros de esa persona.

    Los registros viejos (anteriores al login) no tienen dueno y no se
    muestran a nadie, para no filtrar reportes de otros.
    """
    usuario = usuario or _usuario_actual()

    return [
        registro for registro in _cargar_historial()
        if _normalizar_usuario(
            registro.get("usuario_app")
        ) == _normalizar_usuario(usuario)
    ]


def _pagina_registros(tipo="historial"):
    registros = list(reversed(_historial_del_usuario()))
    es_historial = tipo == "historial"
    activo_historial = "activo" if es_historial else ""
    activo_reportes = "" if es_historial else "activo"

    filas = []
    programas = set()

    if es_historial:
        for registro in registros:
            fecha, hora = _formatear_fecha_hora(registro.get("fecha_iso", ""))
            cursos = registro.get("cursos") or [{"curso": "Curso sin nombre", "programa": "Programa sin nombre"}]

            for item in cursos:
                curso = str(item.get("curso") or "Curso sin nombre")
                programa = str(item.get("programa") or "Programa sin nombre")
                programas.add(programa)
                busqueda = html.escape(f"{curso} {programa}".lower(), quote=True)
                programa_attr = html.escape(programa, quote=True)
                registro_id = html.escape(str(registro.get("id") or ""), quote=True)

                filas.append(
                    f'<tr class="fila-registro" data-busqueda="{busqueda}" data-programa="{programa_attr}">'
                    f'<td class="fecha-celda"><span class="icono-fecha">▣</span><div><strong>{html.escape(fecha)}</strong><small>{html.escape(hora)}</small></div></td>'
                    f'<td>{html.escape(curso)}</td>'
                    f'<td>{html.escape(programa)}</td>'
                    f'<td class="accion-celda"><a class="boton-reporte" href="/reporte-guardado/{registro_id}">◉ <span>Ver reporte</span></a></td>'
                    '</tr>'
                )
    else:
        for registro in registros:
            fecha, hora = _formatear_fecha_hora(registro.get("fecha_iso", ""))
            cursos = registro.get("cursos") or [{"curso": "Curso sin nombre", "programa": "Programa sin nombre"}]
            principal = cursos[0]
            curso = str(principal.get("curso") or "Curso sin nombre")
            programa = str(principal.get("programa") or "Programa sin nombre")
            archivo = str(registro.get("archivo_reporte") or "reporte.csv")
            programas.add(programa)
            busqueda = html.escape(f"{archivo} {curso} {programa}".lower(), quote=True)
            programa_attr = html.escape(programa, quote=True)
            registro_id = html.escape(str(registro.get("id") or ""), quote=True)

            filas.append(
                f'<tr class="fila-registro" data-busqueda="{busqueda}" data-programa="{programa_attr}">'
                f'<td class="fecha-celda"><span class="icono-fecha">▣</span><div><strong>{html.escape(fecha)}</strong><small>{html.escape(hora)}</small></div></td>'
                f'<td class="archivo-reporte" title="{html.escape(archivo, quote=True)}">{html.escape(archivo)}</td>'
                f'<td>{html.escape(curso)}</td>'
                f'<td>{html.escape(programa)}</td>'
                f'<td class="accion-celda"><a class="boton-reporte" href="/reporte-guardado/{registro_id}">◉ <span>Ver</span></a> <a class="boton-reporte" href="/reporte-guardado/{registro_id}?descargar=1">⇩ <span>CSV</span></a></td>'
                '</tr>'
            )

    opciones_programa = ''.join(
        f'<option value="{html.escape(p, quote=True)}">{html.escape(p)}</option>'
        for p in sorted(programas, key=str.casefold)
    )

    if es_historial:
        titulo = "Historial de cargues"
        subtitulo = "Consulta los cursos procesados anteriormente y accede a su reporte correspondiente."
        contador = sum(len(r.get("cursos") or [1]) for r in registros)
        contador_texto = f"{contador} registros"
        placeholder = "Buscar curso o programa..."
        tabla_cabecera = "<th>Fecha y hora</th><th>Curso</th><th>Programa</th><th>Reporte</th>"
        min_table = "900px"
        vacio = "Todavía no hay cargues registrados."
    else:
        titulo = "Reportes generados"
        subtitulo = "Todos los reportes se guardan automáticamente con el nombre del curso y el programa correspondiente."
        contador = len(registros)
        contador_texto = f"{contador} reportes"
        placeholder = "Buscar reporte, curso o programa..."
        tabla_cabecera = "<th>Fecha</th><th>Nombre del reporte</th><th>Curso</th><th>Programa</th><th>Acción</th>"
        min_table = "1120px"
        vacio = "Todavía no hay reportes guardados."

    filas_html = ''.join(filas)
    if not filas_html:
        filas_html = f'<tr><td colspan="5" class="vacio">{html.escape(vacio)}</td></tr>'

    pagina = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITULO__ - Cargue Prizma Pro</title>
    <style>
        :root{--fondo:#f7f8fc;--panel:#fff;--texto:#101828;--muted:#667085;--borde:#e5e7ef;--morado:#5548e8;--sombra:0 12px 34px rgba(29,41,57,.06)}
        *{box-sizing:border-box} body{margin:0;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--fondo);color:var(--texto)}
        .app{min-height:100vh;display:grid;grid-template-columns:235px 1fr}.sidebar{position:sticky;top:0;height:100vh;background:#fff;border-right:1px solid var(--borde);padding:28px 20px;display:flex;flex-direction:column}
        .marca{display:flex;align-items:center;gap:12px;margin-bottom:34px}.logo{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,#6d5dfc,#4338ca);box-shadow:0 8px 20px rgba(79,70,229,.25)}
        .logo svg{width:29px;height:29px;overflow:visible}.logo svg path:first-child{fill:#fff}.logo svg path:last-child{fill:#c7d2fe}.marca strong{display:block;font-size:18px}.marca span{display:block;color:var(--muted);font-size:12px;margin-top:3px}
        .nav{display:grid;gap:8px}.nav-item{padding:12px 14px;border-radius:11px;color:#475467;font-size:14px;display:flex;gap:11px;align-items:center;text-decoration:none;transition:.18s ease}.nav-item:hover{background:#f7f5ff;color:#4f46e5}.nav-item.activo{background:#f1efff;color:#4f46e5;font-weight:700}
        .estado-servicio{margin-top:auto;border:1px solid var(--borde);border-radius:14px;padding:15px}.servicio-linea{font-size:12px;font-weight:800;color:#07894f;margin-bottom:14px}.punto{width:8px;height:8px;background:#12b76a;border-radius:50%;display:inline-block;margin-right:7px}.servicio-mini{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}.chip{background:#eef2ff;color:#4f46e5;border-radius:999px;padding:4px 8px}
        .contenido{padding:30px 34px}.panel{background:#fff;border:1px solid var(--borde);border-radius:18px;box-shadow:var(--sombra);padding:28px;max-width:1320px;margin:0 auto}.cabecera{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}h1{font-size:28px;margin:0 0 7px}.subtitulo{margin:0;color:var(--muted);font-size:14px}.contador{background:#f1efff;color:#4f46e5;border-radius:10px;padding:9px 12px;font-size:12px;font-weight:800;white-space:nowrap}
        .herramientas{display:grid;grid-template-columns:minmax(260px,1fr) 290px;gap:18px;margin:28px 0 22px}.buscador,.filtro{height:52px;border:1px solid #d8dce6;border-radius:11px;background:#fff;display:flex;align-items:center;gap:10px;padding:0 15px;color:#667085}.buscador input,.filtro select{width:100%;border:0;outline:0;background:transparent;font-size:14px;color:#475467}.filtro select{cursor:pointer}
        .tabla-wrap{border:1px solid var(--borde);border-radius:14px;overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px;min-width:__MIN_TABLE__}thead{background:#faf9ff}th{text-align:left;padding:15px 16px;color:#4338ca;font-size:12px;border-bottom:1px solid var(--borde)}td{padding:15px 16px;border-bottom:1px solid #eef0f4;vertical-align:middle;color:#344054}tbody tr:last-child td{border-bottom:0}.fecha-celda{display:flex;align-items:center;gap:11px;white-space:nowrap}.fecha-celda strong{display:block;font-weight:500}.fecha-celda small{display:block;color:#98a2b3;margin-top:4px}.icono-fecha{width:34px;height:34px;border-radius:9px;background:#f4f1ff;color:#6d5dfc;display:grid;place-items:center}.accion-celda{white-space:nowrap}.boton-reporte{display:inline-flex;align-items:center;gap:7px;border:1px solid #d7d0ff;color:#5b4ce8;text-decoration:none;border-radius:9px;padding:9px 12px;font-weight:700;font-size:12px;background:#fff}.boton-reporte:hover{background:#f7f5ff}.archivo-reporte{max-width:390px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vacio{text-align:center;color:#98a2b3;padding:50px 20px!important}.oculta{display:none}
        @media(max-width:1050px){.app{grid-template-columns:1fr}.sidebar{display:none}.contenido{padding:20px}}@media(max-width:700px){.contenido{padding:12px}.panel{padding:18px}.cabecera{flex-direction:column}.herramientas{grid-template-columns:1fr}}
    </style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script>
</head>
<body>
<div class="app">
    <aside class="sidebar">
        <div class="marca"><div class="logo"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div><div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div></div>
        <nav class="nav">
            <a class="nav-item" href="/">⌂ <span>Inicio</span></a>
            <a class="nav-item" href="/tests">▣ <span>Test</span></a>
            <a class="nav-item" href="/cargue-actual">⇧ <span>Cargue actual</span></a>
            <a class="nav-item __ACTIVO_HISTORIAL__" href="/historial">◷ <span>Historial</span></a>
            <a class="nav-item __ACTIVO_REPORTES__" href="/reportes">▥ <span>Reportes</span></a>
            <a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a>
            <a class="nav-item" href="/salir">⏻ <span>Salir</span></a>
        </nav>
        <div class="estado-servicio"><div class="servicio-linea"><span class="punto"></span> Servicio activo</div><div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div><div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div></div>
    </aside>
    <main class="contenido"><section class="panel"><div class="cabecera"><div><h1>__TITULO__</h1><p class="subtitulo">__SUBTITULO__</p></div><div class="contador">▣ &nbsp;__CONTADOR__</div></div><div class="herramientas"><label class="buscador">⌕ <input id="buscar" type="search" placeholder="__PLACEHOLDER__"></label><label class="filtro">▽ <select id="programa"><option value="">Todos los programas</option>__OPCIONES__</select></label></div><div class="tabla-wrap"><table><thead><tr>__CABECERA__</tr></thead><tbody>__FILAS__</tbody></table></div></section></main>
</div>
<script>
const buscar=document.getElementById('buscar');const programa=document.getElementById('programa');function filtrar(){const texto=(buscar.value||'').trim().toLowerCase();const p=programa.value||'';document.querySelectorAll('.fila-registro').forEach(f=>{const okTexto=!texto||(f.dataset.busqueda||'').includes(texto);const okPrograma=!p||f.dataset.programa===p;f.classList.toggle('oculta',!(okTexto&&okPrograma));});}buscar.addEventListener('input',filtrar);programa.addEventListener('change',filtrar);
</script>
</body></html>'''

    pagina = (pagina
        .replace("__TITULO__", html.escape(titulo))
        .replace("__SUBTITULO__", html.escape(subtitulo))
        .replace("__CONTADOR__", html.escape(contador_texto))
        .replace("__PLACEHOLDER__", html.escape(placeholder, quote=True))
        .replace("__OPCIONES__", opciones_programa)
        .replace("__CABECERA__", tabla_cabecera)
        .replace("__FILAS__", filas_html)
        .replace("__MIN_TABLE__", min_table)
        .replace("__ACTIVO_HISTORIAL__", activo_historial)
        .replace("__ACTIVO_REPORTES__", activo_reportes)
    )
    return HTMLResponse(pagina)


@app.get("/historial", response_class=HTMLResponse)
def historial_cargues():
    return _pagina_registros("historial")


@app.get("/reportes", response_class=HTMLResponse)
def reportes_generados():
    return _pagina_registros("reportes")


def _leer_reporte_csv(ruta):
    """Devuelve (cabeceras, filas) del CSV del reporte."""
    with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.reader(archivo)
        filas = [fila for fila in lector if any(str(c).strip() for c in fila)]

    if not filas:
        return [], []

    return filas[0], filas[1:]


def _clase_resultado(valor):
    """Color segun el resultado de la fila."""
    texto = normalizar_texto(valor)

    if "cargad" in texto or "exito" in texto or texto == "ok":
        return ("#ecfdf3", "#067647", "#abefc6")

    if "omitid" in texto or "ya exist" in texto or "duplicad" in texto:
        return ("#fffaeb", "#b54708", "#fedf89")

    if "cancel" in texto:
        return ("#f2f4f7", "#475467", "#e4e7ec")

    return ("#fef3f2", "#b42318", "#fecdca")


def _pagina_reporte_html(titulo, subtitulo, ruta_csv, url_descarga):
    """Muestra el reporte como tabla dentro de la app."""

    def e(valor):
        return html.escape(str(valor or ""))

    try:
        cabeceras, filas = _leer_reporte_csv(ruta_csv)
    except OSError:
        cabeceras, filas = [], []

    # Indice de la columna Resultado, para colorear y contar.
    indice_resultado = None
    for posicion, nombre in enumerate(cabeceras):
        if normalizar_texto(nombre) == normalizar_texto("Resultado"):
            indice_resultado = posicion
            break

    conteo = {}
    filas_html = ""

    for fila in filas:
        resultado = ""
        if indice_resultado is not None and indice_resultado < len(fila):
            resultado = str(fila[indice_resultado] or "").strip()

        conteo[resultado or "—"] = conteo.get(resultado or "—", 0) + 1
        fondo, letra, borde = _clase_resultado(resultado)

        celdas = ""
        for posicion, valor in enumerate(fila):
            if posicion == indice_resultado:
                celdas += (
                    '<td style="white-space:nowrap;">'
                    '<span style="display:inline-block;padding:3px 10px;'
                    'border-radius:999px;font-size:11px;font-weight:800;'
                    'background:' + fondo + ';color:' + letra + ';'
                    'border:1px solid ' + borde + ';">'
                    + e(valor) + "</span></td>"
                )
            else:
                celdas += (
                    '<td style="padding:9px 14px;border-bottom:1px solid #f2f4f7;'
                    'color:#475467;vertical-align:top;">' + e(valor) + "</td>"
                )

        filas_html += (
            '<tr>' + celdas.replace(
                '<td style="white-space:nowrap;">',
                '<td style="white-space:nowrap;padding:9px 14px;'
                'border-bottom:1px solid #f2f4f7;vertical-align:top;">',
            ) + "</tr>"
        )

    encabezados_html = "".join(
        '<th style="text-align:left;padding:10px 14px;font-size:11px;'
        'letter-spacing:.03em;color:#667085;background:#f9fafb;'
        'border-bottom:1px solid #e4e7ec;position:sticky;top:0;">'
        + e(nombre).upper() + "</th>"
        for nombre in cabeceras
    )

    tarjetas = ""
    for valor, cantidad in sorted(
        conteo.items(), key=lambda par: -par[1]
    ):
        fondo, letra, borde = _clase_resultado(valor)
        tarjetas += (
            '<div style="background:' + fondo + ';border:1px solid ' + borde
            + ';border-radius:12px;padding:12px 16px;min-width:120px;">'
            '<div style="font-size:22px;font-weight:800;color:' + letra + ';">'
            + str(cantidad) + "</div>"
            '<div style="font-size:11.5px;color:#667085;margin-top:2px;">'
            + e(valor) + "</div></div>"
        )

    if not filas:
        cuerpo = (
            '<div style="padding:48px 24px;text-align:center;color:#667085;">'
            "El reporte no tiene filas todavía.</div>"
        )
    else:
        cuerpo = (
            '<div style="overflow:auto;max-height:62vh;">'
            '<table style="width:100%;border-collapse:collapse;font-size:12.5px;">'
            "<thead><tr>" + encabezados_html + "</tr></thead>"
            "<tbody>" + filas_html + "</tbody></table></div>"
        )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titulo)} - Cargue Prizma Pro</title>
<style>
:root{{--fondo:#f7f8fc;--texto:#101828;--muted:#667085;--borde:#e5e7ef}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Inter,ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
background:var(--fondo);color:var(--texto)}}
.app{{min-height:100vh;display:grid;grid-template-columns:235px 1fr}}
.sidebar{{height:100vh;background:#fff;border-right:1px solid var(--borde);
padding:28px 20px;display:flex;flex-direction:column}}
.marca{{display:flex;align-items:center;gap:12px;margin-bottom:34px}}
.logo{{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;
background:linear-gradient(145deg,#6d5dfc,#4338ca)}}
.logo svg{{width:29px;height:29px}}
.logo svg path:first-child{{fill:#fff}}.logo svg path:last-child{{fill:#c7d2fe}}
.marca strong{{display:block;font-size:18px}}
.marca span{{display:block;color:var(--muted);font-size:12px;margin-top:3px}}
.nav{{display:grid;gap:8px}}
.nav-item{{padding:12px 14px;border-radius:11px;color:#475467;font-size:14px;
display:flex;gap:11px;align-items:center;text-decoration:none}}
.nav-item:hover{{background:#f7f5ff;color:#4f46e5}}
.nav-item.activo{{background:#f1efff;color:#4f46e5;font-weight:700}}
.estado-servicio{{margin-top:auto;border:1px solid var(--borde);border-radius:14px;padding:15px}}
.servicio-linea{{font-size:12px;font-weight:800;color:#07894f;margin-bottom:14px}}
.punto{{width:8px;height:8px;background:#12b76a;border-radius:50%;display:inline-block;margin-right:7px}}
.servicio-mini{{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}}
.chip{{background:#eef2ff;color:#4f46e5;border-radius:999px;padding:4px 8px}}
.contenido{{padding:30px 34px 44px;min-width:0}}
.panel{{background:#fff;border:1px solid var(--borde);border-radius:18px;
box-shadow:0 10px 30px rgba(29,41,57,.05);overflow:hidden}}
.cabecera{{display:flex;justify-content:space-between;gap:18px;
align-items:flex-start;margin-bottom:20px;flex-wrap:wrap}}
.cabecera h1{{font-size:26px;margin:0 0 6px}}
.cabecera p{{margin:0;color:var(--muted);font-size:13.5px}}
.acciones{{display:flex;gap:10px;flex-wrap:wrap}}
.boton{{display:inline-flex;align-items:center;gap:8px;padding:11px 16px;
border-radius:10px;text-decoration:none;font-size:13px;font-weight:700}}
.boton-primario{{background:linear-gradient(90deg,#5548e8,#6546e8);color:#fff}}
.boton-secundario{{background:#fff;color:#4f46e5;border:1px solid #d8d6f8}}
.tarjetas{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}}
tbody tr:hover{{background:#fafaff}}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head>
<body><div class="app">
<aside class="sidebar">
  <div class="marca">
    <div class="logo"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div>
    <div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div>
  </div>
  <nav class="nav">
    <a class="nav-item" href="/">⌂ <span>Inicio</span></a>
    <a class="nav-item" href="/tests">▣ <span>Test</span></a>
    <a class="nav-item" href="/cargue-actual">⇧ <span>Cargue actual</span></a>
    <a class="nav-item" href="/historial">◷ <span>Historial</span></a>
    <a class="nav-item activo" href="/reportes">▥ <span>Reportes</span></a>
    <a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a>
    <a class="nav-item" href="/salir">⏻ <span>Salir</span></a>
  </nav>
  <div class="estado-servicio"><div class="servicio-linea"><span class="punto"></span> Servicio activo</div><div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div><div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div></div>
</aside>
<main class="contenido">
  <section class="cabecera">
    <div>
      <h1>{e(titulo)}</h1>
      <p>{e(subtitulo)}</p>
    </div>
    <div class="acciones">
      <a class="boton boton-secundario" href="/reportes">← Volver</a>
      <a class="boton boton-primario" href="{e(url_descarga)}">⇩ Descargar CSV</a>
    </div>
  </section>
  <div class="tarjetas">{tarjetas}</div>
  <div class="panel">{cuerpo}</div>
</main></div></body></html>"""


@app.get("/reporte-guardado/{registro_id}")
def descargar_reporte_guardado(registro_id: str, descargar: int = 0):
    registro = next(
        (
            r for r in _historial_del_usuario()
            if r.get("id") == registro_id
        ),
        None,
    )

    if not registro:
        return JSONResponse({"error": "Reporte no encontrado"}, status_code=404)

    nombre = os.path.basename(str(registro.get("archivo_reporte") or ""))
    ruta = os.path.join(RESULTADOS_DIR, nombre)

    if not nombre or not os.path.isfile(ruta):
        return JSONResponse({"error": "El archivo del reporte ya no está disponible"}, status_code=404)

    if descargar:
        return FileResponse(ruta, media_type="text/csv", filename=nombre)

    cursos = registro.get("cursos") or []
    if cursos:
        titulo = str(cursos[0].get("curso") or "Reporte del cargue")
        subtitulo = " · ".join(
            filter(None, [
                str(cursos[0].get("programa") or ""),
                _formatear_fecha_hora(registro.get("fecha_iso"))[0],
            ])
        )
    else:
        titulo = "Reporte del cargue"
        subtitulo = _formatear_fecha_hora(registro.get("fecha_iso"))[0]

    return HTMLResponse(_pagina_reporte_html(
        titulo,
        subtitulo,
        ruta,
        "/reporte-guardado/" + registro_id + "?descargar=1",
    ))


# ============================================================
# DESCARGAR REPORTE
# ============================================================

@app.get(
    "/reporte/{trabajo_id}",
)
def descargar_reporte(
    trabajo_id: str,
    descargar: int = 0,
):

    trabajo = TRABAJOS.get(
        trabajo_id
    )

    if not trabajo or not _es_de(trabajo, _usuario_actual()):

        return JSONResponse(
            {
                "error":
                    "Trabajo no encontrado"
            },
            status_code=404,
        )

    ruta = trabajo[
        "ruta_reporte"
    ]

    if not os.path.isfile(
        ruta
    ):

        return JSONResponse(
            {
                "error":
                    "Reporte todavía no disponible"
            },
            status_code=404,
        )

    if descargar:
        return FileResponse(
            ruta,
            media_type="text/csv",
            filename=os.path.basename(ruta),
        )

    cursos = trabajo.get("cursos") or []
    titulo = (
        str(cursos[0].get("curso") or "Reporte del cargue")
        if cursos else "Reporte del cargue"
    )
    subtitulo = (
        str(trabajo.get("mensaje") or "")
        or "Resultado del cargue en PRIZMA"
    )

    return HTMLResponse(_pagina_reporte_html(
        titulo,
        subtitulo,
        ruta,
        "/reporte/" + trabajo_id + "?descargar=1",
    ))
