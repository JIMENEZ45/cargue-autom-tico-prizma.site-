"""Iniciar, seguir, cancelar y consultar el estado de los cargues.
"""

from fastapi import (
    Form,
    BackgroundTasks,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from auto_prizma.automation.prizma.engine import validar_credenciales_prizma
import os
import html
from datetime import datetime

from auto_prizma.core.application import app
from auto_prizma.services.auth import (
    _es_de,
    _nombre_visible,
    _usuario_actual,
)
from auto_prizma.services.upload_jobs import (
    COLA_CARGUES,
    COLA_CONDICION,
    TRABAJOS,
    ZONA_HORARIA_COLOMBIA,
    _ahora_colombia_iso,
    _encolar_trabajo,
    _posicion_en_cola,
    _validar_seleccion_actividades,
)
from auto_prizma.web.views import generar_html


# ============================================================
# INICIAR
# ============================================================

@app.post(
    "/iniciar/{trabajo_id}",
    response_class=HTMLResponse,
)
def iniciar_trabajo(
    trabajo_id: str,
    background_tasks: BackgroundTasks,
    usuario_prizma: str = Form(...),
    contrasena_prizma: str = Form(...),
    actividades_seleccionadas: list[str] = Form(default=[]),
):
    trabajo = TRABAJOS.get(trabajo_id)
    if not trabajo or not _es_de(trabajo, _usuario_actual()):
        return HTMLResponse("<h2>Trabajo no encontrado.</h2><a href='/'>Volver</a>", status_code=404)

    seleccion_validada = _validar_seleccion_actividades(
        actividades_seleccionadas,
        trabajo.get("resultado_analisis") or {},
    )
    if not seleccion_validada:
        return generar_html(
            resultado=trabajo.get("resultado_analisis"),
            trabajo_id=trabajo_id,
            error=(
                "Selecciona al menos una actividad para cargar en PRIZMA. "
                "Puedes elegir por tipo de recurso o actividad individual."
            ),
            seleccion_actual=[],
        )

    trabajo["seleccion_actividades"] = seleccion_validada

    usuario_prizma = usuario_prizma.strip()
    if not usuario_prizma or not contrasena_prizma:
        return generar_html(
            resultado=trabajo.get("resultado_analisis"),
            trabajo_id=trabajo_id,
            error="Debes ingresar el usuario y la contraseña de PRIZMA.",
            seleccion_actual=seleccion_validada,
        )

    if trabajo.get("etapa") not in ["analizado", "error"]:
        return HTMLResponse("<h2>Este trabajo ya fue iniciado.</h2>")

    # Validar el acceso antes de encolar el curso.
    trabajo["etapa"] = "validando_login"
    trabajo["mensaje"] = "Validando usuario y contraseña en PRIZMA..."
    validacion = validar_credenciales_prizma(usuario_prizma, contrasena_prizma)

    if not validacion.get("ok"):
        trabajo["etapa"] = "analizado"
        trabajo["mensaje"] = validacion.get("mensaje", "No fue posible validar el acceso a PRIZMA.")
        return generar_html(
            resultado=trabajo.get("resultado_analisis"),
            trabajo_id=trabajo_id,
            error=trabajo["mensaje"],
            seleccion_actual=seleccion_validada,
        )

    _encolar_trabajo(trabajo_id, usuario_prizma, contrasena_prizma)

    html_progreso = r"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cargue en progreso - Cargue Prizma Pro</title>
        <style>
            :root {
                --fondo:#f7f8fc; --panel:#fff; --texto:#101828; --muted:#667085;
                --borde:#e5e7ef; --morado:#5548e8; --verde:#0ea968; --rojo:#ef4444;
                --sombra:0 10px 30px rgba(29,41,57,.06);
            }
            * { box-sizing:border-box; }
            body { margin:0; font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--fondo); color:var(--texto); }
            .app { min-height:100vh; display:grid; grid-template-columns:235px 1fr; }
            .sidebar { position:sticky; top:0; height:100vh; background:#fff; border-right:1px solid var(--borde); padding:28px 20px; display:flex; flex-direction:column; }
            .marca { display:flex; align-items:center; gap:12px; margin-bottom:34px; }
            .logo { width:44px; height:44px; border-radius:13px; display:grid; place-items:center; background:linear-gradient(145deg,#6d5dfc,#4338ca); box-shadow:0 8px 20px rgba(79,70,229,.25); flex:0 0 44px; }
            .logo svg{width:29px;height:29px;overflow:visible}.logo svg path:first-child{fill:#fff}.logo svg path:last-child{fill:#c7d2fe}
            .marca strong { display:block; font-size:18px; }
            .marca span { display:block; color:var(--muted); font-size:12px; margin-top:3px; }
            .nav { display:grid; gap:8px; }
            .nav-item { padding:12px 14px; border-radius:11px; color:#475467; font-size:14px; display:flex; gap:11px; align-items:center; text-decoration:none; transition:.18s ease; }
            a.nav-item:hover{background:#f7f5ff;color:#4f46e5}.nav-item.activo{background:#f1efff;color:#4f46e5;font-weight:700}.nav-item.proximamente{opacity:.48;cursor:default}.nav-item.proximamente small{margin-left:auto;font-size:9px}
            .estado-servicio { margin-top:auto; border:1px solid var(--borde); border-radius:14px; padding:15px; background:#fff; }
            .servicio-linea { display:flex; align-items:center; gap:8px; color:#07894f; font-size:13px; font-weight:700; }
            .punto { width:8px; height:8px; border-radius:50%; background:#15b76a; }
            .servicio-mini { margin-top:13px; display:flex; justify-content:space-between; font-size:12px; color:var(--muted); }
            .chip { background:#eef4ff; color:#3538cd; padding:4px 8px; border-radius:999px; }
            .contenido { padding:28px 34px 45px; max-width:1450px; width:100%; margin:0 auto; }
            .panel { background:#fff; border:1px solid var(--borde); border-radius:16px; box-shadow:var(--sombra); }
            .cabecera-progreso { padding:25px 28px; }
            .cabecera-linea { display:flex; justify-content:space-between; align-items:center; gap:20px; }
            .cabecera-titulo { display:flex; gap:13px; align-items:center; }
            .icono-subida { width:43px; height:43px; border-radius:12px; background:#f1efff; color:#4f46e5; display:grid; place-items:center; font-size:21px; }
            .cabecera-titulo h1 { margin:0; font-size:22px; }
            .porcentaje { font-size:14px; color:var(--muted); }
            .porcentaje strong { font-size:18px; color:#4f46e5; }
            .barra { height:11px; background:#eef0f5; border-radius:999px; overflow:hidden; margin:22px 0 14px; }
            .progreso { height:100%; width:0%; border-radius:999px; background:linear-gradient(90deg,#6759f5,#4f46e5); transition:width .35s ease; }
            .estado { color:#4f46e5; font-size:14px; font-weight:600; line-height:1.45; }
            .numeros { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; margin:20px 0; }
            .numero { padding:20px; display:flex; align-items:center; gap:15px; }
            .numero-icono { width:48px; height:48px; border-radius:50%; display:grid; place-items:center; font-weight:900; font-size:20px; }
            .numero.procesadas .numero-icono { background:#eef4ff; color:#4f46e5; }
            .numero.exitosas .numero-icono { background:#e9f9f1; color:#0a9b5b; }
            .numero.errores .numero-icono { background:#fff0f1; color:#e5484d; }
            .numero span { display:block; color:var(--muted); font-size:13px; }
            .numero strong { display:block; font-size:28px; margin-top:2px; }
            .zona { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(280px,.75fr); gap:20px; align-items:start; }
            .lista-panel, .estado-panel { padding:23px; }
            .titulo-panel { margin:0 0 16px; font-size:17px; }
            .lista-actividades { max-height:570px; overflow:auto; border:1px solid var(--borde); border-radius:12px; }
            .actividad-progreso { display:grid; grid-template-columns:27px 1fr; gap:10px; align-items:start; padding:11px 13px; border-bottom:1px solid #eef0f4; background:#fff; }
            .actividad-progreso:last-child { border-bottom:0; }
            .actividad-icono { width:23px; height:23px; display:grid; place-items:center; font-size:15px; }
            .actividad-nombre { font-size:13px; line-height:1.4; }
            .actividad-error { color:#b42318; font-size:11px; margin-top:4px; word-break:break-word; }
            .actividad-ok { background:#fbfffd; }
            .actividad-error-fila { background:#fffafa; }
            .actividad-procesando { background:#f7f6ff; box-shadow:inset 3px 0 0 #5b48e8; }
            .estado-panel .estado-caja { background:#f8f9fc; border:1px solid var(--borde); border-radius:12px; padding:17px; margin-bottom:14px; }
            .estado-caja span { display:block; color:var(--muted); font-size:12px; }
            .estado-caja strong { display:block; margin-top:6px; font-size:14px; line-height:1.45; }
            .leyenda { display:grid; gap:12px; margin-top:22px; }
            .leyenda div { display:flex; align-items:center; gap:9px; color:#475467; font-size:13px; }
            .final { margin-top:18px; padding:18px; border-radius:12px; background:#ecfdf5; border:1px solid #a7f3d0; }
            .final h3 { margin:0 0 6px; }
            .final p { margin:0; color:#475467; font-size:13px; }
            .descarga { display:inline-flex; margin-top:14px; padding:11px 14px; border-radius:9px; background:#4f46e5; color:#fff; text-decoration:none; font-size:13px; font-weight:800; }
            .pie { margin-top:18px; color:var(--muted); font-size:12px; text-align:center; }
            @media(max-width:1050px) { .app{grid-template-columns:1fr}.sidebar{display:none}.contenido{padding:20px}.zona{grid-template-columns:1fr} }
            @media(max-width:680px) { .numeros{grid-template-columns:1fr}.contenido{padding:14px}.cabecera-linea{align-items:flex-start;flex-direction:column} }
        </style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script>
    </head>
    <body>
        <div class="app">
            <aside class="sidebar">
                <div class="marca">
                    <div class="logo" aria-label="Cargue Prizma Pro"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div>
                    <div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div>
                </div>
                <nav class="nav">
                    <a class="nav-item" href="/">⌂ <span>Inicio</span></a>
                    <a class="nav-item" href="/tests">▣ <span>Test</span></a>
                    <a class="nav-item activo" href="/cargue-actual">⇧ <span>Cargue actual</span></a>
                    <a class="nav-item" href="/historial">◷ <span>Historial</span></a>
                    <a class="nav-item" href="/reportes">▥ <span>Reportes</span></a><a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a><a class="nav-item" href="/salir">⏻ <span>Salir</span></a>
                </nav>
                <div class="estado-servicio">
                    <div class="servicio-linea"><span class="punto"></span> Servicio activo</div>
                    <div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div>
                    <div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div>
                </div>
            </aside>

            <main id="cargue-progreso" class="contenido">
                <section class="panel cabecera-progreso">
                    <div class="cabecera-linea">
                        <div class="cabecera-titulo">
                            <div class="icono-subida">⇧</div>
                            <h1>Cargue en progreso</h1>
                        </div>
                        <div class="porcentaje"><strong id="porcentaje">0%</strong> completado</div>
                    </div>
                    <div class="barra"><div id="progreso" class="progreso"></div></div>
                    <div id="estado" class="estado">Iniciando...</div>
                </section>

                <section class="numeros">
                    <div class="panel numero procesadas">
                        <div class="numero-icono">↻</div>
                        <div><span>Procesadas</span><strong id="procesadas">0</strong></div>
                    </div>
                    <div class="panel numero exitosas">
                        <div class="numero-icono">✓</div>
                        <div><span>Exitosas</span><strong id="exitosas">0</strong></div>
                    </div>
                    <div class="panel numero errores">
                        <div class="numero-icono">×</div>
                        <div><span>Errores</span><strong id="errores">0</strong></div>
                    </div>
                </section>

                <section class="zona">
                    <div class="panel lista-panel">
                        <h2 class="titulo-panel">Actividades del cargue</h2>
                        <div id="lista-actividades" class="lista-actividades">
                            <div class="actividad-progreso">Preparando lista de actividades...</div>
                        </div>
                        <div class="pie">El progreso se actualiza automáticamente.</div>
                    </div>

                    <div class="panel estado-panel">
                        <h2 class="titulo-panel">Estado del proceso</h2>
                        <div class="estado-caja">
                            <span>Actividad actual</span>
                            <strong id="actividad-actual">Preparando cargue...</strong>
                        </div>
                        <div class="estado-caja">
                            <span>Total de actividades</span>
                            <strong id="total-actividades">—</strong>
                        </div>
                        <div class="leyenda">
                            <div>⏳ Pendiente</div>
                            <div>🔄 Procesando</div>
                            <div>✅ Completada</div>
                            <div>❌ Con error</div>
                        </div>
                        <form action="/cancelar/__TRABAJO_ID__" method="post" style="margin-top:18px;">
                            <button type="submit" style="width:100%;border:1px solid #fecaca;background:#fff;color:#b42318;border-radius:9px;padding:11px 14px;cursor:pointer;font-weight:800;">Cancelar proceso</button>
                        </form>
                        <div id="final"></div>
                    </div>
                </section>
            </main>
        </div>

        <script>
            const trabajoId = "__TRABAJO_ID__";

            function escaparHtml(texto) {
                return String(texto ?? "")
                    .replaceAll("&", "&amp;")
                    .replaceAll("<", "&lt;")
                    .replaceAll(">", "&gt;")
                    .replaceAll('"', "&quot;")
                    .replaceAll("'", "&#039;");
            }

            function renderizarActividades(actividades) {
                const contenedor = document.getElementById("lista-actividades");

                if (!Array.isArray(actividades) || actividades.length === 0) {
                    contenedor.innerHTML = '<div class="actividad-progreso">Preparando lista de actividades...</div>';
                    return;
                }

                let html = "";
                let actual = "Preparando cargue...";

                for (const actividad of actividades) {
                    let icono = "⏳";
                    let clase = "";

                    if (actividad.estado === "procesando") {
                        icono = "🔄";
                        clase = "actividad-procesando";
                        actual = actividad.numero + ". " + actividad.nombre;
                    } else if (actividad.estado === "ok") {
                        icono = "✅";
                        clase = "actividad-ok";
                    } else if (actividad.estado === "error") {
                        icono = "❌";
                        clase = "actividad-error-fila";
                    }

                    html += '<div class="actividad-progreso ' + clase + '">' +
                        '<div class="actividad-icono">' + icono + '</div>' +
                        '<div><div class="actividad-nombre">' +
                        actividad.numero + '. ' + escaparHtml(actividad.nombre) + '</div>';

                    if (actividad.estado === "error" && actividad.error) {
                        html += '<div class="actividad-error">' + escaparHtml(actividad.error) + '</div>';
                    }

                    html += '</div></div>';
                }

                contenedor.innerHTML = html;
                document.getElementById("actividad-actual").innerText = actual;
            }

            async function revisarEstado() {
                try {
                    const respuesta = await fetch("/estado/" + trabajoId);
                    const datos = await respuesta.json();

                    document.getElementById("estado").innerText = datos.mensaje + (datos.posicion_cola ? ' · Posición en cola: ' + datos.posicion_cola : '');
                    document.getElementById("procesadas").innerText = datos.procesadas;
                    document.getElementById("exitosas").innerText = datos.exitosas;
                    document.getElementById("errores").innerText = datos.errores;
                    document.getElementById("total-actividades").innerText = datos.total || "—";

                    renderizarActividades(datos.detalle_actividades);

                    let porcentaje = 0;
                    if (datos.total > 0) {
                        porcentaje = (datos.procesadas / datos.total) * 100;
                    }
                    porcentaje = Math.min(100, porcentaje);

                    document.getElementById("progreso").style.width = porcentaje + "%";
                    document.getElementById("porcentaje").innerText = Math.round(porcentaje) + "%";

                    if (datos.terminado) {
                        document.getElementById("actividad-actual").innerText = "Proceso finalizado";

                        let html = '<div class="final"><h3>Proceso terminado</h3><p>' +
                            escaparHtml(datos.mensaje) + '</p>';

                        if (datos.reporte_disponible) {
                            html += '<a class="descarga" href="/reporte/' + trabajoId + '">Descargar reporte CSV</a>';
                        }

                        html += '</div>';
                        document.getElementById("final").innerHTML = html;
                        return;
                    }

                    setTimeout(revisarEstado, 1500);
                } catch (error) {
                    document.getElementById("estado").innerText = "Error consultando estado.";
                    setTimeout(revisarEstado, 3000);
                }
            }

            revisarEstado();
        </script>
    </body>
    </html>
    """

    pagina_progreso = html_progreso.replace(
        "__TRABAJO_ID__",
        trabajo_id,
    )
    trabajo["pagina_progreso"] = pagina_progreso

    return HTMLResponse(pagina_progreso)


def _pagina_sin_cargue_actual():
    return HTMLResponse(r'''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Cargue actual - Cargue Prizma Pro</title>
<style>
:root{--fondo:#f7f8fc;--texto:#101828;--muted:#667085;--borde:#e5e7ef;--morado:#5548e8;--sombra:0 12px 34px rgba(29,41,57,.06)}*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--fondo);color:var(--texto)}.app{min-height:100vh;display:grid;grid-template-columns:235px 1fr}.sidebar{height:100vh;background:#fff;border-right:1px solid var(--borde);padding:28px 20px;display:flex;flex-direction:column}.marca{display:flex;align-items:center;gap:12px;margin-bottom:34px}.logo{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,#6d5dfc,#4338ca);box-shadow:0 8px 20px rgba(79,70,229,.25)}.logo svg{width:29px;height:29px}.logo svg path:first-child{fill:#fff}.logo svg path:last-child{fill:#c7d2fe}.marca strong{display:block;font-size:18px}.marca span{display:block;color:var(--muted);font-size:12px;margin-top:3px}.nav{display:grid;gap:8px}.nav-item{padding:12px 14px;border-radius:11px;color:#475467;font-size:14px;display:flex;gap:11px;align-items:center;text-decoration:none}.nav-item:hover{background:#f7f5ff;color:#4f46e5}.nav-item.activo{background:#f1efff;color:#4f46e5;font-weight:700}.estado-servicio{margin-top:auto;border:1px solid var(--borde);border-radius:14px;padding:15px}.servicio-linea{font-size:12px;font-weight:800;color:#07894f;margin-bottom:14px}.punto{width:8px;height:8px;background:#12b76a;border-radius:50%;display:inline-block;margin-right:7px}.servicio-mini{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}.chip{background:#eef2ff;color:#4f46e5;border-radius:999px;padding:4px 8px}.contenido{padding:30px 34px;display:grid;place-items:center}.vacio{width:min(680px,100%);background:#fff;border:1px solid var(--borde);border-radius:18px;box-shadow:var(--sombra);padding:54px 34px;text-align:center}.icono{width:68px;height:68px;border-radius:20px;background:#f1efff;color:#5548e8;display:grid;place-items:center;margin:0 auto 20px;font-size:28px;font-weight:800}.vacio h1{margin:0 0 10px;font-size:27px}.vacio p{margin:0 auto 24px;color:var(--muted);font-size:14px;line-height:1.6;max-width:480px}.boton{display:inline-flex;padding:12px 18px;border-radius:10px;background:linear-gradient(90deg,#5548e8,#6546e8);color:#fff;text-decoration:none;font-size:13px;font-weight:800}@media(max-width:900px){.app{grid-template-columns:1fr}.sidebar{display:none}.contenido{padding:18px}}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head><body><div class="app"><aside class="sidebar"><div class="marca"><div class="logo"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div><div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div></div><nav class="nav"><a class="nav-item" href="/">⌂ <span>Inicio</span></a><a class="nav-item activo" href="/cargue-actual">⇧ <span>Cargue actual</span></a><a class="nav-item" href="/historial">◷ <span>Historial</span></a><a class="nav-item" href="/reportes">▥ <span>Reportes</span></a><a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a><a class="nav-item" href="/salir">⏻ <span>Salir</span></a></nav><div class="estado-servicio"><div class="servicio-linea"><span class="punto"></span> Servicio activo</div><div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div><div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div></div></aside><main class="contenido"><section class="vacio"><div class="icono">⇧</div><h1>No hay cargues activos</h1><p>Cuando alguien inicie un proceso desde Inicio, aparecerá aquí para que el equipo pueda consultar su progreso.</p><a class="boton" href="/">Iniciar un nuevo cargue</a></section></main></div></body></html>''')


def _formatear_inicio_cargue(fecha_iso):
    if not fecha_iso:
        return "Iniciando..."
    try:
        fecha = datetime.fromisoformat(fecha_iso)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=ZONA_HORARIA_COLOMBIA)
        else:
            fecha = fecha.astimezone(ZONA_HORARIA_COLOMBIA)
        return fecha.strftime("%d/%m/%Y · %I:%M %p").replace("AM", "a. m.").replace("PM", "p. m.")
    except Exception:
        return "En progreso"


def _render_tarjeta_cargue(trabajo, usuario_actual):
    cursos = trabajo.get("cursos") or []
    if cursos:
        curso = cursos[0].get("curso") or "Curso sin nombre"
        programa = cursos[0].get("programa") or "Programa sin nombre"
        if len(cursos) > 1:
            curso = f"{curso} y {len(cursos) - 1} curso(s) más"
    else:
        curso, programa = "Curso en proceso", "Programa sin nombre"

    total = int(trabajo.get("total") or 0)
    procesadas = int(trabajo.get("procesadas") or 0)
    exitosas = int(trabajo.get("exitosas") or 0)
    errores = int(trabajo.get("errores") or 0)
    porcentaje = max(
        0,
        min(100, round((procesadas / total) * 100) if total > 0 else 0),
    )
    trabajo_id_raw = str(trabajo.get("id") or "")
    trabajo_id = html.escape(trabajo_id_raw)
    en_cola = trabajo.get("etapa") == "en_cola"
    posicion = _posicion_en_cola(trabajo_id_raw) if en_cola else None
    estado_texto = f"En cola · #{posicion}" if posicion else "En progreso"
    inicio_label = "En cola desde" if en_cola else "Iniciado"
    fecha_mostrar = trabajo.get("encolado_en") if en_cola else trabajo.get("iniciado_en")
    propietario = str(trabajo.get("usuario_app") or "")
    propietario_visible = _nombre_visible(propietario) or propietario or "Usuario"
    es_propietario = _es_de(trabajo, usuario_actual)

    if es_propietario:
        acciones = (
            f'<a href="/proceso/{trabajo_id}">Entrar al proceso <b>&rsaquo;</b></a>'
            f'<form action="/cancelar/{trabajo_id}" method="post" style="margin-top:8px">'
            '<button type="submit" style="border:1px solid #fecaca;background:#fff;color:#b42318;'
            'border-radius:8px;padding:8px 10px;cursor:pointer;font-weight:700">Cancelar</button></form>'
        )
    else:
        acciones = (
            '<span class="solo-lectura" style="display:block;border:1px solid #e5e7ef;'
            'background:#f9fafb;color:#667085;border-radius:10px;padding:11px 12px;'
            'font-size:11px;font-weight:700;">Cargue de otro usuario</span>'
        )

    return (
        f'<article class="carga-card">'
        f'<div class="curso-bloque"><div class="curso-icono">▣</div><div class="curso-texto">'
        f'<h2>{html.escape(curso)}</h2><p>Programa: {html.escape(programa)}</p>'
        f'<p style="margin-top:-4px;">Iniciado por: <strong>{html.escape(propietario_visible)}</strong></p>'
        f'<span class="estado-chip"><span></span> {html.escape(estado_texto)}</span></div></div>'
        f'<div class="inicio-bloque"><small>◷ {inicio_label}</small>'
        f'<strong>{html.escape(_formatear_inicio_cargue(fecha_mostrar))}</strong></div>'
        f'<div class="avance-bloque"><div class="avance-cab"><span>Progreso general</span>'
        f'<strong>{porcentaje}%</strong></div><div class="barra"><div class="barra-interna" '
        f'style="width:{porcentaje}%"></div></div><div class="metricas">'
        f'<div><i class="verde"></i><small>Procesadas</small><strong>{procesadas}</strong></div>'
        f'<div><i class="verde"></i><small>Exitosas</small><strong>{exitosas}</strong></div>'
        f'<div><i class="rojo"></i><small>Errores</small><strong>{errores}</strong></div></div></div>'
        f'<div class="accion-bloque">{acciones}</div></article>'
    )


def _pagina_cargues_activos(trabajos, usuario_actual=None):
    if usuario_actual is None:
        usuario_actual = _usuario_actual()
    tarjetas = [
        _render_tarjeta_cargue(trabajo, usuario_actual)
        for trabajo in trabajos
    ]
    cuerpo = "".join(tarjetas)
    cantidad = len(trabajos)
    plural = "s" if cantidad != 1 else ""
    return HTMLResponse(f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Cargue actual - Cargue Prizma Pro</title><style>
:root{{--fondo:#f7f8fc;--texto:#101828;--muted:#667085;--borde:#e5e7ef;--morado:#5548e8;--sombra:0 10px 30px rgba(29,41,57,.05)}}*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--fondo);color:var(--texto)}}.app{{min-height:100vh;display:grid;grid-template-columns:235px 1fr}}.sidebar{{position:sticky;top:0;height:100vh;background:#fff;border-right:1px solid var(--borde);padding:28px 20px;display:flex;flex-direction:column}}.marca{{display:flex;align-items:center;gap:12px;margin-bottom:34px}}.logo{{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,#6d5dfc,#4338ca);box-shadow:0 8px 20px rgba(79,70,229,.25)}}.logo svg{{width:29px;height:29px}}.logo svg path:first-child{{fill:#fff}}.logo svg path:last-child{{fill:#c7d2fe}}.marca strong{{display:block;font-size:18px}}.marca span{{display:block;color:var(--muted);font-size:12px;margin-top:3px}}.nav{{display:grid;gap:8px}}.nav-item{{padding:12px 14px;border-radius:11px;color:#475467;font-size:14px;display:flex;gap:11px;align-items:center;text-decoration:none}}.nav-item:hover{{background:#f7f5ff;color:#4f46e5}}.nav-item.activo{{background:#f1efff;color:#4f46e5;font-weight:700}}.estado-servicio{{margin-top:auto;border:1px solid var(--borde);border-radius:14px;padding:15px}}.servicio-linea{{font-size:12px;font-weight:800;color:#07894f;margin-bottom:14px}}.punto{{width:8px;height:8px;background:#12b76a;border-radius:50%;display:inline-block;margin-right:7px}}.servicio-mini{{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}}.chip{{background:#eef2ff;color:#4f46e5;border-radius:999px;padding:4px 8px}}.contenido{{padding:34px 36px 44px;min-width:0}}.cabecera-top{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:24px}}.cabecera h1{{font-size:29px;margin:0 0 7px}}.cabecera p{{margin:0;color:var(--muted);font-size:14px;line-height:1.5}}.contador{{background:#f1efff;color:#5548e8;border-radius:999px;padding:8px 12px;font-size:12px;font-weight:800;white-space:nowrap}}.lista{{display:grid;gap:16px}}.carga-card{{background:#fff;border:1px solid var(--borde);border-radius:17px;box-shadow:var(--sombra);padding:22px;display:grid;grid-template-columns:minmax(245px,1.15fr) 170px minmax(320px,1.25fr) 185px;gap:22px;align-items:center}}.curso-bloque{{display:flex;gap:14px;align-items:center;min-width:0}}.curso-icono{{width:58px;height:58px;border-radius:15px;background:#f1efff;color:#5548e8;display:grid;place-items:center;font-size:24px;flex:0 0 58px}}.curso-texto{{min-width:0}}.curso-texto h2{{font-size:16px;margin:0 0 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.curso-texto p{{font-size:12px;color:var(--muted);margin:0 0 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.estado-chip{{display:inline-flex;align-items:center;gap:6px;background:#eef6ff;color:#1473e6;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:800}}.estado-chip span{{width:6px;height:6px;background:#2e90fa;border-radius:50%}}.inicio-bloque small{{display:block;color:var(--muted);font-size:11px;margin-bottom:7px}}.inicio-bloque strong{{font-size:12px;color:#475467}}.avance-cab{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;color:var(--muted);font-size:11px}}.avance-cab strong{{font-size:21px;color:#5548e8}}.barra{{height:10px;border-radius:999px;background:#eeecff;overflow:hidden}}.barra-interna{{height:100%;background:linear-gradient(90deg,#6759f5,#4f46e5);border-radius:999px}}.metricas{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}}.metricas div{{display:grid;grid-template-columns:8px 1fr;column-gap:5px;align-items:center}}.metricas i{{width:7px;height:7px;border-radius:50%}}.metricas i.verde{{background:#12b76a}}.metricas i.rojo{{background:#ef4444}}.metricas small{{font-size:10px;color:var(--muted)}}.metricas strong{{grid-column:2;font-size:14px;margin-top:2px}}.accion-bloque{{border-left:1px solid var(--borde);padding-left:20px;text-align:center}}.accion-bloque a{{display:flex;justify-content:center;align-items:center;gap:8px;background:linear-gradient(90deg,#5548e8,#6546e8);color:#fff;text-decoration:none;font-size:12px;font-weight:800;border-radius:10px;padding:12px 13px}}.accion-bloque b{{font-size:18px}}.accion-bloque small{{display:block;color:var(--muted);font-size:10px;margin-top:8px}}.nota{{margin-top:18px;border:1px solid #ddd8ff;background:#faf9ff;border-radius:14px;padding:14px 17px;color:#475467;font-size:12px}}@media(max-width:1200px){{.carga-card{{grid-template-columns:1fr 1fr}}.accion-bloque{{border-left:0;padding-left:0}}}}@media(max-width:900px){{.app{{grid-template-columns:1fr}}.sidebar{{display:none}}.contenido{{padding:20px}}.carga-card{{grid-template-columns:1fr}}}}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head><body><div class="app"><aside class="sidebar"><div class="marca"><div class="logo"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div><div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div></div><nav class="nav"><a class="nav-item" href="/">⌂ <span>Inicio</span></a><a class="nav-item activo" href="/cargue-actual">⇧ <span>Cargue actual</span></a><a class="nav-item" href="/historial">◷ <span>Historial</span></a><a class="nav-item" href="/reportes">▥ <span>Reportes</span></a><a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a><a class="nav-item" href="/salir">⏻ <span>Salir</span></a></nav><div class="estado-servicio"><div class="servicio-linea"><span class="punto"></span> Servicio activo</div><div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div><div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div></div></aside><main class="contenido"><section class="cabecera"><div class="cabecera-top"><div><h1>Cargue actual</h1><p>Aquí puedes ver todos los cursos que están siendo procesados actualmente.<br>Entra a un proceso para revisar el detalle de sus actividades.</p></div><div class="contador">{cantidad} proceso{plural} activo{plural}</div></div></section><section class="lista">{cuerpo}</section><div class="nota"><strong>Vista global del equipo.</strong> Cada tarjeta representa un cargue activo. Para ver la lista detallada de actividades, entra al proceso correspondiente.</div></main></div><script>setTimeout(function(){{window.location.reload();}},3000);</script></body></html>''')


@app.get("/cargue-actual", response_class=HTMLResponse)
def cargue_actual():
    usuario = _usuario_actual()

    activos = [
        trabajo for trabajo in TRABAJOS.values()
        if not trabajo.get("terminado")
        and trabajo.get("etapa") in {"en_cola", "iniciando", "login", "preparando", "procesando", "validando_login", "cargando_test"}
    ]
    activos.sort(key=lambda item: item.get("encolado_en") or item.get("iniciado_en") or item.get("creado_en", ""))
    if not activos:
        return _pagina_sin_cargue_actual()
    return _pagina_cargues_activos(activos, usuario)


@app.post("/cancelar/{trabajo_id}", response_class=HTMLResponse)
def cancelar_trabajo(trabajo_id: str):
    with COLA_CONDICION:
        trabajo = TRABAJOS.get(trabajo_id)
        if not trabajo or not _es_de(trabajo, _usuario_actual()):
            return HTMLResponse("<h2>Proceso no encontrado.</h2>", status_code=404)

        if trabajo.get("terminado"):
            return HTMLResponse(
                "<script>window.location='/cargue-actual';</script>"
            )

        trabajo["cancelar_solicitado"] = True

        if trabajo.get("etapa") == "en_cola":
            try:
                COLA_CARGUES.remove(trabajo_id)
            except ValueError:
                pass
            trabajo.pop("usuario_prizma_temporal", None)
            trabajo.pop("contrasena_prizma_temporal", None)
            trabajo["etapa"] = "cancelado"
            trabajo["mensaje"] = "Proceso cancelado antes de iniciar."
            trabajo["terminado"] = True
            trabajo["finalizado_en"] = _ahora_colombia_iso()
        else:
            trabajo["mensaje"] = (
                "Cancelación solicitada. El proceso se detendrá de forma segura "
                "al terminar la actividad actual."
            )

        COLA_CONDICION.notify_all()

    return HTMLResponse("<script>window.location='/cargue-actual';</script>")


@app.get("/proceso/{trabajo_id}", response_class=HTMLResponse)
def ver_proceso(trabajo_id: str):
    trabajo = TRABAJOS.get(trabajo_id)
    if not trabajo or not _es_de(trabajo, _usuario_actual()):
        return HTMLResponse("<h2>Proceso no encontrado.</h2><p><a href='/cargue-actual'>Volver a Cargue actual</a></p>", status_code=404)
    pagina = trabajo.get("pagina_progreso")
    if pagina:
        return HTMLResponse(pagina)
    return HTMLResponse("<h2>El proceso todavía se está preparando.</h2><p><a href='/cargue-actual'>Volver a Cargue actual</a></p>", status_code=202)


# ============================================================
# ESTADO
# ============================================================

@app.get(
    "/estado/{trabajo_id}",
)
def estado_trabajo(
    trabajo_id: str,
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

    return {
        "etapa":
            trabajo["etapa"],

        "mensaje":
            trabajo["mensaje"],

        "total":
            trabajo["total"],

        "procesadas":
            trabajo["procesadas"],

        "exitosas":
            trabajo["exitosas"],

        "errores":
            trabajo["errores"],

        "terminado":
            trabajo["terminado"],

        "detalle_actividades":
            trabajo.get(
                "detalle_actividades",
                [],
            ),

        "reporte_disponible":
            os.path.isfile(
                trabajo["ruta_reporte"]
            ),
        "posicion_cola": _posicion_en_cola(trabajo_id),
        "cancelar_solicitado": bool(trabajo.get("cancelar_solicitado")),
    }
