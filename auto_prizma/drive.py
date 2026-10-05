"""Lectura de enlaces de la matriz en Google Sheets y listado de carpetas de Google Drive.
"""

from googleapiclient.discovery import build
import motor_prizma as motor_prizma_modulo
from motor_prizma import normalizar_texto
import re
import threading

from auto_prizma.sesiones import (
    _normalizar_usuario,
    _usuario_actual,
)
from auto_prizma.google_oauth import _cargar_credenciales_google


# ============================================================
# GOOGLE DRIVE PRIVADO - MODO ULTRARRAPIDO
# ============================================================
#
# Objetivo:
# - NO descargar H5P/PDF desde Google Drive.
# - NO abrir cada archivo.
# - Consultar SOLO metadatos: nombre + tamano exacto.
# - Consultar muchas carpetas en BATCH para evitar una peticion HTTP
#   secuencial por cada actividad.
# - Guardar el resultado en el cache del motor. Durante el cargue a
#   PRIZMA, el motor reutiliza ese cache y no vuelve a consultar Drive.
#

DRIVE_BATCH_MAX = 100

# Recursos resueltos por el preflight del trabajo que esta ejecutando
# cada worker. Esto evita volver a consultar Drive dentro de PRIZMA.
_DRIVE_THREAD_LOCAL = threading.local()
_CACHE_ARCHIVOS_DRIVE = {}
_CACHE_ARCHIVOS_DRIVE_LOCK = threading.Lock()
_CACHE_REFERENCIAS_DRIVE = {}
_CACHE_REFERENCIAS_DRIVE_LOCK = threading.Lock()


def _clave_actividad_drive(actividad):
    return (
        str(actividad.get("programa") or "").strip().casefold(),
        str(actividad.get("curso") or "").strip().casefold(),
        str(actividad.get("hoja") or "").strip().casefold(),
        int(actividad.get("fila_excel") or 0),
        str(actividad.get("nombre") or "").strip().casefold(),
        str(actividad.get("tipo_archivo") or "").strip().upper(),
    )


def _recurso_resuelto_thread(actividad):
    mapa = getattr(_DRIVE_THREAD_LOCAL, "recursos", None) or {}
    return mapa.get(_clave_actividad_drive(actividad))


def _extraer_referencia_drive(url):
    url = str(url or "").strip()
    if not url:
        return None, None

    patrones_carpeta = [
        r"drive\.google\.com/(?:drive/(?:u/\d+/)?folders|folders)/([A-Za-z0-9_-]+)",
    ]
    for patron in patrones_carpeta:
        m = re.search(patron, url, flags=re.IGNORECASE)
        if m:
            return "folder", m.group(1)

    patrones_archivo = [
        r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)",
        r"drive\.google\.com/(?:open|uc)\?[^#]*\bid=([A-Za-z0-9_-]+)",
    ]
    for patron in patrones_archivo:
        m = re.search(patron, url, flags=re.IGNORECASE)
        if m:
            return "file", m.group(1)

    return None, None


def _extraer_gid(url_google_sheet):
    """Devuelve el gid (id de la pestaña) que trae el enlace, si lo trae."""
    m = re.search(
        r"[#?&]gid=(\d+)",
        str(url_google_sheet or ""),
    )
    return m.group(1) if m else ""


def _resolver_hoja_objetivo(url_google_sheet):
    """Traduce el gid del enlace al nombre real de la pestaña.

    Devuelve None si el enlace no trae gid: en ese caso se conserva el
    comportamiento anterior (todas las hojas).
    """
    gid = _extraer_gid(url_google_sheet)
    if not gid:
        raise ValueError(
            "El enlace de Google Sheets no identifica una pestaña concreta (falta gid). "
            "Abre la hoja que quieres procesar y copia el enlace desde esa pestaña. "
            "Auto Prizma no procesará todas las hojas como fallback."
        )

    spreadsheet_id = _extraer_spreadsheet_id(url_google_sheet)
    if not spreadsheet_id:
        return None

    credenciales = _cargar_credenciales_google()
    if credenciales is None:
        raise ValueError("Primero debes conectar tu cuenta de Google.")

    sheets = build(
        "sheets",
        "v4",
        credentials=credenciales,
        cache_discovery=False,
    )

    meta = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title)",
    ).execute()

    for item in meta.get("sheets", []):
        propiedades = item.get("properties", {}) or {}
        if str(propiedades.get("sheetId")) == gid:
            titulo = str(propiedades.get("title") or "").strip()
            if titulo:
                aviso = ""
                if len(titulo) > LIMITE_NOMBRE_HOJA_XLSX:
                    aviso = (
                        "  (en el XLSX llega recortada como '"
                        + titulo[:LIMITE_NOMBRE_HOJA_XLSX] + "')"
                    )
                print(
                    "Hoja objetivo: gid=" + gid + " -> '" + titulo + "'"
                    + aviso
                )
                return titulo

    raise ValueError(
        "El enlace apunta a una pestaña (gid=" + gid + ") que ya no existe "
        "en esa matriz. Abre la pestaña correcta y copia el enlace de nuevo."
    )


# Excel limita el nombre de una pestana a 31 caracteres. Cuando Google
# Sheets exporta a XLSX, cualquier pestana con un titulo mas largo llega
# RECORTADA. Por eso el nombre que devuelve la API de Sheets y el que trae
# el XLSX no siempre son iguales, y hay que compararlos por su recorte.
LIMITE_NOMBRE_HOJA_XLSX = 31


def _clave_hoja(nombre):
    """Identidad de una pestana, resistente al recorte del XLSX."""
    return normalizar_texto(
        str(nombre or "")[:LIMITE_NOMBRE_HOJA_XLSX]
    )


def _misma_hoja(nombre_hoja, hoja_objetivo):
    if not hoja_objetivo:
        return True

    if normalizar_texto(nombre_hoja) == normalizar_texto(hoja_objetivo):
        return True

    return _clave_hoja(nombre_hoja) == _clave_hoja(hoja_objetivo)


def _extraer_spreadsheet_id(url_google_sheet):
    m = re.search(
        r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)",
        str(url_google_sheet or ""),
        flags=re.IGNORECASE,
    )
    return m.group(1) if m else ""


def _url_desde_cell_data(celda):
    """Devuelve SOLO un enlace de Google Drive encontrado en la celda.

    La columna G puede contener Smart Chips, hipervinculos, formulas HYPERLINK
    o texto visible. No usamos enlaces de otras plataformas y, si la celda
    contiene varios links, priorizamos el primero que realmente sea Drive.
    """
    if not isinstance(celda, dict):
        return ""

    candidatos = []

    hyperlink = str(celda.get("hyperlink") or "").strip()
    if hyperlink:
        candidatos.append(hyperlink)

    for run in celda.get("chipRuns") or []:
        try:
            uri = str(
                run.get("chip", {})
                .get("richLinkProperties", {})
                .get("uri")
                or ""
            ).strip()
        except Exception:
            uri = ""
        if uri:
            candidatos.append(uri)

    valor = celda.get("userEnteredValue") or {}
    formula = str(valor.get("formulaValue") or "").strip()
    if formula:
        m = re.search(
            r'^\s*=\s*HYPERLINK\(\s*["\']([^"\']+)["\']',
            formula,
            flags=re.IGNORECASE,
        )
        if m:
            candidatos.append(m.group(1).strip())

    visible = str(celda.get("formattedValue") or "").strip()
    if visible.lower().startswith(("https://", "http://")):
        candidatos.append(visible)

    vistos = set()
    for url in candidatos:
        if not url or url in vistos:
            continue
        vistos.add(url)
        _, drive_id = _extraer_referencia_drive(url)
        if drive_id:
            return url

    return ""

def _leer_enlaces_columna_g_google_sheet(url_google_sheet, hoja_objetivo=None):
    """Lee SOLO enlaces Google Drive de la columna G (Enlaces).

    No usa valores de otras columnas para decidir que abrir en Drive. Tampoco
    descarga recursos: solamente recupera el link real de cada celda G,
    incluyendo Smart Chips.
    """
    spreadsheet_id = _extraer_spreadsheet_id(url_google_sheet)
    if not spreadsheet_id:
        raise ValueError("El enlace de Google Sheets no es valido.")

    credenciales = _cargar_credenciales_google()
    if credenciales is None:
        raise ValueError("Primero debes conectar tu cuenta de Google.")

    sheets = build(
        "sheets",
        "v4",
        credentials=credenciales,
        cache_discovery=False,
    )

    meta = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(title)",
    ).execute()

    titulos = [
        str(item.get("properties", {}).get("title") or "")
        for item in meta.get("sheets", [])
        if str(item.get("properties", {}).get("title") or "").strip()
    ]

    if hoja_objetivo:
        titulos = [
            titulo for titulo in titulos
            if _misma_hoja(titulo, hoja_objetivo)
        ]

    if not titulos:
        print(
            "AVISO: ninguna pestana coincidio con '"
            + str(hoja_objetivo or "")
            + "'. No se leyeron enlaces de la columna G."
        )
        return {}

    rangos = [
        "'" + titulo.replace("'", "''") + "'!G:G"
        for titulo in titulos
    ]

    respuesta = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=rangos,
        includeGridData=True,
        fields=(
            "sheets(properties(title),"
            "data(startRow,rowData(values("
            "formattedValue,hyperlink,chipRuns,userEnteredValue"
            "))))"
        ),
    ).execute()

    enlaces_drive = {}

    for hoja in respuesta.get("sheets", []):
        titulo = str(hoja.get("properties", {}).get("title") or "")
        for bloque in hoja.get("data", []) or []:
            inicio = int(bloque.get("startRow") or 0)
            filas = bloque.get("rowData") or []
            for offset, fila in enumerate(filas):
                valores = fila.get("values") or []
                if not valores:
                    continue
                url_drive = _url_desde_cell_data(valores[0])
                if url_drive:
                    # La clave usa el recorte porque las actividades vienen
                    # del XLSX, donde el nombre puede llegar cortado.
                    enlaces_drive[
                        (_clave_hoja(titulo), inicio + offset + 1)
                    ] = url_drive

    print(
        "Sheets SOLO ENLACES:",
        len(titulos),
        "hoja(s) |",
        len(enlaces_drive),
        "enlace(s) Google Drive encontrados exclusivamente en columna G",
    )

    return enlaces_drive

def _clave_cache_drive(drive_id):
    """Las caches de Drive son por usuario.

    Cada persona tiene su propio token de Google y por tanto sus propios
    permisos: lo que una alcanza a ver no puede reutilizarse para otra.
    """
    return _normalizar_usuario(_usuario_actual()) + "|" + str(drive_id or "")


def _cache_drive_obtener(carpeta_id):
    try:
        with motor_prizma_modulo._CACHE_CARPETAS_DRIVE_LOCK:
            valor = motor_prizma_modulo._CACHE_CARPETAS_DRIVE.get(
                _clave_cache_drive(carpeta_id)
            )
    except Exception:
        return None

    # Las entradas guardadas por la version anterior no traen "subcarpetas"
    # y solo contienen hijos directos. Se descartan para volver a leerlas
    # con el recorrido nuevo.
    if isinstance(valor, dict) and "subcarpetas" not in valor:
        return None

    return valor


def _cache_drive_guardar(carpeta_id, resultado):
    try:
        with motor_prizma_modulo._CACHE_CARPETAS_DRIVE_LOCK:
            motor_prizma_modulo._CACHE_CARPETAS_DRIVE[
                _clave_cache_drive(carpeta_id)
            ] = resultado
    except Exception:
        pass


MIME_CARPETA_DRIVE = "application/vnd.google-apps.folder"
MIME_ATAJO_DRIVE = "application/vnd.google-apps.shortcut"

# Profundidad maxima al recorrer una carpeta de Drive.
# 0 = solo hijos directos (comportamiento anterior).
DRIVE_PROFUNDIDAD_MAX = 3


def _resultado_carpeta_vacio():
    return {
        "ok": True,
        "error": None,
        "archivos": [],
        "detalles": [],
        "subcarpetas": 0,
        "ignorados": [],
    }


def _agregar_detalle_carpeta(resultado, item, mime_type=None):
    """Agrega un archivo real (con tamano) al resultado de la carpeta."""
    nombre = str(item.get("name") or "").strip()
    if not nombre:
        return

    mime_type = str(mime_type or item.get("mimeType") or "").strip()

    tamano = item.get("size")
    try:
        tamano = int(tamano) if tamano is not None else None
    except (TypeError, ValueError):
        tamano = None

    identificador = str(item.get("id") or "").strip()

    for existente in resultado["detalles"]:
        if identificador and existente.get("id") == identificador:
            return

    resultado["archivos"].append(nombre)
    resultado["detalles"].append({
        "id": identificador,
        "nombre": nombre,
        "mimeType": mime_type,
        "tamano": tamano,
    })


def _normalizar_respuesta_carpeta_drive(respuesta):
    """Compatibilidad: normaliza una respuesta simple de files().list."""
    resultado = _resultado_carpeta_vacio()

    for item in (respuesta or {}).get("files", []):
        mime_type = str(item.get("mimeType") or "").strip()

        if mime_type == MIME_CARPETA_DRIVE:
            resultado["subcarpetas"] += 1
            continue

        if mime_type == MIME_ATAJO_DRIVE:
            continue

        _agregar_detalle_carpeta(resultado, item, mime_type)

    return resultado


def _listar_carpetas_drive_en_lote(drive, carpetas_raiz):
    """Lista por lotes el contenido de varias carpetas de Drive.

    A diferencia de la version anterior:
      - entra en subcarpetas (hasta DRIVE_PROFUNDIDAD_MAX niveles);
      - resuelve atajos (shortcuts) a archivos y a carpetas;
      - respeta nextPageToken (carpetas con muchos elementos).

    Sigue pidiendo unicamente id, name, mimeType y size:
    NO descarga ni abre ningun H5P/PDF.
    """
    carpetas_raiz = [c for c in dict.fromkeys(carpetas_raiz) if c]
    resultados = {raiz: _resultado_carpeta_vacio() for raiz in carpetas_raiz}

    if not carpetas_raiz:
        return resultados

    visitadas = {raiz: {raiz} for raiz in carpetas_raiz}
    atajos_a_archivo = {}

    # tarea = (raiz, carpeta_id, page_token, profundidad)
    pendientes = [(raiz, raiz, None, 0) for raiz in carpetas_raiz]

    while pendientes:
        siguientes = []

        for inicio in range(0, len(pendientes), DRIVE_BATCH_MAX):
            grupo = pendientes[inicio:inicio + DRIVE_BATCH_MAX]
            respuestas = {}

            def callback_lista(request_id, response, exception):
                if exception is not None:
                    respuestas[str(request_id)] = ("error", exception)
                else:
                    respuestas[str(request_id)] = ("ok", response)

            batch = drive.new_batch_http_request(callback=callback_lista)

            for indice, (raiz, carpeta_id, token, profundidad) in enumerate(grupo):
                batch.add(
                    drive.files().list(
                        q="'" + carpeta_id + "' in parents and trashed = false",
                        spaces="drive",
                        fields=(
                            "nextPageToken,files(id,name,mimeType,size,"
                            "shortcutDetails(targetId,targetMimeType))"
                        ),
                        pageSize=1000,
                        pageToken=token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    ),
                    request_id=str(indice),
                )

            batch.execute()

            for indice, tarea in enumerate(grupo):
                raiz, carpeta_id, token, profundidad = tarea
                estado, payload = respuestas.get(str(indice), ("error", None))

                if estado == "error":
                    if carpeta_id == raiz and token is None:
                        resultados[raiz]["ok"] = False
                        resultados[raiz]["error"] = "ERROR_CARPETA_RECURSO_NO_ACCESIBLE"
                    else:
                        resultados[raiz]["ignorados"].append({
                            "nombre": carpeta_id,
                            "mimeType": MIME_CARPETA_DRIVE,
                            "motivo": "subcarpeta no accesible",
                        })
                    continue

                payload = payload or {}

                for item in payload.get("files", []) or []:
                    nombre = str(item.get("name") or "").strip()
                    mime_type = str(item.get("mimeType") or "").strip()

                    if not nombre:
                        continue

                    if mime_type == MIME_CARPETA_DRIVE:
                        resultados[raiz]["subcarpetas"] += 1
                        hijo = str(item.get("id") or "").strip()
                        if (
                            hijo
                            and profundidad + 1 <= DRIVE_PROFUNDIDAD_MAX
                            and hijo not in visitadas[raiz]
                        ):
                            visitadas[raiz].add(hijo)
                            siguientes.append((raiz, hijo, None, profundidad + 1))
                        continue

                    if mime_type == MIME_ATAJO_DRIVE:
                        detalle = item.get("shortcutDetails") or {}
                        target_id = str(detalle.get("targetId") or "").strip()
                        target_mime = str(detalle.get("targetMimeType") or "").strip()

                        if not target_id:
                            continue

                        if target_mime == MIME_CARPETA_DRIVE:
                            if (
                                profundidad + 1 <= DRIVE_PROFUNDIDAD_MAX
                                and target_id not in visitadas[raiz]
                            ):
                                visitadas[raiz].add(target_id)
                                siguientes.append(
                                    (raiz, target_id, None, profundidad + 1)
                                )
                        else:
                            atajos_a_archivo.setdefault(target_id, set()).add(raiz)
                        continue

                    if item.get("size") is None:
                        resultados[raiz]["ignorados"].append({
                            "nombre": nombre,
                            "mimeType": mime_type,
                            "motivo": "archivo nativo de Google (sin tamano)",
                        })
                        continue

                    _agregar_detalle_carpeta(resultados[raiz], item, mime_type)

                token_siguiente = str(payload.get("nextPageToken") or "").strip()
                if token_siguiente:
                    siguientes.append((raiz, carpeta_id, token_siguiente, profundidad))

        pendientes = siguientes

    # Resolver los atajos que apuntan a archivos reales.
    objetivos = list(atajos_a_archivo.keys())

    for inicio in range(0, len(objetivos), DRIVE_BATCH_MAX):
        grupo = objetivos[inicio:inicio + DRIVE_BATCH_MAX]
        respuestas = {}

        def callback_atajo(request_id, response, exception):
            respuestas[str(request_id)] = None if exception is not None else response

        batch = drive.new_batch_http_request(callback=callback_atajo)

        for target_id in grupo:
            batch.add(
                drive.files().get(
                    fileId=target_id,
                    fields="id,name,mimeType,size",
                    supportsAllDrives=True,
                ),
                request_id=target_id,
            )

        batch.execute()

        for target_id in grupo:
            item = respuestas.get(target_id)
            if not item:
                continue
            for raiz in atajos_a_archivo.get(target_id, set()):
                if item.get("size") is None:
                    resultados[raiz]["ignorados"].append({
                        "nombre": str(item.get("name") or ""),
                        "mimeType": str(item.get("mimeType") or ""),
                        "motivo": "atajo a archivo sin tamano",
                    })
                    continue
                _agregar_detalle_carpeta(resultados[raiz], item)

    return resultados


def _listar_archivos_carpeta_drive_oauth(url_carpeta):
    """Fallback individual. Normalmente el preflight ya deja todo en cache."""

    carpeta_id = motor_prizma_modulo.extraer_id_carpeta_drive(url_carpeta)

    if not carpeta_id:
        return {
            "ok": False,
            "error": "ERROR_CARPETA_RECURSO_NO_ACCESIBLE",
            "archivos": [],
            "detalles": [],
        }

    cache = _cache_drive_obtener(carpeta_id)
    if cache is not None:
        return cache

    credenciales = _cargar_credenciales_google()
    if credenciales is None:
        return {
            "ok": False,
            "error": "ERROR_GOOGLE_NO_CONECTADO",
            "archivos": [],
            "detalles": [],
        }

    try:
        drive = build(
            "drive",
            "v3",
            credentials=credenciales,
            cache_discovery=False,
        )

        respuesta = drive.files().list(
            q=f"'{carpeta_id}' in parents and trashed = false",
            spaces="drive",
            fields="files(id,name,mimeType,size)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        resultado = _normalizar_respuesta_carpeta_drive(respuesta)
        _cache_drive_guardar(carpeta_id, resultado)
        return resultado

    except Exception as error:
        print(
            "Drive API - error carpeta:",
            carpeta_id,
            type(error).__name__,
            str(error),
        )
        return {
            "ok": False,
            "error": "ERROR_CARPETA_RECURSO_NO_ACCESIBLE",
            "archivos": [],
            "detalles": [],
        }


def _precargar_referencias_drive_batch(actividades):
    """Precarga Drive rapido usando el tipo REAL del recurso, no solo la forma de la URL.

    Algunos Smart Chips usan enlaces tipo open?id=... incluso cuando apuntan a una
    carpeta. Primero consultamos metadatos de esas referencias ambiguas y solo despues
    decidimos si son carpeta o archivo. No se descarga ningun H5P/PDF.
    """

    carpetas_url = {}
    referencias_ambiguas = {}

    for actividad in actividades or []:
        url = str(actividad.get("_url_drive_sheet") or "").strip()
        tipo_ref, drive_id = _extraer_referencia_drive(url)
        if not drive_id:
            continue
        if tipo_ref == "folder":
            carpetas_url.setdefault(drive_id, url)
            with _CACHE_REFERENCIAS_DRIVE_LOCK:
                _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                    "tipo": "folder",
                    "target_id": drive_id,
                }
        else:
            referencias_ambiguas.setdefault(drive_id, url)

    credenciales = _cargar_credenciales_google()
    if credenciales is None:
        raise ValueError(
            "Primero debes conectar tu cuenta de Google antes de analizar la matriz."
        )

    drive = build(
        "drive",
        "v3",
        credentials=credenciales,
        cache_discovery=False,
    )

    # --------------------------------------------------------
    # 1) Resolver referencias ambiguas por SU MIMETYPE REAL.
    #    open?id=... puede ser archivo o carpeta.
    # --------------------------------------------------------
    ambiguas_pendientes = []
    with _CACHE_REFERENCIAS_DRIVE_LOCK:
        for drive_id in referencias_ambiguas:
            if _clave_cache_drive(drive_id) not in _CACHE_REFERENCIAS_DRIVE:
                ambiguas_pendientes.append(drive_id)

    metadatos_ambiguos = {}

    for inicio in range(0, len(ambiguas_pendientes), DRIVE_BATCH_MAX):
        grupo = ambiguas_pendientes[inicio:inicio + DRIVE_BATCH_MAX]
        respuestas = {}

        def callback_meta(request_id, response, exception):
            respuestas[str(request_id)] = None if exception is not None else response

        batch = drive.new_batch_http_request(callback=callback_meta)
        for drive_id in grupo:
            batch.add(
                drive.files().get(
                    fileId=drive_id,
                    fields="id,name,mimeType,size,shortcutDetails(targetId,targetMimeType)",
                    supportsAllDrives=True,
                ),
                request_id=drive_id,
            )
        batch.execute()

        for drive_id in grupo:
            metadatos_ambiguos[drive_id] = respuestas.get(drive_id)

    # Resolver shortcuts a archivos reales solo cuando existan.
    shortcut_archivos = {}
    for original_id, item in metadatos_ambiguos.items():
        if not item:
            continue
        mime_type = str(item.get("mimeType") or "")
        if mime_type == "application/vnd.google-apps.shortcut":
            detalle = item.get("shortcutDetails") or {}
            target_id = str(detalle.get("targetId") or "").strip()
            target_mime = str(detalle.get("targetMimeType") or "").strip()
            if target_id and target_mime != "application/vnd.google-apps.folder":
                shortcut_archivos[original_id] = target_id

    metadatos_targets = {}
    targets_unicos = list(dict.fromkeys(shortcut_archivos.values()))
    for inicio in range(0, len(targets_unicos), DRIVE_BATCH_MAX):
        grupo = targets_unicos[inicio:inicio + DRIVE_BATCH_MAX]
        respuestas = {}

        def callback_target(request_id, response, exception):
            respuestas[str(request_id)] = None if exception is not None else response

        batch = drive.new_batch_http_request(callback=callback_target)
        for target_id in grupo:
            batch.add(
                drive.files().get(
                    fileId=target_id,
                    fields="id,name,mimeType,size",
                    supportsAllDrives=True,
                ),
                request_id=target_id,
            )
        batch.execute()
        metadatos_targets.update(respuestas)

    carpetas_reales = dict(carpetas_url)
    archivos_reales = 0
    carpetas_detectadas_desde_enlace_archivo = 0
    shortcuts_detectados = 0

    with _CACHE_REFERENCIAS_DRIVE_LOCK, _CACHE_ARCHIVOS_DRIVE_LOCK:
        for drive_id in referencias_ambiguas:
            item = metadatos_ambiguos.get(drive_id)

            if not item:
                _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                    "tipo": "error",
                    "target_id": drive_id,
                }
                _CACHE_ARCHIVOS_DRIVE[_clave_cache_drive(drive_id)] = None
                continue

            mime_type = str(item.get("mimeType") or "").strip()
            target_id = drive_id

            if mime_type == "application/vnd.google-apps.shortcut":
                shortcuts_detectados += 1
                detalle = item.get("shortcutDetails") or {}
                target_id = str(detalle.get("targetId") or "").strip()
                target_mime = str(detalle.get("targetMimeType") or "").strip()

                if target_id and target_mime == "application/vnd.google-apps.folder":
                    carpetas_reales.setdefault(target_id, referencias_ambiguas[drive_id])
                    _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                        "tipo": "folder",
                        "target_id": target_id,
                    }
                    carpetas_detectadas_desde_enlace_archivo += 1
                    continue

                item = metadatos_targets.get(target_id)
                if not item:
                    _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                        "tipo": "error",
                        "target_id": target_id or drive_id,
                    }
                    _CACHE_ARCHIVOS_DRIVE[_clave_cache_drive(drive_id)] = None
                    continue
                mime_type = str(item.get("mimeType") or "").strip()

            if mime_type == "application/vnd.google-apps.folder":
                carpetas_reales.setdefault(target_id, referencias_ambiguas[drive_id])
                _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                    "tipo": "folder",
                    "target_id": target_id,
                }
                carpetas_detectadas_desde_enlace_archivo += 1
                continue

            tamano = item.get("size")
            try:
                tamano = int(tamano) if tamano is not None else None
            except (TypeError, ValueError):
                tamano = None

            archivo = {
                "id": str(item.get("id") or target_id or drive_id).strip(),
                "nombre": str(item.get("name") or "").strip(),
                "mimeType": mime_type,
                "tamano": tamano,
            }

            _CACHE_ARCHIVOS_DRIVE[_clave_cache_drive(drive_id)] = archivo
            _CACHE_REFERENCIAS_DRIVE[_clave_cache_drive(drive_id)] = {
                "tipo": "file",
                "target_id": archivo["id"],
                "item": archivo,
            }
            archivos_reales += 1

    # --------------------------------------------------------
    # 2) Listar hijos SOLO de las referencias que son carpetas
    #    reales. Ahora tambien se entra en subcarpetas y atajos,
    #    pero seguimos pidiendo unicamente nombre + tamano.
    # --------------------------------------------------------
    carpetas_pendientes = [
        drive_id for drive_id in carpetas_reales
        if _cache_drive_obtener(drive_id) is None
    ]

    carpetas_con_subcarpetas = 0
    carpetas_vacias = 0

    if carpetas_pendientes:
        resultados_carpetas = _listar_carpetas_drive_en_lote(
            drive,
            carpetas_pendientes,
        )

        for carpeta_id in carpetas_pendientes:
            resultado = resultados_carpetas.get(carpeta_id)

            if not resultado:
                resultado = {
                    "ok": False,
                    "error": "ERROR_CARPETA_RECURSO_NO_ACCESIBLE",
                    "archivos": [],
                    "detalles": [],
                    "subcarpetas": 0,
                    "ignorados": [],
                }

            if resultado.get("subcarpetas"):
                carpetas_con_subcarpetas += 1

            if resultado.get("ok") and not resultado.get("detalles"):
                carpetas_vacias += 1

            _cache_drive_guardar(carpeta_id, resultado)

    print(
        "Drive rapido tipo-real:",
        len(carpetas_url),
        "carpeta(s) por URL +",
        len(referencias_ambiguas),
        "referencia(s) ambigua(s) |",
        carpetas_detectadas_desde_enlace_archivo,
        "eran carpeta(s) |",
        archivos_reales,
        "eran archivo(s) |",
        shortcuts_detectados,
        "shortcut(s) | solo nombre + tamano",
    )

    print(
        "Drive estructura:",
        len(carpetas_pendientes),
        "carpeta(s) leida(s) |",
        carpetas_con_subcarpetas,
        "con subcarpetas (se recorrieron hasta",
        DRIVE_PROFUNDIDAD_MAX,
        "nivel(es)) |",
        carpetas_vacias,
        "sin ningun archivo con tamano",
    )

    return {
        "total_carpetas": len(carpetas_reales),
        "total_archivos_directos": archivos_reales,
        "consultadas_google": len(ambiguas_pendientes) + len(carpetas_pendientes) + len(targets_unicos),
    }
