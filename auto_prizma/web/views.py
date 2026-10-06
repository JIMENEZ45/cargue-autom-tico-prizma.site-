"""HTML de la pagina principal de analisis y cargue (generar_html).
"""

import html

from auto_prizma.services.auth import (
    _nombre_visible,
    _usuario_actual,
)
from auto_prizma.integrations.google.oauth import _google_conectado
from auto_prizma.services.drive_zip_validation import _bytes_legibles
from auto_prizma.services.upload_jobs import _codificar_clave_actividad


# ============================================================
# HTML PRINCIPAL
# ============================================================

def generar_html(
    resultado=None,
    error=None,
    trabajo_id=None,
    seleccion_actual=None,
):

    def e(valor):
        return html.escape(
            str(valor or "")
        )

    contenido = ""

    # ========================================================
    # PANTALLA INICIAL
    # ========================================================

    if resultado is None:

        bloque_error = ""

        if error:
            bloque_error = f"""
            <div class="alerta-error">
                <div class="alerta-icono">!</div>
                <div>
                    <strong>No se pudo continuar</strong>
                    <p>{e(error)}</p>
                </div>
            </div>
            """

        google_conectado = _google_conectado()

        if google_conectado:
            bloque_google = """
            <section class="google-conexion google-ok">
                <div class="google-icono">G</div>
                <div class="google-texto">
                    <strong>Google conectado</strong>
                    <span>Esta sesión usa tu propia cuenta de Google, con permiso de solo lectura para Sheets y Drive.</span>
                </div>
                <form action="/google/desconectar" method="post">
                    <button class="google-boton secundario" type="submit">Desconectar</button>
                </form>
            </section>
            """
        else:
            bloque_google = """
            <section class="google-conexion">
                <div class="google-icono">G</div>
                <div class="google-texto">
                    <strong>Conecta tu cuenta de Google</strong>
                    <span>Cada persona conecta la suya. Necesario para leer matrices y carpetas privadas.</span>
                </div>
                <a class="google-boton" href="/google/conectar">Conectar con Google</a>
            </section>
            """

        contenido = f"""
        <section class="encabezado-pagina">
            <div>
                <h1>¡Hola, {e(_nombre_visible(_usuario_actual()))}!</h1>
                <p>Automatiza el cargue de actividades en PRIZMA de forma rápida y segura.</p>
            </div>
        </section>

        {bloque_error}

        <div id="google-conexion-panel">{bloque_google}</div>

        <form
            id="cargue-principal"
            action="/analizar"
            method="post"
            enctype="multipart/form-data"
            class="panel panel-principal"
        >
            <div class="selector-modo-matriz" style="display:flex;gap:10px;margin-bottom:22px;flex-wrap:wrap;">
                <label style="flex:1;min-width:180px;border-radius:12px;padding:12px 14px;cursor:pointer;">
                    <input type="radio" name="modo_matriz" value="link" checked>
                    <strong style="margin-left:7px;">🔗 Por link</strong>
                    <span style="display:block;margin:5px 0 0 25px;color:#667085;font-size:12px;">Google Sheets + ZIP</span>
                </label>
                <label style="flex:1;min-width:180px;border-radius:12px;padding:12px 14px;cursor:pointer;">
                    <input type="radio" name="modo_matriz" value="archivo">
                    <strong style="margin-left:7px;">📄 Por archivo</strong>
                    <span style="display:block;margin:5px 0 0 25px;color:#667085;font-size:12px;">XLSX/CSV + ZIP</span>
                </label>
            </div>

            <div class="titulo-seccion">
                <span class="numero-seccion">1</span>
                <div>
                    <h2>Matriz y recursos</h2>
                    <p>Elige si usarás un enlace de Google Sheets o un archivo XLSX/CSV, y selecciona el ZIP.</p>
                </div>
            </div>

            <div class="grid-archivos">
                <div class="tarjeta-archivo" id="bloque-matriz-link">
                    <div class="archivo-cabecera">
                        <div class="archivo-icono verde" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M9 11l6 6M15 11l-6 6"/></svg>
                        </div>
                        <div>
                            <strong>Google Sheets de la matriz</strong>
                            <span>Pega el enlace de la pestaña que vas a cargar. Solo se procesa esa pestaña.</span>
                        </div>
                    </div>
                    <div class="selector-archivo">
                        <input
                            id="google-sheet-url"
                            type="url"
                            name="google_sheet_url"
                            placeholder="https://docs.google.com/spreadsheets/d/..."
                            autocomplete="off"
                            style="display:block;width:100%;border:0;outline:0;background:transparent;color:#101828;font:inherit;font-size:12px;"
                        >
                    </div>
                </div>

                <label class="tarjeta-archivo zona-drop" id="bloque-matriz-archivo" for="archivo-matriz" data-input="archivo-matriz" style="display:none;">
                    <div class="archivo-cabecera">
                        <div class="archivo-icono verde" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M8 12h8M8 16h8"/></svg>
                        </div>
                        <div>
                            <strong>Archivo de matriz</strong>
                            <span>Selecciona un XLSX o CSV descargado.</span>
                        </div>
                    </div>
                    <div class="selector-archivo">
                        <span class="boton-selector">Seleccionar archivo</span>
                        <span id="nombre-matriz" class="nombre-archivo">Ningún archivo seleccionado</span>
                    </div>
                    <input
                        id="archivo-matriz"
                        type="file"
                        name="matriz_archivo"
                        accept=".xlsx,.csv"
                        disabled
                    >
                </label>

                <label class="tarjeta-archivo zona-drop" for="archivo-zip" data-input="archivo-zip">
                    <div class="archivo-cabecera">
                        <div class="archivo-icono morado" aria-hidden="true">
                            <svg viewBox="0 0 24 24"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M11 5h2M11 8h2M11 11h2M11 14h2"/></svg>
                        </div>
                        <div>
                            <strong>ZIP de recursos</strong>
                            <span>Archivos H5P y PDF · también puedes arrastrarlo aquí</span>
                        </div>
                    </div>
                    <div class="selector-archivo">
                        <span class="boton-selector">Seleccionar archivo</span>
                        <span id="nombre-zip" class="nombre-archivo">Ningún archivo seleccionado</span>
                    </div>
                    <input
                        id="archivo-zip"
                        type="file"
                        name="recursos"
                        accept=".zip"
                        required
                    >
                </label>
            </div>

            <div class="separador"></div>

            <div class="titulo-seccion">
                <span class="numero-seccion">2</span>
                <div>
                    <h2>Tipos de actividades</h2>
                    <p>Selecciona qué actividades deseas procesar.</p>
                </div>
            </div>

            <div class="grid-tipos">
                <label class="tarjeta-tipo tipo-verde">
                    <input type="checkbox" name="ovi" value="1" checked>
                    <span class="check-personalizado">✓</span>
                    <span class="tipo-icono icono-ovi" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></svg>
                    </span>
                    <strong>OVI</strong>
                    <small>Objetos Virtuales de Información</small>
                </label>

                <label class="tarjeta-tipo tipo-azul">
                    <input type="checkbox" name="ova" value="1" checked>
                    <span class="check-personalizado">✓</span>
                    <span class="tipo-icono icono-ova" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/><path d="m9 9 2 2 4-4"/></svg>
                    </span>
                    <strong>OVA</strong>
                    <small>Objetos Virtuales de Aprendizaje</small>
                </label>

                <label class="tarjeta-tipo tipo-morado">
                    <input type="checkbox" name="retos" value="1" checked>
                    <span class="check-personalizado">✓</span>
                    <span class="tipo-icono icono-reto" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M8 3h8v4a4 4 0 0 1-8 0z"/><path d="M8 5H4v2a4 4 0 0 0 4 4M16 5h4v2a4 4 0 0 1-4 4"/><path d="M12 11v5M8 21h8M10 16h4v5h-4z"/></svg>
                    </span>
                    <strong>Retos Evaluativos</strong>
                    <small>Retos evaluativos en PDF</small>
                </label>

                <label class="tarjeta-tipo tipo-naranja">
                    <input type="checkbox" name="test_evaluativo" value="1" id="chk-test">
                    <span class="check-personalizado">✓</span>
                    <span class="tipo-icono icono-test" aria-hidden="true">
                        <svg viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="m9 14 2 2 4-4"/></svg>
                    </span>
                    <strong>Test Evaluativo</strong>
                    <small>Exámenes desde Word / Google Docs</small>
                </label>
            </div>

            <div id="bloque-test" style="display:none;margin-top:10px;">
                <div class="separador"></div>
                <div class="titulo-seccion">
                    <span class="numero-seccion" style="background:#fef3c7;color:#d97706;">3</span>
                    <div>
                        <h2>Documento de Test y Datos Académicos</h2>
                        <p>Sube el archivo Word o pega el enlace de Google Docs, e indica los datos académicos del curso.</p>
                    </div>
                </div>

                <div class="selector-modo-matriz" style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;">
                    <label style="flex:1;min-width:180px;border-radius:12px;padding:12px 14px;cursor:pointer;">
                        <input type="radio" name="modo_test" value="archivo" checked>
                        <strong style="margin-left:7px;">📄 Por archivo Word</strong>
                        <span style="display:block;margin:5px 0 0 25px;color:#667085;font-size:12px;">Documento .docx</span>
                    </label>
                    <label style="flex:1;min-width:180px;border-radius:12px;padding:12px 14px;cursor:pointer;">
                        <input type="radio" name="modo_test" value="link">
                        <strong style="margin-left:7px;">🔗 Por link Google Docs</strong>
                        <span style="display:block;margin:5px 0 0 25px;color:#667085;font-size:12px;">Enlace del examen</span>
                    </label>
                </div>

                <div class="grid-archivos" style="grid-template-columns:1fr;margin-bottom:18px;">
                    <label class="tarjeta-archivo zona-drop" id="bloque-test-archivo" for="archivo-test-docx" data-input="archivo-test-docx">
                        <div class="archivo-cabecera">
                            <div class="archivo-icono naranja" aria-hidden="true">
                                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                            </div>
                            <div>
                                <strong>Documento de evaluación (.docx)</strong>
                                <span>Arrastra o selecciona el archivo Word con las preguntas</span>
                            </div>
                        </div>
                        <div class="selector-archivo">
                            <span class="boton-selector" style="background:#d97706;">Seleccionar archivo</span>
                            <span id="nombre-test-docx" class="nombre-archivo">Ningún archivo seleccionado</span>
                        </div>
                        <input id="archivo-test-docx" type="file" name="test_archivo_docx" accept=".docx" disabled>
                    </label>

                    <div class="tarjeta-archivo" id="bloque-test-link" style="display:none;">
                        <div class="archivo-cabecera">
                            <div class="archivo-icono naranja" aria-hidden="true">
                                <svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                            </div>
                            <div>
                                <strong>Google Docs del examen</strong>
                                <span>Pega el enlace del documento de Google con las preguntas</span>
                            </div>
                        </div>
                        <div class="selector-archivo">
                            <input id="test-google-doc-url" type="url" name="test_google_doc_url" placeholder="https://docs.google.com/document/d/..." autocomplete="off" disabled style="display:block;width:100%;border:0;outline:0;background:transparent;color:#101828;font:inherit;font-size:12px;">
                        </div>
                    </div>
                </div>

                <div class="caja-datos-academicos" style="border-radius:12px;padding:16px;margin-bottom:18px;">
                    <div style="margin-bottom:14px;">
                        <label for="test-datos-academicos" style="font-weight:700;font-size:14px;color:#344054;margin-bottom:6px;display:block;">
                            Datos académicos (Código Programa · Código Pensum · Código Asignatura · Nombre Asignatura)
                        </label>
                        <input id="test-datos-academicos" name="test_datos_academicos" type="text"
                               placeholder="Ej: ADM101 PEN2024 MAC001 Macroeconomía Aplicada"
                               autocomplete="off" disabled
                               style="width:100%;box-sizing:border-box;padding:12px 14px;border:1px solid #d5d1fc;border-radius:10px;font-size:13px;color:#101828;background:#fff;">
                        <small style="color:#667085;margin-top:5px;display:block;font-size:12px;">
                            Ingresa los 3 códigos seguidos del nombre de la asignatura, separados por espacio o guión.
                        </small>
                    </div>

                    <div>
                        <label for="test-semestre" style="font-weight:700;font-size:14px;color:#344054;margin-bottom:6px;display:block;">
                            Semestre / Nivel de pensum
                        </label>
                        <select id="test-semestre" name="test_semestre" disabled
                                style="width:100%;max-width:260px;box-sizing:border-box;padding:11px 14px;border:1px solid #d5d1fc;border-radius:10px;font-size:13px;color:#101828;background:#fff;cursor:pointer;">
                            <option value="">Selecciona el semestre...</option>
                            <option value="1">Semestre 1</option>
                            <option value="2">Semestre 2</option>
                            <option value="3">Semestre 3</option>
                            <option value="4">Semestre 4</option>
                            <option value="5">Semestre 5</option>
                            <option value="6">Semestre 6</option>
                            <option value="7">Semestre 7</option>
                            <option value="8">Semestre 8</option>
                            <option value="9">Semestre 9</option>
                            <option value="10">Semestre 10</option>
                        </select>
                    </div>
                </div>
            </div>

            <button class="boton-principal" type="submit">
                <span>↗</span>
                Analizar matriz y recursos
            </button>

            <p class="nota-seguridad">
                Tus archivos se utilizan únicamente durante el proceso de cargue.
            </p>
        </form>

        <aside id="ayuda" class="panel panel-ayuda">
            <h3>¿Cómo funciona?</h3>
            <div class="paso"><b>1</b><span>Elige Por link o Por archivo para suministrar la matriz.</span></div>
            <div class="paso"><b>2</b><span>Sube el ZIP con los recursos correspondientes.</span></div>
            <div class="paso"><b>3</b><span>Selecciona los tipos de actividades.</span></div>
            <div class="paso"><b>4</b><span>Analiza, revisa y luego inicia el cargue.</span></div>

            <div class="ayuda-separador"></div>

            <h3 class="titulo-consejos">Consejos</h3>
            <p class="consejo">✓ En modo link, la matriz debe conservar los enlaces de Google Drive. En modo archivo no necesitas Google.</p>
            <p class="consejo">✓ El ZIP debe contener los H5P y PDF correspondientes.</p>
            <p class="consejo">✓ Revisa el análisis antes de iniciar el cargue.</p>
        </aside>
        """

    # ========================================================
    # PANTALLA DE REVISIÓN
    # ========================================================

    else:

        total_actividades = 0
        total_ovi = 0
        total_ova = 0
        total_retos = 0
        total_h5p = 0
        total_pdf = 0
        filas_html = ""
        tipos_recurso_conteo = {}
        tipos_recurso_seleccionados = {}

        seleccion_actual_claves = None
        if seleccion_actual is not None:
            seleccion_actual_claves = set()
            for item in seleccion_actual or []:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                try:
                    seleccion_actual_claves.add((str(item[0] or ""), int(item[1])))
                except (TypeError, ValueError):
                    continue

        origen_matriz = str(resultado.get("origen_matriz") or "link").strip().lower()
        nombre_matriz = str(resultado.get("nombre_matriz") or "").strip()
        es_modo_archivo = origen_matriz == "archivo"

        drive_info = resultado.get("drive") or {}
        drive_validados = int(drive_info.get("validadas_drive") or 0)
        drive_coincidencias_zip = int(drive_info.get("coincidencias_zip") or 0)
        advertencias_drive = list(drive_info.get("advertencias") or [])
        recursos_drive = {
            (str(item.get("hoja") or ""), int(item.get("fila") or 0)): item
            for item in drive_info.get("recursos", [])
        }

        for hoja in resultado["hojas"]:

            total_actividades += len(
                hoja["actividades"]
            )
            total_ovi += hoja.get("ovi", 0)
            total_ova += hoja.get("ova", 0)
            total_retos += hoja.get("retos", 0)
            total_h5p += hoja.get("h5p", 0)
            total_pdf += hoja.get("pdf", 0)

            for actividad in hoja["actividades"]:

                tipo_recurso = str(
                    actividad.get("tipo_recurso")
                    or actividad.get("tipo")
                    or "Sin tipo"
                ).strip()
                tipos_recurso_conteo[tipo_recurso] = (
                    tipos_recurso_conteo.get(tipo_recurso, 0) + 1
                )

                clave_tuple = (
                    str(hoja.get("hoja") or ""),
                    int(actividad.get("fila") or 0),
                )
                seleccionada = (
                    seleccion_actual_claves is None
                    or clave_tuple in seleccion_actual_claves
                )
                if seleccionada:
                    tipos_recurso_seleccionados[tipo_recurso] = (
                        tipos_recurso_seleccionados.get(tipo_recurso, 0) + 1
                    )

                clave_actividad = _codificar_clave_actividad(*clave_tuple)

                categoria = actividad["categoria"]
                clase_categoria = {
                    "OVI": "badge-verde",
                    "OVA": "badge-azul",
                    "CHALLENGE": "badge-morado",
                }.get(categoria, "badge-gris")

                etiqueta_categoria = (
                    "RETO"
                    if categoria == "CHALLENGE"
                    else categoria
                )

                clase_tipo = (
                    "badge-pdf"
                    if actividad["tipo"] == "PDF"
                    else "badge-h5p"
                )

                recurso_drive = recursos_drive.get(
                    (str(hoja.get("hoja") or ""), int(actividad.get("fila") or 0)),
                    {},
                )

                if es_modo_archivo:
                    archivo_drive = "Se resolverá desde el ZIP"
                    tamano_drive_txt = ""
                    coincide_zip = False
                    estado_zip = "Validación segura al cargar"
                else:
                    archivo_drive = str(
                        recurso_drive.get("archivo")
                        or "NO HAY ARCHIVO EN LA CARPETA"
                    )
                    tamano_drive = recurso_drive.get("tamano_drive")
                    tamano_drive_txt = (
                        _bytes_legibles(tamano_drive)
                        if tamano_drive is not None
                        else ""
                    )
                    coincide_zip = bool(recurso_drive.get("coincide_zip"))
                    estado_zip = "ZIP COINCIDE" if coincide_zip else "REVISAR ZIP"

                filas_html += f"""
                <tr>
                    <td class="celda-seleccion">
                        <input
                            type="checkbox"
                            class="actividad-seleccion"
                            name="actividades_seleccionadas"
                            value="{e(clave_actividad)}"
                            data-tipo-recurso="{e(tipo_recurso)}"
                            form="form-iniciar-cargue"
                            {"checked" if seleccionada else ""}
                            aria-label="Seleccionar {e(actividad["nombre"])}"
                        >
                    </td>
                    <td>{e(actividad["semana"])}</td>
                    <td>{e(actividad["unidad"])}</td>
                    <td class="celda-actividad">{e(actividad["nombre"])}</td>
                    <td><span class="badge {clase_categoria}">{e(etiqueta_categoria)}</span></td>
                    <td><span class="badge badge-recurso">{e(tipo_recurso)}</span></td>
                    <td><span class="badge {clase_tipo}">{e(actividad["tipo"])}</span></td>
                    <td class="celda-actividad" title="{e(archivo_drive)}">
                        <strong>{e(archivo_drive)}</strong>
                        {('<div style="margin-top:4px;color:#667085;font-size:11px;">' + e(tamano_drive_txt) + '</div>') if tamano_drive_txt else ''}
                    </td>
                    <td><span class="badge {'badge-verde' if coincide_zip else 'badge-gris'}">{e(estado_zip)}</span></td>
                </tr>
                """

        total_seleccionadas = sum(tipos_recurso_seleccionados.values())
        filtros_tipo_html = ""
        for tipo_recurso, cantidad in tipos_recurso_conteo.items():
            seleccionadas_tipo = tipos_recurso_seleccionados.get(tipo_recurso, 0)
            marcado = seleccionadas_tipo == cantidad and cantidad > 0
            filtros_tipo_html += f"""
            <label class="filtro-recurso-item">
                <input
                    type="checkbox"
                    class="filtro-tipo-recurso"
                    data-tipo-recurso="{e(tipo_recurso)}"
                    {"checked" if marcado else ""}
                >
                <span class="filtro-recurso-check">✓</span>
                <span class="filtro-recurso-texto">
                    <strong>{e(tipo_recurso)}</strong>
                    <small>{cantidad} actividad{"es" if cantidad != 1 else ""}</small>
                </span>
            </label>
            """

        bloque_advertencias_revision = ""
        if advertencias_drive:

            colores_aviso = {
                "Sin archivo en Drive": ("#fef3f2", "#b42318"),
                "Sin enlace Drive": ("#fef3f2", "#b42318"),
                "Carpeta Drive no legible": ("#fef3f2", "#b42318"),
                "Varios archivos en Drive": ("#fff4ed", "#b93815"),
                "Sin equivalente en el ZIP": ("#fef3f2", "#b42318"),
                "Tamano distinto": ("#fff4ed", "#b93815"),
                "Recurso en varias filas": ("#fffaeb", "#b54708"),
                "Copia repetida en el ZIP": ("#fffaeb", "#b54708"),
                "Copia repetida en Drive": ("#fffaeb", "#b54708"),
                "Nombre distinto": ("#eff8ff", "#175cd3"),
            }

            conteo_aviso = {}
            filas_aviso = ""

            for item in advertencias_drive:
                if not isinstance(item, dict):
                    item = {"tipo": "Diferencia", "detalle": str(item)}

                tipo = str(item.get("tipo") or "Diferencia")
                conteo_aviso[tipo] = conteo_aviso.get(tipo, 0) + 1

                fondo, letra = colores_aviso.get(tipo, ("#f2f4f7", "#475467"))

                actividad_txt = str(item.get("actividad") or "")
                fila_txt = str(item.get("fila") or "")

                filas_aviso += (
                    "<tr>"
                    + '<td style="white-space:nowrap;font-weight:700;'
                      'color:#475467;">' + (e(fila_txt) or "—") + "</td>"
                    + '<td style="color:#101828;">'
                      + (e(actividad_txt) or "<i>Todas las filas</i>") + "</td>"
                    + '<td style="white-space:nowrap;">'
                      + '<span style="display:inline-block;padding:3px 9px;'
                      'border-radius:999px;font-size:11px;font-weight:800;'
                      'background:' + fondo + ';color:' + letra + ';">'
                      + e(tipo) + "</span></td>"
                    + '<td style="color:#475467;">'
                      + e(item.get("detalle")) + "</td>"
                    + "</tr>"
                )

            resumen_tipos = " · ".join(
                e(tipo) + ": <b>" + str(cantidad) + "</b>"
                for tipo, cantidad in sorted(conteo_aviso.items())
            )

            bloque_advertencias_revision = (
                '<div style="grid-column:1/-1;margin-bottom:18px;'
                'background:#fff;border:1px solid #fedf89;border-radius:16px;'
                'overflow:hidden;">'

                + '<div style="background:#fffaeb;padding:15px 18px;'
                  'border-bottom:1px solid #fedf89;">'
                + '<strong style="font-size:14px;color:#b54708;">'
                + str(len(advertencias_drive))
                + " advertencia(s) en la comparación con Google Drive</strong>"
                + '<p style="margin:5px 0 8px;font-size:12.5px;color:#667085;">'
                + "El análisis terminó completo. Estas alertas no detuvieron el análisis. "
                + "Las filas sin coincidencia exacta Drive/ZIP no se cargarán "
                + "automáticamente hasta corregirse.</p>"
                + '<div style="font-size:12px;color:#667085;">'
                + resumen_tipos + "</div>"
                + "</div>"

                + '<div style="max-height:340px;overflow:auto;">'
                + '<table style="width:100%;border-collapse:collapse;'
                  'font-size:12.5px;">'
                + '<thead><tr style="background:#f9fafb;'
                  'position:sticky;top:0;">'
                + '<th style="text-align:left;padding:9px 14px;font-size:11px;'
                  'color:#667085;border-bottom:1px solid #e4e7ec;">FILA</th>'
                + '<th style="text-align:left;padding:9px 14px;font-size:11px;'
                  'color:#667085;border-bottom:1px solid #e4e7ec;">ACTIVIDAD</th>'
                + '<th style="text-align:left;padding:9px 14px;font-size:11px;'
                  'color:#667085;border-bottom:1px solid #e4e7ec;">TIPO</th>'
                + '<th style="text-align:left;padding:9px 14px;font-size:11px;'
                  'color:#667085;border-bottom:1px solid #e4e7ec;">DETALLE</th>'
                + "</tr></thead>"
                + '<tbody style="line-height:1.5;">' + filas_aviso + "</tbody>"
                + "</table></div></div>"
            )

        bloque_error_revision = ""
        if error:
            bloque_error_revision = f"""
            <div class="alerta-error" style="grid-column:1/-1;margin-bottom:18px;">
                <div class="alerta-icono">!</div>
                <div><strong>No se pudo iniciar el cargue</strong><p>{e(error)}</p></div>
            </div>
            """

        if es_modo_archivo:
            resumen_origen = (
                "Modo archivo · " + e(nombre_matriz or "Matriz local")
                + " · " + str(int((resultado.get("zip") or {}).get("total") or 0))
                + " recurso(s) H5P/PDF detectado(s) en el ZIP"
            )
            encabezado_recurso = "Resolución de recurso"
            encabezado_estado = "Estado"
        else:
            resumen_origen = (
                str(total_actividades) + " actividades analizadas · "
                + str(drive_validados) + " archivo(s) encontrado(s) en Drive · "
                + str(drive_coincidencias_zip) + " coincidencia(s) exacta(s) con el ZIP"
            )
            encabezado_recurso = "Archivo Drive"
            encabezado_estado = "Estado ZIP"

        bloque_test_html = ""
        test_info = resultado.get("test_info")
        if test_info:
            test_job_id = test_info.get("test_job_id", "")
            cant_tests = test_info.get("cantidad_tests", 1)
            cant_preg = test_info.get("cantidad_preguntas", 0)
            nom_doc = test_info.get("nombre_documento", "documento.docx")
            bloque_test_html = f"""
            <div class="panel" style="margin-bottom:20px;border:2px solid #f59e0b;background:#fffdf5;border-radius:16px;padding:22px;">
                <div style="display:flex;gap:14px;align-items:flex-start;">
                    <div class="archivo-icono naranja" style="width:44px;height:44px;border-radius:12px;font-size:24px;">📝</div>
                    <div style="flex:1;">
                        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                            <div>
                                <h3 style="margin:0 0 4px;color:#92400e;font-size:18px;font-weight:800;">Test Evaluativo Preparado</h3>
                                <p style="margin:0;color:#78350f;font-size:13px;">Documento: <strong>{e(nom_doc)}</strong> · {cant_tests} examen(es) con {cant_preg} preguntas detectadas.</p>
                            </div>
                            <a href="/tests/{test_job_id}/revision" class="boton-selector" style="background:#d97706;padding:11px 20px;font-size:13px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;border-radius:8px;">
                                Revisar y Configurar Test ➔
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            """

        contenido = f"""
        <section id="cargue-principal" class="encabezado-exito panel">
            <div class="check-grande">✓</div>
            <div>
                <h1>Análisis completado</h1>
                <p>{resumen_origen}</p>
            </div>
        </section>

        <section class="resumen-grid">
            <div class="resumen-card"><span>Actividades</span><strong>{total_actividades}</strong></div>
            <div class="resumen-card verde"><span>OVI</span><strong>{total_ovi}</strong></div>
            <div class="resumen-card azul"><span>OVA</span><strong>{total_ova}</strong></div>
            <div class="resumen-card morado"><span>Retos</span><strong>{total_retos}</strong></div>
            <div class="resumen-card violeta"><span>H5P</span><strong>{total_h5p}</strong></div>
            <div class="resumen-card rojo"><span>PDF</span><strong>{total_pdf}</strong></div>
        </section>

        {bloque_test_html}
        {bloque_advertencias_revision}
        {bloque_error_revision}

        <section class="panel selector-recursos-panel">
            <div class="selector-recursos-cabecera">
                <div class="titulo-bloque">
                    <h2>Selecciona qué se cargará</h2>
                    <p>Marca tipos completos para seleccionar rápido y ajusta actividades individuales en la tabla.</p>
                </div>
                <div class="selector-recursos-contador">
                    <strong id="contador-seleccionadas">{total_seleccionadas} de {total_actividades}</strong>
                    <span>actividades seleccionadas</span>
                </div>
            </div>

            <div class="filtros-recursos">
                {filtros_tipo_html}
            </div>

            <div class="selector-recursos-acciones">
                <button type="button" id="seleccionar-todas-actividades">Seleccionar todo</button>
                <button type="button" id="limpiar-seleccion-actividades">Limpiar selección</button>
            </div>
        </section>

        <section class="revision-grid">
            <div class="panel tabla-panel">
                <div class="titulo-bloque">
                    <h2>Actividades detectadas</h2>
                    <p>Revisa que las actividades y categorías sean correctas.</p>
                </div>

                <div class="tabla-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>✓</th>
                                <th>Semana</th>
                                <th>Unidad</th>
                                <th>Actividad</th>
                                <th>Categoría</th>
                                <th>Tipo de recurso</th>
                                <th>Formato</th>
                                <th>{e(encabezado_recurso)}</th>
                                <th>{e(encabezado_estado)}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="panel credenciales-panel">
                <div class="titulo-bloque">
                    <h2>Acceso a PRIZMA</h2>
                    <p>Ingresa tus credenciales para autorizar este cargue.</p>
                </div>

                <form id="form-iniciar-cargue" action="/iniciar/{trabajo_id}" method="post" autocomplete="off">
                    <label class="campo-label" for="usuario_prizma">Usuario PRIZMA</label>
                    <div class="campo-moderno">
                        <span>♙</span>
                        <input
                            id="usuario_prizma"
                            type="text"
                            name="usuario_prizma"
                            placeholder="Ingresa tu usuario"
                            autocomplete="off"
                            required
                        >
                    </div>

                    <label class="campo-label" for="contrasena_prizma">Contraseña PRIZMA</label>
                    <div class="campo-moderno">
                        <span>⌾</span>
                        <input
                            id="contrasena_prizma"
                            type="password"
                            name="contrasena_prizma"
                            placeholder="Ingresa tu contraseña"
                            autocomplete="new-password"
                            required
                        >
                    </div>

                    <div class="caja-seguridad">
                        <strong>Credenciales de uso temporal</strong>
                        <span>La aplicación no las escribe en archivos, reportes ni base de datos.</span>
                    </div>

                    <button class="boton-principal" type="submit">
                        <span>↗</span>
                        Iniciar cargue en PRIZMA
                    </button>
                </form>
            </div>
        </section>

        <a class="boton-secundario" href="/">← Cambiar matriz o ZIP</a>
        """

    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cargue Prizma Pro</title>
        <link rel="icon" type="image/png" href="/auto-prizma-logo.png">
        <style>
            :root {
                --fondo: #f7f8fc;
                --panel: #ffffff;
                --texto: #101828;
                --muted: #667085;
                --borde: #e5e7ef;
                --morado: #5b48e8;
                --morado-2: #4338ca;
                --verde: #0ea968;
                --azul: #1976d2;
                --rojo: #ef4444;
                --sombra: 0 10px 30px rgba(29, 41, 57, .06);
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: var(--fondo);
                color: var(--texto);
            }

            .app { min-height: 100vh; display: grid; grid-template-columns: 235px 1fr; }

            .sidebar {
                position: sticky;
                top: 0;
                height: 100vh;
                background: #fff;
                border-right: 1px solid var(--borde);
                padding: 28px 20px;
                display: flex;
                flex-direction: column;
            }

            .marca { display: flex; align-items: center; gap: 12px; margin-bottom: 34px; }
            .logo {
                width: 44px; height: 44px; border-radius: 13px;
                display: grid; place-items: center;
                background: transparent;
                box-shadow: none;
                flex: 0 0 44px;
                overflow: hidden;
            }
            .logo-imagen { width: 100%; height: 100%; object-fit: contain; display: block; }
            .marca strong { display: block; font-size: 18px; }
            .marca span { display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }

            .nav { display: grid; gap: 8px; }
            .nav-item {
                padding: 12px 14px; border-radius: 11px; color: #475467; font-size: 14px;
                display: flex; gap: 11px; align-items: center; text-decoration: none; transition: .18s ease;
            }
            a.nav-item:hover { background: #f7f5ff; color: #4f46e5; }
            .nav-item.activo { background: #f1efff; color: #4f46e5; font-weight: 700; }
            .nav-item.proximamente { opacity: .48; cursor: default; }
            .nav-item.proximamente small { margin-left: auto; font-size: 9px; }

            .estado-servicio {
                margin-top: auto; border: 1px solid var(--borde); border-radius: 14px;
                padding: 15px; background: #fff;
            }
            .servicio-linea { display: flex; align-items: center; gap: 8px; color: #07894f; font-size: 13px; font-weight: 700; }
            .punto { width: 8px; height: 8px; border-radius: 50%; background: #15b76a; }
            .servicio-mini { margin-top: 13px; display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); }
            .chip { background: #eef4ff; color: #3538cd; padding: 4px 8px; border-radius: 999px; }

            .contenido { padding: 28px 34px 45px; max-width: 1500px; width: 100%; margin: 0 auto; }
            .layout-inicio { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 24px; align-items: start; }
            #google-conexion-panel { grid-column: 1 / -1; }

            .prizma-loader {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 24px;

    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(7px);
    -webkit-backdrop-filter: blur(7px);
}

.prizma-loader.activo {
    display: flex;
}

.loader-contenido {
    width: min(360px, 92vw);
    padding: 30px 26px;
    border-radius: 24px;
    text-align: center;

    background: rgba(255, 255, 255, 0.20);
    border: 1px solid rgba(255, 255, 255, 0.45);

    box-shadow:
        0 20px 60px rgba(31, 41, 55, 0.10),
        inset 0 1px 0 rgba(255, 255, 255, 0.55);

    backdrop-filter: blur(13px);
    -webkit-backdrop-filter: blur(13px);
}

.loader-logo {
    width: 125px;
    height: 125px;
    object-fit: contain;
    display: block;
    margin: 0 auto 20px;

    animation: giro-prizma 2.1s linear infinite;

    filter:
        drop-shadow(0 12px 24px rgba(79, 70, 229, 0.18))
        drop-shadow(0 0 18px rgba(43, 164, 255, 0.12));
}

.loader-contenido strong {
    display: block;
    font-size: 17px;
    font-weight: 750;
    color: #111827;
}

.loader-contenido span {
    display: block;
    margin-top: 8px;
    color: rgba(71, 84, 103, 0.90);
    font-size: 12px;
    line-height: 1.5;
}

@keyframes giro-prizma {
    to {
        transform: rotate(360deg);
    }
}

            .panel {
                background: var(--panel); border: 1px solid var(--borde); border-radius: 16px;
                box-shadow: var(--sombra);
            }

            .encabezado-pagina {
                grid-column: 1 / -1; background: #fff; border: 1px solid var(--borde);
                border-radius: 16px; padding: 24px 28px; box-shadow: var(--sombra);
            }
            .encabezado-pagina h1, .encabezado-exito h1 { margin: 0; font-size: 25px; }
            .encabezado-pagina p, .encabezado-exito p { margin: 6px 0 0; color: var(--muted); }

            .google-conexion {
                grid-column: 1 / -1;
                display: flex;
                align-items: center;
                gap: 14px;
                padding: 16px 18px;
                background: #fff;
                border: 1px solid var(--borde);
                border-radius: 14px;
                box-shadow: var(--sombra);
            }
            .google-conexion.google-ok {
                border-color: #a7e7c7;
                background: #fbfffd;
            }
            .google-icono {
                width: 42px;
                height: 42px;
                border-radius: 11px;
                display: grid;
                place-items: center;
                background: #f5f6f8;
                color: #344054;
                font-size: 18px;
                font-weight: 900;
                flex: 0 0 42px;
            }
            .google-texto { min-width: 0; flex: 1 1 auto; }
            .google-texto strong { display: block; font-size: 14px; }
            .google-texto span {
                display: block;
                margin-top: 4px;
                color: var(--muted);
                font-size: 12px;
                line-height: 1.45;
            }
            .google-boton {
                border: 0;
                border-radius: 9px;
                padding: 10px 14px;
                background: #4f46e5;
                color: #fff;
                text-decoration: none;
                font-size: 12px;
                font-weight: 800;
                cursor: pointer;
                white-space: nowrap;
            }
            .google-boton.secundario {
                background: #fff;
                color: #475467;
                border: 1px solid #d0d5dd;
            }

            .panel-principal { padding: 26px; }
            .titulo-seccion { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 18px; }
            .titulo-seccion h2, .titulo-bloque h2 { margin: 0; font-size: 18px; }
            .titulo-seccion p, .titulo-bloque p { margin: 5px 0 0; color: var(--muted); font-size: 13px; }
            .numero-seccion {
                width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center;
                background: #f0edff; color: #5145cd; font-weight: 800; font-size: 13px;
            }

            .grid-archivos { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
            .tarjeta-archivo {
                border: 1px dashed #cfd4e1; border-radius: 14px; padding: 20px;
                cursor: pointer; transition: .18s ease; background: #fff;
                min-width: 0; overflow: hidden;
            }
            .tarjeta-archivo:hover { border-color: #8176f2; background: #fbfaff; transform: translateY(-1px); }
            .tarjeta-archivo.arrastrando { border-color: #5b48e8; background: #f5f3ff; box-shadow: inset 0 0 0 2px rgba(91,72,232,.10); }
            .tarjeta-archivo input { display: none; }
            .archivo-cabecera { display: flex; align-items: center; gap: 12px; min-width: 0; }
            .archivo-cabecera > div:last-child { min-width: 0; }
            .archivo-cabecera strong { display: block; font-size: 14px; }
            .archivo-cabecera span { display: block; font-size: 12px; color: var(--muted); margin-top: 4px; }
            .archivo-icono {
                width: 40px; height: 40px; border-radius: 10px; display: grid; place-items: center;
                flex: 0 0 40px;
            }
            .archivo-icono svg { width: 23px; height: 23px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
            .archivo-icono.verde { background: #e8f8f0; color: #0a9b5b; }
            .archivo-icono.morado { background: #f0edff; color: #5b48e8; }
            .archivo-icono.naranja { background: #fef3c7; color: #d97706; }
            .selector-modo-matriz label {
                border: 1px solid #e5e7ef;
                transition: .15s ease;
            }
            .selector-modo-matriz label:has(input:checked) {
                border-color: #d8d5ff; background: #f8f7ff;
            }
            #bloque-test .selector-modo-matriz label:has(input:checked) {
                border-color: #fde68a; background: #fffdf5;
            }
            .caja-datos-academicos { background: #f8f9fc; border: 1px solid #eaecf0; }
            .selector-archivo {
                margin-top: 18px; min-height: 46px; border: 1px solid var(--borde); border-radius: 10px;
                padding: 9px 12px; display: flex; align-items: center; gap: 12px;
                min-width: 0; overflow: hidden;
            }
            .boton-selector {
                background: #5b48e8; color: #fff; padding: 8px 12px; border-radius: 8px;
                font-size: 12px; font-weight: 700; white-space: nowrap;
            }
            .nombre-archivo { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1 1 auto; display: block; }

            .separador { height: 1px; background: var(--borde); margin: 26px 0; }
            .grid-tipos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
            .tarjeta-tipo {
                position: relative; border: 1px solid var(--borde); border-radius: 14px; padding: 18px;
                min-height: 125px; cursor: pointer; transition: .18s ease; display: flex; flex-direction: column;
            }
            .tarjeta-tipo:hover { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(16,24,40,.06); }
            .tarjeta-tipo input { position: absolute; opacity: 0; pointer-events: none; }
            .check-personalizado {
                position: absolute; top: 15px; right: 15px; width: 22px; height: 22px;
                border-radius: 6px; display: grid; place-items: center; color: white; font-size: 13px;
                background: #d0d5dd;
            }
            .tarjeta-tipo:has(input:checked).tipo-verde { border-color: #65d6a1; background: #fbfffd; }
            .tarjeta-tipo:has(input:checked).tipo-verde .check-personalizado { background: #0ea968; }
            .tarjeta-tipo:has(input:checked).tipo-azul { border-color: #7ab6ef; background: #fbfdff; }
            .tarjeta-tipo:has(input:checked).tipo-azul .check-personalizado { background: #1976d2; }
            .tarjeta-tipo:has(input:checked).tipo-morado { border-color: #b9a8f5; background: #fdfcff; }
            .tarjeta-tipo:has(input:checked).tipo-morado .check-personalizado { background: #8b5cf6; }
            .tarjeta-tipo:has(input:checked).tipo-naranja { border-color: #f59e0b; background: #fffdf5; }
            .tarjeta-tipo:has(input:checked).tipo-naranja .check-personalizado { background: #d97706; }
            .tipo-icono { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; margin-bottom: 15px; }
            .tipo-icono svg { width: 25px; height: 25px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
            .icono-ovi { color:#079455; background:#e9f9f1; }
            .icono-ova { color:#1976d2; background:#eaf4ff; }
            .icono-reto { color:#7f56d9; background:#f1ebff; }
            .icono-test { color:#d97706; background:#fef3c7; }
            .tarjeta-tipo strong { font-size: 16px; }
            .tarjeta-tipo small { color: var(--muted); margin-top: 6px; line-height: 1.4; }

            .boton-principal {
                width: 100%; border: 0; border-radius: 11px; padding: 15px 20px; margin-top: 24px;
                color: #fff; font-size: 15px; font-weight: 800; cursor: pointer;
                background: linear-gradient(90deg, #5145e5, #4f46e5 55%, #5f45df);
                box-shadow: 0 8px 20px rgba(79,70,229,.20);
            }
            .boton-principal:hover { filter: brightness(.98); transform: translateY(-1px); }
            .boton-principal span { margin-right: 8px; }
            .nota-seguridad { text-align: center; color: var(--muted); font-size: 12px; margin: 14px 0 0; }

            .panel-ayuda { padding: 24px; }
            .panel-ayuda h3 { margin: 0 0 20px; font-size: 17px; }
            .paso { display: grid; grid-template-columns: 30px 1fr; gap: 12px; align-items: start; margin-bottom: 20px; color: #475467; font-size: 13px; line-height: 1.5; }
            .paso b { width: 28px; height: 28px; border-radius: 50%; background: #f1efff; color: #4f46e5; display: grid; place-items: center; }
            .ayuda-separador { height: 1px; background: var(--borde); margin: 24px 0; }
            .titulo-consejos { color: #4f46e5; }
            .consejo { color: #475467; font-size: 13px; line-height: 1.55; }

            .alerta-advertencia {
                display:flex; gap:12px; align-items:flex-start; padding:16px 18px;
                border:1px solid #f5c451; background:#fff8df; color:#7a4b00;
                border-radius:16px; box-shadow:var(--sombra);
            }
            .alerta-advertencia p { margin:4px 0 8px; color:#805b16; }
            .alerta-advertencia ul { margin:8px 0 0; padding-left:20px; }
            .alerta-advertencia li { margin:6px 0; line-height:1.4; }
            .alerta-advertencia-icono {
                width:28px; height:28px; border-radius:50%; background:#f4b223;
                color:#4b3200; display:grid; place-items:center; font-weight:900; flex:0 0 auto;
            }

            .alerta-error {
                grid-column: 1 / -1; display: flex; gap: 12px; padding: 16px 18px; border-radius: 12px;
                background: #fff1f2; border: 1px solid #fecdd3; color: #9f1239;
            }
            .alerta-error p { margin: 4px 0 0; }
            .alerta-icono { width: 28px; height: 28px; border-radius: 50%; background: #ef4444; color: #fff; display: grid; place-items: center; font-weight: 900; }

            .encabezado-exito { padding: 22px 24px; display: flex; gap: 15px; align-items: center; margin-bottom: 0; grid-column: 1 / -1; }
            .check-grande { width: 48px; height: 48px; border-radius: 14px; background: #e9f9f1; color: #08a45e; display: grid; place-items: center; font-size: 25px; font-weight: 900; }
            .resumen-grid { display: grid; grid-template-columns: repeat(6, minmax(110px, 1fr)); gap: 14px; margin: 18px 0 20px; grid-column: 1 / -1; min-width: 0; }
            .resumen-card { background: #fff; border: 1px solid var(--borde); border-radius: 14px; padding: 17px; box-shadow: var(--sombra); text-align: center; }
            .resumen-card span { display: block; color: var(--muted); font-size: 12px; }
            .resumen-card strong { display: block; font-size: 27px; margin-top: 6px; }
            .resumen-card.verde strong { color: #0a9b5b; }
            .resumen-card.azul strong { color: #1976d2; }
            .resumen-card.morado strong, .resumen-card.violeta strong { color: #6d4ce8; }
            .resumen-card.rojo strong { color: #e5484d; }

            .selector-recursos-panel { grid-column:1/-1; padding:24px; margin-bottom:20px; }
            .selector-recursos-cabecera { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
            .selector-recursos-cabecera .titulo-bloque { margin-bottom:0; }
            .selector-recursos-contador { text-align:right; min-width:170px; }
            .selector-recursos-contador strong { display:block; font-size:18px; color:#4f46e5; }
            .selector-recursos-contador span { display:block; margin-top:3px; color:var(--muted); font-size:11px; }
            .filtros-recursos { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; margin-top:18px; }
            .filtro-recurso-item { position:relative; display:flex; gap:10px; align-items:center; border:1px solid var(--borde); border-radius:12px; padding:12px; cursor:pointer; background:#fff; }
            .filtro-recurso-item:hover { border-color:#b9b3f8; background:#fbfaff; }
            .filtro-recurso-item input { position:absolute; opacity:0; pointer-events:none; }
            .filtro-recurso-check { width:22px; height:22px; border-radius:6px; display:grid; place-items:center; background:#d0d5dd; color:#fff; font-size:12px; font-weight:900; flex:0 0 22px; }
            .filtro-recurso-item:has(input:checked) { border-color:#9b8ff2; background:#faf9ff; }
            .filtro-recurso-item:has(input:checked) .filtro-recurso-check { background:#5b48e8; }
            .filtro-recurso-texto strong, .filtro-recurso-texto small { display:block; }
            .filtro-recurso-texto strong { font-size:12px; color:#344054; }
            .filtro-recurso-texto small { margin-top:3px; color:var(--muted); font-size:10px; }
            .selector-recursos-acciones { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
            .selector-recursos-acciones button { border:1px solid #d8d6f8; background:#fff; color:#4f46e5; border-radius:9px; padding:8px 11px; font-size:11px; font-weight:800; cursor:pointer; }
            .selector-recursos-acciones button:hover { background:#f8f7ff; }
            .celda-seleccion { width:48px; text-align:center; }
            .actividad-seleccion { width:18px; height:18px; accent-color:#5b48e8; cursor:pointer; }
            .badge-recurso { background:#eef4ff; color:#3538cd; white-space:nowrap; }

            .revision-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(310px, .75fr); gap: 20px; align-items: start; grid-column: 1 / -1; min-width: 0; }
            .tabla-panel, .credenciales-panel { padding: 24px; }
            .titulo-bloque { margin-bottom: 18px; }
            .tabla-scroll { max-height: 570px; overflow: auto; border: 1px solid var(--borde); border-radius: 12px; }
            table { width: 100%; border-collapse: collapse; font-size: 13px; }
            thead { position: sticky; top: 0; background: #f8f9fc; z-index: 1; }
            th { text-align: left; color: #475467; font-size: 12px; padding: 12px 13px; border-bottom: 1px solid var(--borde); }
            td { padding: 12px 13px; border-bottom: 1px solid #eef0f4; vertical-align: middle; }
            tbody tr:last-child td { border-bottom: 0; }
            .celda-actividad { min-width: 260px; }
            .badge { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 10px; font-weight: 800; }
            .badge-verde { background: #e9f9f1; color: #07894f; }
            .badge-azul { background: #eaf4ff; color: #1565c0; }
            .badge-morado { background: #f1ebff; color: #7048d7; }
            .badge-gris { background: #f2f4f7; color: #475467; }
            .badge-h5p { background: #f1ebff; color: #6941c6; }
            .badge-pdf { background: #fff0f1; color: #d92d20; }

            .campo-label { display: block; font-size: 13px; font-weight: 700; margin: 18px 0 8px; }
            .campo-moderno { display: flex; align-items: center; gap: 10px; border: 1px solid #d7dbe5; border-radius: 10px; padding: 0 12px; background: #fff; }
            .campo-moderno span { color: #667085; }
            .campo-moderno input { width: 100%; border: 0; outline: 0; padding: 13px 0; font-size: 14px; background: transparent; }
            .caja-seguridad { margin-top: 20px; background: #f8f7ff; border: 1px solid #d9d4ff; border-radius: 11px; padding: 14px; }
            .caja-seguridad strong, .caja-seguridad span { display: block; }
            .caja-seguridad strong { font-size: 12px; color: #4f46e5; }
            .caja-seguridad span { font-size: 12px; color: var(--muted); margin-top: 5px; line-height: 1.45; }
            .boton-secundario { grid-column: 1 / -1; display: inline-block; margin-top: 20px; color: #4f46e5; text-decoration: none; font-weight: 700; font-size: 14px; padding: 11px 15px; border: 1px solid #d8d6f8; border-radius: 10px; background: #fff; }

            @media (max-width: 1050px) {
                .app { grid-template-columns: 1fr; }
                .sidebar { display: none; }
                .contenido { padding: 20px; }
                .layout-inicio { grid-template-columns: 1fr; }
                .panel-ayuda { order: 2; }
                .resumen-grid { grid-template-columns: repeat(3, 1fr); }
                .revision-grid { grid-template-columns: 1fr; }
            }

            @media (max-width: 700px) {
                .google-conexion { align-items: flex-start; flex-wrap: wrap; }
                .google-conexion .google-boton { width: 100%; text-align: center; }
                .grid-archivos, .grid-tipos { grid-template-columns: 1fr; }
                .resumen-grid { grid-template-columns: repeat(2, 1fr); }
                .selector-recursos-cabecera { flex-direction:column; }
                .selector-recursos-contador { text-align:left; min-width:0; }
                .contenido { padding: 14px; }
                .panel-principal, .tabla-panel, .credenciales-panel { padding: 18px; }
            }
        </style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script>
    </head>
    <body>
        <div id="prizma-loader" class="prizma-loader" role="status" aria-live="polite" aria-hidden="true">
            <div class="loader-contenido">
                <img class="loader-logo" src="/auto-prizma-logo.png" alt="">
                <strong id="prizma-loader-texto">Procesando...</strong>
                <span>Espera mientras Auto Prizma prepara la información.</span>
            </div>
        </div>
        <div class="app">
            <aside class="sidebar">
                <div class="marca">
                    <div class="logo" aria-label="Cargue Prizma Pro">
                        <img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro">
                    </div>
                    <div>
                        <strong>Cargue Prizma Pro</strong>
                        <span>Cargue Prizma</span>
                    </div>
                </div>

                <nav class="nav">
                    <a class="nav-item activo" href="/">⌂ <span>Inicio</span></a>
                    <a class="nav-item" href="/tests">▣ <span>Test</span></a>
                    <a class="nav-item" href="/cargue-actual">⇧ <span>Cargue actual</span></a>
                    <a class="nav-item" href="/historial">◷ <span>Historial</span></a>
                    <a class="nav-item" href="/reportes">▥ <span>Reportes</span></a><a class="nav-item" href="/cambiar-clave">✎ <span>Mi contraseña</span></a><a class="nav-item" href="/salir">⏻ <span>Salir</span></a>
                </nav>

                <div class="estado-servicio">
                    <div class="servicio-linea"><span class="punto"></span> Servicio activo</div>
                    <div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div>
                    <div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div>
                </div>
            </aside>

            <main class="contenido">
                <div class="layout-inicio">
                    """ + contenido + """
                </div>
            </main>
        </div>

        <script>
            const matriz = document.getElementById('archivo-matriz');
            const zip = document.getElementById('archivo-zip');
            const googleUrl = document.getElementById('google-sheet-url');
            const bloqueLink = document.getElementById('bloque-matriz-link');
            const bloqueArchivo = document.getElementById('bloque-matriz-archivo');
            const bloqueGoogle = document.getElementById('google-conexion-panel');
            const radiosModo = document.querySelectorAll('input[name="modo_matriz"]');
            const loader = document.getElementById('prizma-loader');
            const loaderTexto = document.getElementById('prizma-loader-texto');

            function mostrarLoader(texto) {
                if (!loader) return;
                if (loaderTexto && texto) loaderTexto.textContent = texto;
                loader.classList.add('activo');
                loader.setAttribute('aria-hidden', 'false');
            }

            const formularioAnalisis = document.querySelector('form[action="/analizar"]');
            if (formularioAnalisis) {
                formularioAnalisis.addEventListener('submit', () => {
                    mostrarLoader('Analizando matriz y recursos...');
                });
            }

            const formularioInicio = document.querySelector('form[action^="/iniciar/"]');
            const actividadesSeleccion = Array.from(document.querySelectorAll('.actividad-seleccion'));
            const filtrosTipoRecurso = Array.from(document.querySelectorAll('.filtro-tipo-recurso'));
            const contadorSeleccionadas = document.getElementById('contador-seleccionadas');
            const botonSeleccionarTodas = document.getElementById('seleccionar-todas-actividades');
            const botonLimpiarSeleccion = document.getElementById('limpiar-seleccion-actividades');

            function actualizarEstadoSeleccion() {
                const totalMarcadas = actividadesSeleccion.filter((item) => item.checked).length;
                if (contadorSeleccionadas) {
                    contadorSeleccionadas.textContent = totalMarcadas + ' de ' + actividadesSeleccion.length;
                }

                filtrosTipoRecurso.forEach((filtro) => {
                    const tipo = filtro.dataset.tipoRecurso || '';
                    const delTipo = actividadesSeleccion.filter(
                        (actividad) => (actividad.dataset.tipoRecurso || '') === tipo
                    );
                    const marcadas = delTipo.filter((actividad) => actividad.checked).length;
                    filtro.checked = delTipo.length > 0 && marcadas === delTipo.length;
                    filtro.indeterminate = marcadas > 0 && marcadas < delTipo.length;
                });
            }

            filtrosTipoRecurso.forEach((filtro) => {
                filtro.addEventListener('change', () => {
                    const tipo = filtro.dataset.tipoRecurso || '';
                    actividadesSeleccion.forEach((actividad) => {
                        if ((actividad.dataset.tipoRecurso || '') === tipo) {
                            actividad.checked = filtro.checked;
                        }
                    });
                    actualizarEstadoSeleccion();
                });
            });

            actividadesSeleccion.forEach((actividad) => {
                actividad.addEventListener('change', actualizarEstadoSeleccion);
            });

            if (botonSeleccionarTodas) {
                botonSeleccionarTodas.addEventListener('click', () => {
                    actividadesSeleccion.forEach((actividad) => { actividad.checked = true; });
                    actualizarEstadoSeleccion();
                });
            }

            if (botonLimpiarSeleccion) {
                botonLimpiarSeleccion.addEventListener('click', () => {
                    actividadesSeleccion.forEach((actividad) => { actividad.checked = false; });
                    actualizarEstadoSeleccion();
                });
            }

            actualizarEstadoSeleccion();

            if (formularioInicio) {
                formularioInicio.addEventListener('submit', (evento) => {
                    const totalMarcadas = actividadesSeleccion.filter((item) => item.checked).length;
                    if (actividadesSeleccion.length && totalMarcadas === 0) {
                        evento.preventDefault();
                        alert('Selecciona al menos una actividad para cargar en PRIZMA.');
                        return;
                    }
                    mostrarLoader('Procesando cargue...');
                });
            }

            window.addEventListener('pageshow', () => {
                if (!loader) return;
                loader.classList.remove('activo');
                loader.setAttribute('aria-hidden', 'true');
            });

            function aplicarModoMatriz() {
                const seleccionado = document.querySelector('input[name="modo_matriz"]:checked');
                const modo = seleccionado ? seleccionado.value : 'link';
                const esArchivo = modo === 'archivo';
                if (bloqueLink) bloqueLink.style.display = esArchivo ? 'none' : '';
                if (bloqueArchivo) bloqueArchivo.style.display = esArchivo ? '' : 'none';
                if (bloqueGoogle) bloqueGoogle.style.display = esArchivo ? 'none' : '';
                if (googleUrl) {
                    googleUrl.disabled = esArchivo;
                    googleUrl.required = !esArchivo;
                }
                if (matriz) {
                    matriz.disabled = !esArchivo;
                    matriz.required = esArchivo;
                }
            }

            radiosModo.forEach((radio) => radio.addEventListener('change', aplicarModoMatriz));
            aplicarModoMatriz();

            function actualizarNombre(input, destinoId) {
                const destino = document.getElementById(destinoId);
                if (!destino || !input) return;
                destino.textContent = input.files.length ? input.files[0].name : 'Ningún archivo seleccionado';
                destino.title = input.files.length ? input.files[0].name : '';
            }

            if (matriz) matriz.addEventListener('change', () => actualizarNombre(matriz, 'nombre-matriz'));
            if (zip) zip.addEventListener('change', () => actualizarNombre(zip, 'nombre-zip'));

            document.querySelectorAll('.zona-drop').forEach((zona) => {
                const input = document.getElementById(zona.dataset.input);
                if (!input) return;

                ['dragenter', 'dragover'].forEach((evento) => {
                    zona.addEventListener(evento, (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        zona.classList.add('arrastrando');
                    });
                });

                ['dragleave', 'drop'].forEach((evento) => {
                    zona.addEventListener(evento, (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        zona.classList.remove('arrastrando');
                    });
                });

                zona.addEventListener('drop', (e) => {
                    const archivos = e.dataTransfer.files;
                    if (!archivos || !archivos.length) return;
                    const transferencia = new DataTransfer();
                    transferencia.items.add(archivos[0]);
                    input.files = transferencia.files;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                });
            });

            // Gestión interactiva del apartado Test Evaluativo
            const chkTest = document.getElementById('chk-test');
            const bloqueTest = document.getElementById('bloque-test');
            const testDocx = document.getElementById('archivo-test-docx');
            const testUrl = document.getElementById('test-google-doc-url');
            const testDatos = document.getElementById('test-datos-academicos');
            const testSemestre = document.getElementById('test-semestre');
            const radiosTest = document.querySelectorAll('input[name="modo_test"]');

            function aplicarModoTest() {
                const sel = document.querySelector('input[name="modo_test"]:checked');
                const esArchivo = !sel || sel.value === 'archivo';
                const bloqueTestArchivo = document.getElementById('bloque-test-archivo');
                const bloqueTestLink = document.getElementById('bloque-test-link');
                const activo = chkTest && chkTest.checked;

                if (bloqueTestArchivo) bloqueTestArchivo.style.display = esArchivo ? '' : 'none';
                if (bloqueTestLink) bloqueTestLink.style.display = esArchivo ? 'none' : '';

                if (testDocx) {
                    testDocx.disabled = !activo || !esArchivo;
                    testDocx.required = activo && esArchivo;
                }
                if (testUrl) {
                    testUrl.disabled = !activo || esArchivo;
                    testUrl.required = activo && !esArchivo;
                }
            }

            function toggleTest() {
                const activo = chkTest && chkTest.checked;
                if (bloqueTest) bloqueTest.style.display = activo ? '' : 'none';
                if (testDatos) {
                    testDatos.disabled = !activo;
                    testDatos.required = activo;
                }
                if (testSemestre) {
                    testSemestre.disabled = !activo;
                    testSemestre.required = activo;
                }
                aplicarModoTest();
                ajustarRequeridosGenerales();
            }

            function ajustarRequeridosGenerales() {
                const chkOvi = document.querySelector('input[name="ovi"]');
                const chkOva = document.querySelector('input[name="ova"]');
                const chkRetos = document.querySelector('input[name="retos"]');
                const tieneRecursos = (chkOvi && chkOvi.checked) || (chkOva && chkOva.checked) || (chkRetos && chkRetos.checked);

                if (zip) {
                    zip.required = tieneRecursos;
                }
                const selModo = document.querySelector('input[name="modo_matriz"]:checked');
                const esArchivo = selModo ? selModo.value === 'archivo' : false;
                if (googleUrl) {
                    googleUrl.required = tieneRecursos && !esArchivo;
                }
                if (matriz) {
                    matriz.required = tieneRecursos && esArchivo;
                }
            }

            if (chkTest) chkTest.addEventListener('change', toggleTest);
            radiosTest.forEach(r => r.addEventListener('change', aplicarModoTest));
            if (testDocx) testDocx.addEventListener('change', () => actualizarNombre(testDocx, 'nombre-test-docx'));
            document.querySelectorAll('input[name="ovi"], input[name="ova"], input[name="retos"]').forEach(cb => {
                cb.addEventListener('change', ajustarRequeridosGenerales);
            });
            toggleTest();
        </script>
    </body>
    </html>
    """
