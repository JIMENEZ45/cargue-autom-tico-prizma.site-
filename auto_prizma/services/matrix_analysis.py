"""Lectura de la matriz (CSV, Excel o Google Sheets) y analisis de la matriz y del ZIP.
"""

from io import BytesIO
from openpyxl import (
    load_workbook,
    Workbook,
)
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from auto_prizma.automation.prizma.engine import (
    determinar_tipo_archivo,
    normalizar_categoria,
    normalizar_texto,
)
import zipfile
import csv
import os
import re

from auto_prizma.core.config import EXTENSIONES_HTML, GOOGLE_SHEETS_MAX_BYTES
from auto_prizma.integrations.google.oauth import _cargar_credenciales_google
from auto_prizma.integrations.google.drive import _misma_hoja


# ============================================================
# CONVERTIR CSV A XLSX INTERNO
# ============================================================

def _validar_origen_matriz(modo, google_sheet_url=None, nombre_archivo=None):
    """Valida que la matriz provenga de una sola fuente: link o archivo."""
    modo = str(modo or "").strip().lower()
    tiene_link = bool(str(google_sheet_url or "").strip())
    tiene_archivo = bool(str(nombre_archivo or "").strip())

    if modo not in {"link", "archivo"}:
        return False, "Selecciona si cargarás la matriz por link o por archivo."

    if tiene_link and tiene_archivo:
        return False, "Usa una sola fuente de matriz: por link o por archivo."

    if modo == "link":
        if not tiene_link:
            return False, "Pega el enlace de Google Sheets."
        if tiene_archivo:
            return False, "Usa una sola fuente de matriz: por link o por archivo."
        return True, ""

    if not tiene_archivo:
        return False, "Selecciona un archivo XLSX o CSV."
    if tiene_link:
        return False, "Usa una sola fuente de matriz: por link o por archivo."
    return True, ""


def _parsear_datos_academicos(texto: str) -> dict | None:
    """Parsea el campo único de datos académicos:
    'codigo_programa - codigo_pensum - codigo_asignatura - nombre_asignatura'
    Soporta separadores por espacios, guiones o combinaciones.
    Los primeros 3 tokens corresponden a los códigos y el resto al nombre de la asignatura.
    """
    texto = (texto or "").strip()
    if not texto:
        return None

    # Primero intentar separar por guiones explícitos (' - ' o '-')
    partes_guion = [p.strip() for p in re.split(r"\s*[-–—]\s*", texto) if p.strip()]
    if len(partes_guion) >= 4:
        return {
            "programa": partes_guion[0],
            "pensum": partes_guion[1],
            "codigo_asignatura": partes_guion[2],
            "asignatura": " - ".join(partes_guion[3:]),
        }

    # Separación por espacios
    tokens = texto.split()
    if len(tokens) >= 4:
        return {
            "programa": tokens[0],
            "pensum": tokens[1],
            "codigo_asignatura": tokens[2],
            "asignatura": " ".join(tokens[3:]),
        }

    return None



def _extension_matriz_archivo(nombre_archivo):
    extension = os.path.splitext(str(nombre_archivo or ""))[1].lower()
    if extension not in {".xlsx", ".csv"}:
        raise ValueError("La matriz local debe ser un archivo .xlsx o .csv.")
    return extension


def convertir_csv_a_xlsx(
    contenido_csv,
):

    texto = None

    for codificacion in [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]:

        try:

            texto = contenido_csv.decode(
                codificacion
            )

            break

        except UnicodeDecodeError:
            continue

    if texto is None:
        raise ValueError(
            "No fue posible leer el archivo CSV."
        )

    muestra = texto[:10000]

    try:

        dialecto = csv.Sniffer().sniff(
            muestra,
            delimiters=",;\t|",
        )

        delimitador = dialecto.delimiter

    except csv.Error:

        delimitador = ","

    filas = list(
        csv.reader(
            texto.splitlines(),
            delimiter=delimitador,
        )
    )

    if not filas:
        raise ValueError(
            "El archivo CSV está vacío."
        )

    libro = Workbook()

    hoja = libro.active
    hoja.title = "Matriz"

    for numero_fila, fila in enumerate(
        filas,
        start=1,
    ):

        for numero_columna, valor in enumerate(
            fila,
            start=1,
        ):

            hoja.cell(
                row=numero_fila,
                column=numero_columna,
                value=valor,
            )

    salida = BytesIO()
    libro.save(salida)

    return salida.getvalue()


def _normalizar_contenido_matriz_archivo(nombre_archivo, contenido):
    nombre_visible = os.path.basename(str(nombre_archivo or "").strip())
    extension = _extension_matriz_archivo(nombre_visible)
    if not contenido:
        raise ValueError("La matriz local está vacía.")

    if extension == ".csv":
        contenido_xlsx = convertir_csv_a_xlsx(contenido)
    else:
        contenido_xlsx = bytes(contenido)
        try:
            libro_prueba = load_workbook(
                BytesIO(contenido_xlsx),
                read_only=True,
                data_only=False,
            )
            libro_prueba.close()
        except Exception as error:
            raise ValueError("El archivo XLSX no es válido.") from error

    return contenido_xlsx, nombre_visible


# ============================================================
# DESCARGAR MATRIZ DESDE GOOGLE SHEETS
# ============================================================

# GOOGLE_SHEETS_MAX_BYTES vive en auto_prizma.core.config.


def descargar_google_sheet_xlsx(url_google_sheet):
    """Exporta un Google Sheet privado a XLSX usando la cuenta OAuth conectada."""

    url_google_sheet = str(url_google_sheet or "").strip()

    coincidencia = re.search(
        r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)",
        url_google_sheet,
        flags=re.IGNORECASE,
    )

    if not coincidencia:
        raise ValueError(
            "El enlace de Google Sheets no es válido. Copia el enlace completo de la matriz."
        )

    credenciales = _cargar_credenciales_google()

    if credenciales is None:
        raise ValueError(
            "Primero debes conectar tu cuenta de Google antes de analizar una matriz privada."
        )

    spreadsheet_id = coincidencia.group(1)

    try:
        drive = build(
            "drive",
            "v3",
            credentials=credenciales,
            cache_discovery=False,
        )

        metadata = drive.files().get(
            fileId=spreadsheet_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()

        mime_type = str(metadata.get("mimeType") or "")

        if mime_type != "application/vnd.google-apps.spreadsheet":
            raise ValueError(
                "El enlace no corresponde a una hoja nativa de Google Sheets."
            )

        salida = BytesIO()

        solicitud = drive.files().export_media(
            fileId=spreadsheet_id,
            mimeType=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

        descargador = MediaIoBaseDownload(
            salida,
            solicitud,
            chunksize=1024 * 1024,
        )

        terminado = False

        while not terminado:
            _, terminado = descargador.next_chunk()

            if salida.tell() > GOOGLE_SHEETS_MAX_BYTES:
                raise ValueError(
                    "La matriz de Google Sheets supera el tamaño máximo permitido."
                )

        contenido = salida.getvalue()

    except ValueError:
        raise

    except HttpError as error:
        estado = getattr(getattr(error, "resp", None), "status", None)

        if estado in (401, 403):
            mensaje = (
                "La cuenta de Google conectada no tiene permiso para leer esta matriz. "
                "Verifica que puedas abrirla con esa misma cuenta."
            )
        elif estado == 404:
            mensaje = (
                "Google Drive no encontró la matriz o la cuenta conectada no tiene acceso."
            )
        else:
            mensaje = (
                "Google Drive no pudo exportar la matriz. "
                f"Código HTTP: {estado or 'desconocido'}."
            )

        raise ValueError(mensaje) from error

    except Exception as error:
        raise ValueError(
            "No fue posible descargar la matriz mediante la cuenta de Google conectada."
        ) from error

    if not contenido:
        raise ValueError(
            "Google Drive devolvió una matriz vacía."
        )

    if not contenido.startswith(b"PK"):
        raise ValueError(
            "Google Drive no devolvió un archivo Excel válido."
        )

    try:
        libro_prueba = load_workbook(
            BytesIO(contenido),
            read_only=True,
            data_only=False,
        )
        libro_prueba.close()
    except Exception as error:
        raise ValueError(
            "La matriz descargada desde Google Sheets no pudo leerse como XLSX."
        ) from error

    return contenido


# ============================================================
# ANALIZAR MATRIZ
# ============================================================

def analizar_excel(
    contenido_excel,
    procesar_ovi=True,
    procesar_ova=True,
    procesar_retos=True,
    hoja_objetivo=None,
    formato_recurso="H5P",
):
    # formato_recurso: "H5P" o "HTML". En modo HTML las actividades de
    # recurso interactivo (H5P) se muestran y cuentan como HTML.
    modo_html = str(formato_recurso or "").strip().upper() == "HTML"

    libro = load_workbook(
        BytesIO(contenido_excel),
        data_only=True,
    )

    hojas_validas = []

    for nombre_hoja in libro.sheetnames:

        if not _misma_hoja(nombre_hoja, hoja_objetivo):
            continue

        hoja = libro[
            nombre_hoja
        ]

        fila_cabecera = None

        for fila in range(
            1,
            min(
                hoja.max_row,
                30,
            ) + 1,
        ):

            valor = hoja.cell(
                row=fila,
                column=1,
            ).value

            if normalizar_texto(
                valor
            ) == normalizar_texto(
                "Semana correspondiente"
            ):

                fila_cabecera = fila
                break

        if fila_cabecera is None:
            continue

        programa = hoja.cell(
            row=1,
            column=1,
        ).value

        curso = hoja.cell(
            row=2,
            column=1,
        ).value

        actividades = []

        cantidad_ovi = 0
        cantidad_ova = 0
        cantidad_retos = 0
        cantidad_h5p = 0
        cantidad_pdf = 0
        cantidad_html = 0

        for fila in range(
            fila_cabecera + 1,
            hoja.max_row + 1,
        ):

            semana = hoja.cell(
                row=fila,
                column=1,
            ).value

            unidad = hoja.cell(
                row=fila,
                column=2,
            ).value

            nombre = hoja.cell(
                row=fila,
                column=4,
            ).value

            categoria = hoja.cell(
                row=fila,
                column=5,
            ).value

            tipo_recurso = hoja.cell(
                row=fila,
                column=6,
            ).value

            enlace = hoja.cell(
                row=fila,
                column=7,
            ).value

            if not nombre:
                continue

            if not categoria:
                continue

            categoria_prizma = normalizar_categoria(
                categoria
            )

            if categoria_prizma not in [
                "OVI",
                "OVA",
                "CHALLENGE",
            ]:
                continue

            if (
                categoria_prizma == "OVI"
                and not procesar_ovi
            ):
                continue

            if (
                categoria_prizma == "OVA"
                and not procesar_ova
            ):
                continue

            if (
                categoria_prizma == "CHALLENGE"
                and not procesar_retos
            ):
                continue

            tipo_archivo = determinar_tipo_archivo(
                categoria,
                tipo_recurso,
                enlace,
            )

            if tipo_archivo is None:
                continue

            if modo_html and tipo_archivo == "H5P":
                tipo_archivo = "HTML"

            if categoria_prizma == "OVI":
                cantidad_ovi += 1

            if categoria_prizma == "OVA":
                cantidad_ova += 1

            if categoria_prizma == "CHALLENGE":
                cantidad_retos += 1

            if tipo_archivo == "H5P":
                cantidad_h5p += 1

            if tipo_archivo == "PDF":
                cantidad_pdf += 1

            if tipo_archivo == "HTML":
                cantidad_html += 1

            actividades.append(
                {
                    "fila": fila,

                    "semana": (
                        str(semana).strip()
                        if semana
                        else ""
                    ),

                    "unidad": (
                        str(unidad).strip()
                        if unidad
                        else ""
                    ),

                    "nombre": str(
                        nombre
                    ).strip(),

                    "categoria":
                        categoria_prizma,

                    "tipo":
                        tipo_archivo,

                    "tipo_recurso": (
                        str(tipo_recurso).strip()
                        if tipo_recurso
                        else tipo_archivo
                    ),
                }
            )

        hojas_validas.append(
            {
                "hoja":
                    nombre_hoja,

                "programa": (
                    str(programa).strip()
                    if programa
                    else ""
                ),

                "curso": (
                    str(curso).strip()
                    if curso
                    else nombre_hoja
                ),

                "actividades":
                    actividades,

                "ovi":
                    cantidad_ovi,

                "ova":
                    cantidad_ova,

                "retos":
                    cantidad_retos,

                "h5p":
                    cantidad_h5p,

                "pdf":
                    cantidad_pdf,

                "html":
                    cantidad_html,
            }
        )

    return hojas_validas


# ============================================================
# ANALIZAR ZIP
# ============================================================

def analizar_zip(
    contenido_zip,
    formato_recurso="H5P",
):
    # El total cuenta los archivos que se usaran en el cargue: H5P o HTML
    # (segun el formato elegido) mas los PDF.
    modo_html = str(formato_recurso or "").strip().upper() == "HTML"

    cantidad_h5p = 0
    cantidad_pdf = 0
    cantidad_html = 0

    with zipfile.ZipFile(
        BytesIO(contenido_zip),
        "r",
    ) as archivo_zip:

        for miembro in archivo_zip.namelist():

            if miembro.endswith("/"):
                continue

            nombre = os.path.basename(
                miembro
            )

            extension = os.path.splitext(
                nombre
            )[1].lower()

            if extension == ".h5p":

                cantidad_h5p += 1

            elif extension == ".pdf":

                cantidad_pdf += 1

            elif extension in EXTENSIONES_HTML:

                cantidad_html += 1

    return {
        "h5p":
            cantidad_h5p,

        "pdf":
            cantidad_pdf,

        "html":
            cantidad_html,

        "total":
            (cantidad_html if modo_html else cantidad_h5p)
            + cantidad_pdf,
    }
