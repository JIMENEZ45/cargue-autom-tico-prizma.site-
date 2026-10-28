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

from auto_prizma.core.application import app
from auto_prizma.core.clock import _ahora_colombia_iso
from auto_prizma.core.config import FORMATOS_RECURSO_INTERACTIVO, TEMP_DIR
from auto_prizma.services.auth import _usuario_actual
from auto_prizma.services.course_state import preseleccion_faltantes
from auto_prizma.integrations.google.drive import _resolver_hoja_objetivo
from auto_prizma.services.upload_jobs import create_analyzed_job
from auto_prizma.services.h5p_preview import preview_h5p_titles
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
    formato_recurso: str = Form(default="H5P"),
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
            from auto_prizma.evaluative_tests.state import register_test_job
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

            test_job_id = register_test_job(
                _usuario_actual(),
                document_test,
                _ahora_colombia_iso(),
                cascada_datos={
                    "programa": datos_acad["programa"],
                    "pensum": datos_acad["pensum"],
                    "nivel": semestre_val,
                    "asignatura": datos_acad["asignatura"],
                    "codigo_asignatura": datos_acad["codigo_asignatura"],
                },
            )

            if not procesar_recursos:
                return RedirectResponse(f"/tests/{test_job_id}/revision", status_code=303)

        formato_recurso = str(formato_recurso or "").strip().upper() or "H5P"
        if formato_recurso not in FORMATOS_RECURSO_INTERACTIVO:
            return generar_html(
                error="Formato de recurso no válido: elige H5P o HTML."
            )

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
            formato_recurso=formato_recurso,
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
            zip_info = analizar_zip(contenido_zip, formato_recurso=formato_recurso)
        except zipfile.BadZipFile:
            return generar_html(error="El ZIP no es válido.")

        revision_h5p = None
        if formato_recurso == "H5P":
            revision_h5p = preview_h5p_titles(contenido_zip, hojas, TEMP_DIR)

        # ====================================================
        # CREAR TRABAJO (guarda archivos, prevalida Drive-ZIP y lo registra)
        # ====================================================

        test_info = None
        if procesar_test and test_job_id and document_test:
            test_info = {
                "test_job_id": test_job_id,
                "nombre_documento": nom_test,
                "cantidad_tests": len(document_test.tests),
                "cantidad_preguntas": sum(len(sec.questions) for t in document_test.tests for sec in t.sections),
            }

        # Si la prevalidacion falla, el servicio lanza ValueError con el
        # mensaje para el usuario y el except de abajo lo muestra.
        trabajo_id, resultado = create_analyzed_job(
            contenido_excel,
            contenido_zip,
            hojas,
            zip_info,
            modo_matriz,
            google_sheet_url,
            hoja_objetivo,
            nombre_matriz,
            procesar_ovi,
            procesar_ova,
            procesar_retos,
            _usuario_actual(),
            test_job_id=test_job_id,
            test_info=test_info,
            formato_recurso=formato_recurso,
        )
        resultado_revision = dict(resultado)
        if revision_h5p is not None:
            resultado_revision["revision_h5p"] = revision_h5p

        # ====================================================
        # PRE-SELECCION DE FALTANTES (reintento sin volver a elegir)
        # ====================================================
        # Si este curso ya tuvo cargues con actividades pendientes, se marcan
        # solo esas. Si la matriz no coincide con lo registrado, no se marca
        # nada y se conserva el comportamiento normal (todo marcado).
        faltantes, cursos_faltantes = preseleccion_faltantes(hojas, _usuario_actual())
        aviso_preseleccion = None
        if faltantes:
            cursos_txt = ", ".join(cursos_faltantes) or "este curso"
            aviso_preseleccion = (
                f"Quedaron {len(faltantes)} actividad(es) pendientes de un cargue anterior "
                f"de {cursos_txt}. Se marcaron solo esas para no repetir lo que ya está "
                "en PRIZMA; las demás quedaron sin marca. Si quieres cargar todas, usa "
                "«Seleccionar todo»."
            )

        return generar_html(
            resultado=resultado_revision,
            trabajo_id=trabajo_id,
            seleccion_actual=faltantes or None,
            aviso=aviso_preseleccion,
        )

    except Exception as e:
        return generar_html(error=str(e))
