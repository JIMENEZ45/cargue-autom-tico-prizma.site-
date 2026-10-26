"""Estado de los cargues y cola de ejecucion con limite de cargues simultaneos.

El historial y los reportes viven en auto_prizma.services.history.
"""

from auto_prizma.automation.prizma import engine as motor_prizma_modulo
from auto_prizma.automation.prizma.engine import (
    ejecutar_cargue,
    validar_credenciales_prizma,
)
import json
import os
import shutil
import threading
import uuid
from collections import deque

from auto_prizma.core.clock import _ahora_colombia_iso
from auto_prizma.core.config import (
    FORMATO_RECURSO_POR_DEFECTO,
    MAX_CARGUES_SIMULTANEOS,
    RESULTADOS_DIR,
    TEMP_DIR,
    UPLOADS_DIR,
)
from auto_prizma.services.auth import USUARIO_ACTUAL, _es_de
from auto_prizma.services.drive_zip_validation import _prevalidar_recursos_drive_zip_ultrarapido
from auto_prizma.services.history import _nombre_reporte, _registrar_reporte_final
from auto_prizma.integrations.google.drive import _DRIVE_THREAD_LOCAL


# ============================================================
# TRABAJOS
# ============================================================

TRABAJOS = {}
TRABAJOS_LOCK = threading.RLock()
COLA_CARGUES = deque()
COLA_CONDICION = threading.Condition(TRABAJOS_LOCK)

# Cuantos cargues pueden correr al mismo tiempo: MAX_CARGUES_SIMULTANEOS
# (maximo 2, ver auto_prizma.core.config).

CARGUES_ACTIVOS = 0


def _codificar_clave_actividad(hoja, fila):
    return json.dumps(
        [str(hoja or ""), int(fila or 0)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _parsear_clave_actividad(valor):
    try:
        datos = json.loads(str(valor or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(datos, list) or len(datos) != 2:
        return None

    hoja = str(datos[0] or "")
    try:
        fila = int(datos[1])
    except (TypeError, ValueError):
        return None

    if not hoja or fila <= 0:
        return None

    return hoja, fila


def _validar_seleccion_actividades(valores, resultado):
    permitidas = set()
    for hoja in (resultado or {}).get("hojas", []) or []:
        nombre_hoja = str(hoja.get("hoja") or "")
        for actividad in hoja.get("actividades", []) or []:
            try:
                fila = int(actividad.get("fila") or 0)
            except (TypeError, ValueError):
                continue
            if nombre_hoja and fila > 0:
                permitidas.add((nombre_hoja, fila))

    seleccion = []
    vistas = set()
    for valor in valores or []:
        clave = _parsear_clave_actividad(valor)
        if clave is None or clave not in permitidas or clave in vistas:
            continue
        vistas.add(clave)
        seleccion.append([clave[0], clave[1]])

    return seleccion


def _cursos_desde_hojas(hojas):
    cursos = []
    vistos = set()

    for hoja in hojas or []:
        curso = str(hoja.get("curso") or "").strip() or "Curso sin nombre"
        programa = str(hoja.get("programa") or "").strip() or "Programa sin nombre"
        clave = (curso.casefold(), programa.casefold())
        if clave in vistos:
            continue
        vistos.add(clave)
        cursos.append({"curso": curso, "programa": programa})

    return cursos


def ejecutar_cargue_con_historial(
    ruta_excel,
    ruta_zip,
    carpeta_temp,
    ruta_reporte,
    procesar_ovi,
    procesar_ova,
    procesar_retos,
    usuario_prizma,
    contrasena_prizma,
    trabajo,
):
    _DRIVE_THREAD_LOCAL.recursos = trabajo.get(
        "recursos_drive_resueltos",
        {},
    )
    _DRIVE_THREAD_LOCAL.hoja_objetivo = trabajo.get(
        "hoja_objetivo",
    )

    # El hilo del worker no hereda el contexto de la peticion.
    testigo_usuario = USUARIO_ACTUAL.set(trabajo.get("usuario_app"))

    try:
        ejecutar_cargue(
            ruta_excel,
            ruta_zip,
            carpeta_temp,
            ruta_reporte,
            procesar_ovi,
            procesar_ova,
            procesar_retos,
            usuario_prizma,
            contrasena_prizma,
            trabajo,
            trabajo.get("seleccion_actividades"),
            formato_recurso=trabajo.get("formato_recurso") or FORMATO_RECURSO_POR_DEFECTO,
        )
    finally:
        try:
            _DRIVE_THREAD_LOCAL.recursos = {}
            _DRIVE_THREAD_LOCAL.hoja_objetivo = None
            USUARIO_ACTUAL.reset(testigo_usuario)
        except Exception:
            pass
        # El registro en historial se hace en _ejecutar_cargue_en_hilo,
        # despues de que tambien corra (si aplica) el Test Evaluativo,
        # para que el resultado del test quede reflejado.


# ============================================================
# COLA GLOBAL DE CARGUES - HASTA 2 PROCESOS A LA VEZ
# ============================================================

def _posicion_en_cola(trabajo_id):
    with TRABAJOS_LOCK:
        pendientes = [
            tid for tid in COLA_CARGUES
            if tid in TRABAJOS
            and TRABAJOS[tid].get("etapa") == "en_cola"
            and not TRABAJOS[tid].get("terminado")
        ]
        try:
            return pendientes.index(trabajo_id) + 1
        except ValueError:
            return None


def _encolar_trabajo(trabajo_id, usuario_prizma, contrasena_prizma):
    with COLA_CONDICION:
        trabajo = TRABAJOS[trabajo_id]
        # Las credenciales solo viven en estos dos campos temporales: el hilo
        # del cargue (o la cancelacion) los elimina. Nunca se guardan en otro
        # campo del trabajo, que permanece en memoria mientras el servidor vive.
        trabajo["usuario_prizma_temporal"] = usuario_prizma
        trabajo["contrasena_prizma_temporal"] = contrasena_prizma
        trabajo["etapa"] = "en_cola"
        trabajo["mensaje"] = "Cargue agregado a la cola de procesamiento."
        trabajo["encolado_en"] = _ahora_colombia_iso()
        trabajo["cancelar_solicitado"] = False
        trabajo["terminado"] = False
        if trabajo_id not in COLA_CARGUES:
            COLA_CARGUES.append(trabajo_id)

        # Despacha solo si hay uno de los dos cupos globales disponible.
        # Si ambos estan ocupados, el trabajo conserva su posicion FIFO.
        _despachar_cargues_pendientes()


def _hay_capacidad():
    """Debe llamarse con COLA_CONDICION tomado."""
    return CARGUES_ACTIVOS < MAX_CARGUES_SIMULTANEOS


def _despachar_cargues_pendientes():
    """Lanza un hilo propio por cada cargue que quepa.

    Debe llamarse con COLA_CONDICION tomado.
    """
    global CARGUES_ACTIVOS

    while COLA_CARGUES and _hay_capacidad():
        trabajo_id = COLA_CARGUES.popleft()
        trabajo = TRABAJOS.get(trabajo_id)

        if not trabajo:
            continue

        if trabajo.get("terminado") or trabajo.get("cancelar_solicitado"):
            continue

        CARGUES_ACTIVOS += 1

        threading.Thread(
            target=_ejecutar_cargue_en_hilo,
            args=(trabajo_id,),
            name="auto-prizma-cargue-" + str(trabajo_id)[:8],
            daemon=True,
        ).start()

    COLA_CONDICION.notify_all()


def _ejecutar_test_en_cargue(trabajo, test_job_id, usuario, contrasena):
    from auto_prizma.evaluative_tests.state import _JOBS, _JOBS_LOCK
    from auto_prizma.evaluative_tests.execution import ejecutar_test_job
    with _JOBS_LOCK:
        job_test = _JOBS.get(test_job_id)
    if not job_test:
        return

    doc = job_test.get("document")
    if not doc or not getattr(doc, "tests", None):
        return

    tests_list = doc.tests
    num_tests = len(tests_list)
    if num_tests == 0:
        return

    cascada_test = job_test.get("cascada_datos") or {}
    ruta_reporte = trabajo.get("ruta_reporte")

    detalle = trabajo.setdefault("detalle_actividades", [])
    offset = len(detalle)
    for idx, t in enumerate(tests_list, start=1):
        num_preg = sum(len(sec.questions) for sec in t.sections)
        detalle.append({
            "numero": offset + idx,
            "nombre": f"Test Evaluativo: {t.title or f'Test {idx}'} ({num_preg} preguntas)",
            "estado": "pendiente",
            "error": "",
        })

    trabajo["total"] = len(detalle)
    trabajo["terminado"] = False
    trabajo["etapa"] = "cargando_test"
    trabajo["mensaje"] = f"Iniciando cargue del Test Evaluativo en PRIZMA ({num_tests} examen{'es' if num_tests > 1 else ''})..."

    def _fila_test_reporte(indice, item, resultado):
        t = tests_list[indice - 1] if 0 < indice <= len(tests_list) else None
        actividad = {
            "fila_excel": f"Test {indice}",
            "programa": cascada_test.get("programa") or "",
            "curso": cascada_test.get("asignatura") or "",
            "semana": (getattr(t, "week", "") or cascada_test.get("nivel") or "") if t else "",
            "unidad": (getattr(t, "cut", "") or "") if t else "",
            "nombre": item["nombre"],
            "categoria_prizma": "Test Evaluativo",
            "tipo_archivo": "Test",
        }
        try:
            motor_prizma_modulo.guardar_resultado(
                ruta_reporte,
                actividad,
                resultado,
                item.get("error") or "",
            )
        except Exception:
            pass

    def on_test(indice, estado_test, msg_test, err=""):
        item_idx = offset + indice - 1
        if 0 <= item_idx < len(trabajo["detalle_actividades"]):
            item = trabajo["detalle_actividades"][item_idx]
            if estado_test == "en_proceso":
                item["estado"] = "procesando"
                trabajo["mensaje"] = f"Cargando {item['nombre']}..."
            elif estado_test == "exitoso":
                item["estado"] = "ok"
                trabajo["procesadas"] = (trabajo.get("procesadas") or 0) + 1
                trabajo["exitosas"] = (trabajo.get("exitosas") or 0) + 1
                trabajo["mensaje"] = f"{item['nombre']} guardado con éxito."
                if ruta_reporte:
                    _fila_test_reporte(indice, item, "Cargado")
            elif estado_test == "omitido":
                # Ya existía en PRIZMA de un intento anterior: el objetivo ya
                # está cumplido (el test está en PRIZMA), solo no se duplica.
                item["estado"] = "ok"
                trabajo["procesadas"] = (trabajo.get("procesadas") or 0) + 1
                trabajo["exitosas"] = (trabajo.get("exitosas") or 0) + 1
                trabajo["mensaje"] = f"{item['nombre']} ya estaba cargado en PRIZMA (omitido para no duplicar)."
                if ruta_reporte:
                    _fila_test_reporte(indice, item, "Omitido")
            elif estado_test == "error":
                item["estado"] = "error"
                item["error"] = err or msg_test
                trabajo["procesadas"] = (trabajo.get("procesadas") or 0) + 1
                trabajo["errores"] = (trabajo.get("errores") or 0) + 1
                trabajo["mensaje"] = f"Error en {item['nombre']}: {item['error']}"
                if ruta_reporte:
                    _fila_test_reporte(indice, item, "Error")
            elif estado_test == "cancelado":
                item["estado"] = "error"
                item["error"] = "Detenido por usuario"
                if ruta_reporte:
                    _fila_test_reporte(indice, item, "Cancelado")

    def on_log(nivel, msg, snap=None):
        if nivel in ["error", "warn"]:
            trabajo["mensaje"] = f"Test: {msg}"

    res = ejecutar_test_job(
        job_id=test_job_id,
        usuario_prizma=usuario,
        clave_prizma=contrasena,
        user=trabajo.get("usuario_app", ""),
        simulacion=False,
        headless=True,
        on_test_callback=on_test,
        on_log_callback=on_log,
        cancel_checker=lambda: bool(trabajo.get("cancelar_solicitado")),
    )

    trabajo["terminado"] = True
    ex = trabajo.get("exitosas", 0)
    er = trabajo.get("errores", 0)
    if not res.get("ok"):
        trabajo["etapa"] = "error"
        trabajo["mensaje"] = f"Error en el cargue del Test Evaluativo: {res.get('error', 'Error desconocido.')}"
    else:
        trabajo["etapa"] = "finalizado"
        trabajo["mensaje"] = f"Cargue completo finalizado. Exitosas: {ex}. Errores: {er}."


def _ejecutar_cargue_en_hilo(trabajo_id):
    """Corre UN cargue completo. Cada cargue tiene su propio hilo y su
    propio navegador, asi que varios usuarios pueden cargar a la vez."""
    global CARGUES_ACTIVOS

    usuario = ""
    contrasena = ""

    with COLA_CONDICION:
        trabajo = TRABAJOS.get(trabajo_id)

        if not trabajo:
            CARGUES_ACTIVOS -= 1
            COLA_CONDICION.notify_all()
            return

        usuario = trabajo.pop("usuario_prizma_temporal", "")
        contrasena = trabajo.pop("contrasena_prizma_temporal", "")
        trabajo["etapa"] = "iniciando"
        trabajo["mensaje"] = "Iniciando navegador y autenticación PRIZMA..."
        trabajo["iniciado_en"] = _ahora_colombia_iso()
        trabajo["terminado"] = False

    try:
        tiene_recursos = (
            bool(trabajo.get("procesar_ovi")) or
            bool(trabajo.get("procesar_ova")) or
            bool(trabajo.get("procesar_retos"))
        )
        test_job_id = trabajo.get("test_job_id")

        if tiene_recursos:
            ejecutar_cargue_con_historial(
                trabajo["ruta_excel"],
                trabajo["ruta_zip"],
                trabajo["carpeta_temp"],
                trabajo["ruta_reporte"],
                trabajo["procesar_ovi"],
                trabajo["procesar_ova"],
                trabajo["procesar_retos"],
                usuario,
                contrasena,
                trabajo,
            )

        if test_job_id and not trabajo.get("cancelar_solicitado"):
            msg_act = str(trabajo.get("mensaje", ""))
            # Si hubo error fatal de login en los recursos, no intentamos el test
            if tiene_recursos and ("ERROR_LOGIN_PRIZMA" in msg_act or "No fue posible iniciar sesión en PRIZMA" in msg_act):
                pass
            else:
                _ejecutar_test_en_cargue(trabajo, test_job_id, usuario, contrasena)

    except Exception as exc:
        trabajo["etapa"] = "error"
        trabajo["mensaje"] = str(exc)
        trabajo["terminado"] = True
    finally:
        usuario = ""
        contrasena = ""
        trabajo.pop("usuario_prizma_temporal", None)
        trabajo.pop("contrasena_prizma_temporal", None)
        trabajo["finalizado_en"] = _ahora_colombia_iso()
        _registrar_reporte_final(trabajo)

        with COLA_CONDICION:
            CARGUES_ACTIVOS -= 1
            _despachar_cargues_pendientes()


# ============================================================
# CICLO DE VIDA DE UN TRABAJO (lo usan las rutas web)
# ============================================================

# Etapas en las que un trabajo cuenta como "cargue en curso".
ETAPAS_ACTIVAS = {
    "en_cola",
    "iniciando",
    "login",
    "preparando",
    "procesando",
    "validando_login",
    "cargando_test",
}


def create_analyzed_job(
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
    usuario_app,
    test_job_id=None,
    test_info=None,
    formato_recurso=FORMATO_RECURSO_POR_DEFECTO,
):
    """Registra un trabajo de cargue a partir de un analisis valido.

    Guarda la matriz y el ZIP en uploads/<id>/, crea temp/<id>/, ejecuta la
    prevalidacion Drive-ZIP (solo con matriz por link) y deja el trabajo en
    TRABAJOS con etapa "analizado".

    Args:
        contenido_excel: bytes de la matriz ya normalizada a XLSX.
        contenido_zip: bytes del ZIP de recursos.
        hojas: hojas validas devueltas por analizar_excel.
        zip_info: resumen devuelto por analizar_zip.
        modo_matriz: "link" (Google Sheets) o "archivo".
        google_sheet_url: enlace de la matriz (solo modo link).
        hoja_objetivo: pestana del enlace (#gid) o None.
        nombre_matriz: nombre visible de la matriz.
        procesar_ovi, procesar_ova, procesar_retos: categorias elegidas.
        usuario_app: usuario de la aplicacion dueno del trabajo.
        test_job_id: id del Test Evaluativo combinado, si lo hay.
        test_info: resumen del Test Evaluativo para la pagina, si lo hay.
        formato_recurso: "H5P" o "HTML". En modo HTML no se valida contra
            Drive: los .html solo vienen en el ZIP y se emparejan por nombre.

    Returns:
        (trabajo_id, resultado): resultado es lo que muestra la pagina de analisis.

    Raises:
        ValueError: si la prevalidacion Drive-ZIP encuentra problemas
            estructurales (con el mensaje para el usuario). Antes se borran
            las carpetas creadas.
    """
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

    modo_html = str(formato_recurso or "").strip().upper() == "HTML"

    if modo_matriz == "link" and not modo_html:
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

            raise ValueError(
                "La validación Google Drive vs ZIP encontró problemas. "
                + resumen_errores
            )
    else:
        # En modo archivo (o en modo HTML) no se valida contra Drive. El motor
        # conserva su resolvedor seguro de recursos del ZIP y nunca elige
        # ambiguos.
        recursos_drive_resueltos = {}
        preflight_drive = {
            "ok": True,
            "modo": "html" if modo_html else "archivo",
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
        "formato_recurso": "HTML" if modo_html else "H5P",
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
        "usuario_app": usuario_app,
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
        "formato_recurso": "HTML" if modo_html else "H5P",
    }

    if test_info is not None:
        resultado["test_info"] = test_info
        TRABAJOS[trabajo_id]["test_job_id"] = test_job_id

    TRABAJOS[trabajo_id]["resultado_analisis"] = resultado

    return trabajo_id, resultado


def validate_access_and_enqueue(trabajo_id, usuario_prizma, contrasena_prizma):
    """Valida las credenciales de PRIZMA y, si son correctas, encola el trabajo.

    Returns:
        (True, "") si el trabajo quedo en cola, o (False, mensaje) si PRIZMA
        rechazo el acceso o no respondio; en ese caso el trabajo vuelve a la
        etapa "analizado" para poder reintentar.
    """
    trabajo = TRABAJOS[trabajo_id]
    trabajo["etapa"] = "validando_login"
    trabajo["mensaje"] = "Validando usuario y contraseña en PRIZMA..."
    validacion = validar_credenciales_prizma(usuario_prizma, contrasena_prizma)

    if not validacion.get("ok"):
        trabajo["etapa"] = "analizado"
        trabajo["mensaje"] = validacion.get("mensaje", "No fue posible validar el acceso a PRIZMA.")
        return False, trabajo["mensaje"]

    _encolar_trabajo(trabajo_id, usuario_prizma, contrasena_prizma)
    return True, ""


def active_jobs():
    """Cargues en curso de todos los usuarios, del mas antiguo al mas reciente."""
    activos = [
        trabajo for trabajo in TRABAJOS.values()
        if not trabajo.get("terminado")
        and trabajo.get("etapa") in ETAPAS_ACTIVAS
    ]
    activos.sort(key=lambda item: item.get("encolado_en") or item.get("iniciado_en") or item.get("creado_en", ""))
    return activos


def cancel_job(trabajo_id, usuario):
    """Pide cancelar un trabajo del usuario.

    Returns:
        "no_encontrado": no existe o pertenece a otra persona.
        "terminado": ya habia terminado; no se hace nada.
        "cancelado": estaba en cola y se cancelo sin llegar a iniciar.
        "solicitado": esta en ejecucion; se detendra de forma segura al
            terminar la actividad actual.
    """
    with COLA_CONDICION:
        trabajo = TRABAJOS.get(trabajo_id)
        if not trabajo or not _es_de(trabajo, usuario):
            return "no_encontrado"

        if trabajo.get("terminado"):
            return "terminado"

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
            resultado = "cancelado"
        else:
            trabajo["mensaje"] = (
                "Cancelación solicitada. El proceso se detendrá de forma segura "
                "al terminar la actividad actual."
            )
            resultado = "solicitado"

        COLA_CONDICION.notify_all()

    return resultado


def public_job_status(trabajo_id, usuario):
    """Estado de un trabajo para la pagina de progreso (JSON de /estado).

    Returns:
        El diccionario publico (sin credenciales ni rutas internas salvo la
        disponibilidad del reporte), o None si el trabajo no existe o
        pertenece a otra persona.
    """
    trabajo = TRABAJOS.get(trabajo_id)

    if not trabajo or not _es_de(trabajo, usuario):
        return None

    return {
        "etapa": trabajo["etapa"],
        "mensaje": trabajo["mensaje"],
        "total": trabajo["total"],
        "procesadas": trabajo["procesadas"],
        "exitosas": trabajo["exitosas"],
        "errores": trabajo["errores"],
        "terminado": trabajo["terminado"],
        "detalle_actividades": trabajo.get("detalle_actividades", []),
        "reporte_disponible": os.path.isfile(trabajo["ruta_reporte"]),
        "posicion_cola": _posicion_en_cola(trabajo_id),
        "cancelar_solicitado": bool(trabajo.get("cancelar_solicitado")),
    }


print(
    "Cargues simultaneos:",
    MAX_CARGUES_SIMULTANEOS,
)
