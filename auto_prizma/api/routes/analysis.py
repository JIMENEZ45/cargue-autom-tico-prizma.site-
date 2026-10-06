"""Pagina de inicio y analisis de la matriz y los recursos antes del cargue.
"""

from fastapi import (
    UploadFile,
    File,
    Form,
    Request as FastAPIRequest,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)
import zipfile
import os
import uuid
import shutil

from auto_prizma.core.application import app
from auto_prizma.core.config import (
    RESULTADOS_DIR,
    TEMP_DIR,
    UPLOADS_DIR,
)
from auto_prizma.services.auth import _usuario_actual
from auto_prizma.integrations.google.drive import _resolver_hoja_objetivo
from auto_prizma.services.drive_zip_validation import _prevalidar_recursos_drive_zip_ultrarapido
from auto_prizma.services.upload_jobs import (
    TRABAJOS,
    _ahora_colombia_iso,
    _cursos_desde_hojas,
    _nombre_reporte,
)
from auto_prizma.services.matrix_analysis import (
    _normalizar_contenido_matriz_archivo,
    _parsear_datos_academicos,
    _validar_origen_matriz,
    analizar_excel,
    analizar_zip,
    descargar_google_sheet_xlsx,
)
from auto_prizma.web.views import generar_html


# ============================================================
# INICIO
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def inicio():

    return generar_html()


# ============================================================
# ANALIZAR
# ============================================================

@app.post(
    "/analizar",
    response_class=HTMLResponse,
)
async def analizar(
    request: FastAPIRequest,
    recursos: UploadFile | None = File(default=None),
    modo_matriz: str = Form(default="link"),
    google_sheet_url: str | None = Form(default=None),
    matriz_archivo: UploadFile | None = File(default=None),
    ovi: str | None = Form(default=None),
    ova: str | None = Form(default=None),
    retos: str | None = Form(default=None),
    test_evaluativo: str | None = Form(default=None),
    test_archivo_docx: UploadFile | None = File(default=None),
    test_google_doc_url: str | None = Form(default=None),
    modo_test: str = Form(default="archivo"),
    test_datos_academicos: str | None = Form(default=None),
    test_semestre: str | None = Form(default=None),
):

    try:
        procesar_ovi = ovi is not None
        procesar_ova = ova is not None
        procesar_retos = retos is not None
        procesar_test = test_evaluativo is not None
        procesar_recursos = procesar_ovi or procesar_ova or procesar_retos

        if not procesar_recursos and not procesar_test:
            return generar_html(
                error="Selecciona al menos una categoría: OVI, OVA, Retos Evaluativos o Test Evaluativo."
            )

        test_job_id = None
        nom_test = ""
        document_test = None
        if procesar_test:
            datos_acad = _parsear_datos_academicos(test_datos_academicos)
            if not datos_acad:
                return generar_html(
                    error="Debes ingresar los datos académicos en el formato: CódigoPrograma CódigoPensum CódigoAsignatura NombreAsignatura"
                )
            semestre_val = str(test_semestre or "").strip()
            if not semestre_val:
                return generar_html(
                    error="Debes seleccionar el semestre para el test evaluativo."
                )

            from auto_prizma.evaluative_tests.routes import _extraer_bytes_docx_request
            from auto_prizma.evaluative_tests.state import _JOBS, _JOBS_LOCK
            from auto_prizma.evaluative_tests.parser import parse_docx_bytes

            content_test, nom_test, err_test = await _extraer_bytes_docx_request(
                request, test_archivo_docx, test_google_doc_url, modo_test
            )
            if err_test or not content_test:
                return generar_html(error=err_test or "El documento de test está vacío.")

            try:
                document_test = parse_docx_bytes(content_test, source_name=nom_test)
            except Exception as exc_p:
                return generar_html(error=f"Error al procesar documento de test: {exc_p}")

            test_job_id = uuid.uuid4().hex
            with _JOBS_LOCK:
                _JOBS[test_job_id] = {
                    "owner": _usuario_actual(),
                    "document": document_test,
                    "created_at": _ahora_colombia_iso(),
                    "cascada_datos": {
                        "programa": datos_acad["programa"],
                        "pensum": datos_acad["pensum"],
                        "nivel": semestre_val,
                        "asignatura": datos_acad["asignatura"],
                        "codigo_asignatura": datos_acad["codigo_asignatura"],
                    },
                }

            if not procesar_recursos:
                return RedirectResponse(f"/tests/{test_job_id}/revision", status_code=303)

        nombre_archivo_matriz = (
            str(getattr(matriz_archivo, "filename", "") or "").strip()
            if matriz_archivo is not None
            else ""
        )
        modo_matriz = str(modo_matriz or "").strip().lower()

        origen_ok, error_origen = _validar_origen_matriz(
            modo_matriz,
            google_sheet_url,
            nombre_archivo_matriz,
        )
        if not origen_ok:
            return generar_html(error=error_origen)

        if not recursos or not str(recursos.filename or "").lower().endswith(".zip"):
            return generar_html(
                error="Los recursos deben estar en un archivo .zip"
            )

        if modo_matriz == "link":
            google_sheet_url = str(google_sheet_url or "").strip()
            contenido_excel = descargar_google_sheet_xlsx(
                google_sheet_url
            )
            # Solo se procesa la pestaña que viene en el enlace (#gid=...).
            hoja_objetivo = _resolver_hoja_objetivo(google_sheet_url)
            nombre_matriz = hoja_objetivo or "Google Sheets"
        else:
            contenido_original = await matriz_archivo.read()
            contenido_excel, nombre_matriz = _normalizar_contenido_matriz_archivo(
                nombre_archivo_matriz,
                contenido_original,
            )
            hoja_objetivo = None

        contenido_zip = await recursos.read()

        hojas = analizar_excel(
            contenido_excel,
            procesar_ovi,
            procesar_ova,
            procesar_retos,
            hoja_objetivo,
        )

        if not hojas:
            if modo_matriz == "link" and hoja_objetivo:
                return generar_html(
                    error=(
                        "La pestaña \"" + hoja_objetivo + "\" no tiene una "
                        "matriz PRIZMA válida (no encontré la fila de "
                        "encabezado \"Semana correspondiente\"). "
                        "Abre la pestaña correcta y copia el enlace otra vez."
                    )
                )

            return generar_html(
                error="No encontré una matriz PRIZMA válida."
            )

        try:
            zip_info = analizar_zip(contenido_zip)
        except zipfile.BadZipFile:
            return generar_html(error="El ZIP no es válido.")

        # ====================================================
        # CREAR TRABAJO
        # ====================================================

        trabajo_id = uuid.uuid4().hex
        carpeta_trabajo = os.path.join(UPLOADS_DIR, trabajo_id)
        os.makedirs(carpeta_trabajo, exist_ok=True)

        ruta_excel = os.path.join(carpeta_trabajo, "matriz.xlsx")
        ruta_zip = os.path.join(carpeta_trabajo, "recursos.zip")

        with open(ruta_excel, "wb") as archivo:
            archivo.write(contenido_excel)

        with open(ruta_zip, "wb") as archivo:
            archivo.write(contenido_zip)

        carpeta_temp = os.path.join(TEMP_DIR, trabajo_id)
        os.makedirs(carpeta_temp, exist_ok=True)

        if modo_matriz == "link":
            preflight_drive = _prevalidar_recursos_drive_zip_ultrarapido(
                google_sheet_url,
                ruta_excel,
                ruta_zip,
                procesar_ovi,
                procesar_ova,
                procesar_retos,
                hoja_objetivo,
            )

            recursos_drive_resueltos = preflight_drive.pop(
                "_mapa_resueltos",
                {},
            )

            if not preflight_drive.get("ok"):
                errores_drive = preflight_drive.get("errores") or []
                resumen_errores = " | ".join(errores_drive[:8])

                if len(errores_drive) > 8:
                    resumen_errores += (
                        " | ... y "
                        + str(len(errores_drive) - 8)
                        + " error(es) más."
                    )

                shutil.rmtree(carpeta_trabajo, ignore_errors=True)
                shutil.rmtree(carpeta_temp, ignore_errors=True)

                return generar_html(
                    error=(
                        "La validación Google Drive vs ZIP encontró problemas. "
                        + resumen_errores
                    )
                )
        else:
            # En modo archivo no se consulta Google. El motor conserva su
            # resolvedor seguro de recursos del ZIP y nunca elige ambiguos.
            recursos_drive_resueltos = {}
            preflight_drive = {
                "ok": True,
                "modo": "archivo",
                "total_actividades": sum(
                    len(hoja.get("actividades") or []) for hoja in hojas
                ),
                "validadas_drive": 0,
                "coincidencias_zip": 0,
                "errores": [],
                "advertencias": [],
                "recursos": [],
            }

        cursos_trabajo = _cursos_desde_hojas(hojas)
        ruta_reporte = os.path.join(
            RESULTADOS_DIR,
            _nombre_reporte(cursos_trabajo, trabajo_id),
        )

        TRABAJOS[trabajo_id] = {
            "id": trabajo_id,
            "ruta_excel": ruta_excel,
            "ruta_zip": ruta_zip,
            "carpeta_temp": carpeta_temp,
            "ruta_reporte": ruta_reporte,
            "procesar_ovi": procesar_ovi,
            "procesar_ova": procesar_ova,
            "procesar_retos": procesar_retos,
            "etapa": "analizado",
            "mensaje": "Archivos analizados correctamente.",
            "total": 0,
            "procesadas": 0,
            "exitosas": 0,
            "errores": 0,
            "terminado": False,
            "detalle_actividades": [],
            "recursos_drive_resueltos": recursos_drive_resueltos,
            "hoja_objetivo": hoja_objetivo,
            "origen_matriz": modo_matriz,
            "nombre_matriz": nombre_matriz,
            "usuario_app": _usuario_actual(),
            "cursos": cursos_trabajo,
            "historial_registrado": False,
            "creado_en": _ahora_colombia_iso(),
            "cancelar_solicitado": False,
        }

        resultado = {
            "hojas": hojas,
            "zip": zip_info,
            "drive": preflight_drive,
            "origen_matriz": modo_matriz,
            "nombre_matriz": nombre_matriz,
        }

        if procesar_test and test_job_id and document_test:
            resultado["test_info"] = {
                "test_job_id": test_job_id,
                "nombre_documento": nom_test,
                "cantidad_tests": len(document_test.tests),
                "cantidad_preguntas": sum(len(sec.questions) for t in document_test.tests for sec in t.sections),
            }
            TRABAJOS[trabajo_id]["test_job_id"] = test_job_id

        TRABAJOS[trabajo_id]["resultado_analisis"] = resultado

        return generar_html(
            resultado=resultado,
            trabajo_id=trabajo_id,
        )

    except Exception as e:
        return generar_html(error=str(e))
