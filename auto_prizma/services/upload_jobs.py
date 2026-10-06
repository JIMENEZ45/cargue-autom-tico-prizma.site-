"""Estado de los cargues, historial, reportes y cola de ejecucion con limite de cargues simultaneos.
"""

from auto_prizma.automation.prizma import engine as motor_prizma_modulo
from auto_prizma.automation.prizma.engine import ejecutar_cargue
import os
import json
import re
import threading
from collections import deque
from datetime import datetime

from auto_prizma.core.config import (
    HISTORIAL_PATH,
    MAX_CARGUES_SIMULTANEOS,
    RESULTADOS_DIR,
    ZONA_HORARIA_COLOMBIA,
)
from auto_prizma.services.auth import USUARIO_ACTUAL
from auto_prizma.integrations.google.drive import _DRIVE_THREAD_LOCAL


# ============================================================
# TRABAJOS
# ============================================================

TRABAJOS = {}
HISTORIAL_LOCK = threading.Lock()
TRABAJOS_LOCK = threading.RLock()
COLA_CARGUES = deque()
COLA_CONDICION = threading.Condition(TRABAJOS_LOCK)

# Cuantos cargues pueden correr al mismo tiempo: MAX_CARGUES_SIMULTANEOS
# (maximo 2, ver auto_prizma.core.config). ZONA_HORARIA_COLOMBIA tambien
# vive en la configuracion central y se reexporta desde aqui.

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


def _ahora_colombia():
    return datetime.now(ZONA_HORARIA_COLOMBIA)


def _ahora_colombia_iso():
    return _ahora_colombia().isoformat(timespec="seconds")


def _sanitizar_parte_nombre(valor, limite=70):
    texto = str(valor or "").strip()
    texto = re.sub(r'[\\/:*?"<>|]+', "-", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .-")
    if not texto:
        texto = "Sin nombre"
    return texto[:limite].rstrip()


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


def _nombre_reporte(cursos, trabajo_id):
    fecha = _ahora_colombia().strftime("%Y-%m-%d_%H-%M-%S")

    if cursos:
        curso = _sanitizar_parte_nombre(cursos[0]["curso"], 58)
        programa = _sanitizar_parte_nombre(cursos[0]["programa"], 58)
        extra = ""
        if len(cursos) > 1:
            extra = f"_y_{len(cursos) - 1}_curso_mas"
        return f"{fecha} - {curso} - {programa}{extra} - {trabajo_id[:6]}.csv"

    return f"{fecha} - resultado_prizma - {trabajo_id[:6]}.csv"


def _ruta_reporte_test(cascada, test_job_id):
    """Ruta del CSV de reporte para un Test Evaluativo ejecutado SOLO
    (sin OVI/OVA/Retos), fuera de la cola de cargues normal."""
    fecha = _ahora_colombia().strftime("%Y-%m-%d_%H-%M-%S")
    asignatura = _sanitizar_parte_nombre((cascada or {}).get("asignatura") or "Test Evaluativo", 58)
    nombre = f"{fecha} - {asignatura} - Test - {test_job_id[:6]}.csv"
    return os.path.join(RESULTADOS_DIR, nombre)


def _registrar_historial_test(test_job_id, ruta_reporte, cascada, estado_final, usuario_app):
    """Registra en data/historial.json el resultado de un Test Evaluativo
    ejecutado SOLO (flujo exclusivo, sin recursos OVI/OVA/Retos)."""
    cascada = cascada or {}
    cursos = [{
        "curso": f"Test Evaluativo: {cascada.get('asignatura') or 'Sin asignatura'}",
        "programa": cascada.get("programa") or "Programa sin nombre",
    }]
    return _agregar_registro_historial(test_job_id, ruta_reporte, cursos, estado_final, usuario_app, tipo="test")


def _cargar_historial():
    if not os.path.isfile(HISTORIAL_PATH):
        return []

    try:
        with open(HISTORIAL_PATH, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, list) else []
    except Exception:
        return []


def _guardar_historial(registros):
    temporal = HISTORIAL_PATH + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(registros, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, HISTORIAL_PATH)


def _agregar_registro_historial(registro_id, ruta_reporte, cursos, estado_final, usuario_app, tipo=None):
    """Escribe una fila en data/historial.json si no existe ya ese id.
    Usado tanto por cargues de recursos (OVI/OVA/Retos) como por
    tests evaluativos (combinados o exclusivos)."""
    if not ruta_reporte or not os.path.isfile(ruta_reporte):
        return False

    with HISTORIAL_LOCK:
        registros = _cargar_historial()

        if any(r.get("id") == registro_id for r in registros):
            return False

        registro = {
            "id": registro_id,
            "fecha_iso": _ahora_colombia_iso(),
            "archivo_reporte": os.path.basename(ruta_reporte),
            "cursos": cursos or [],
            "estado_final": estado_final,
            "usuario_app": usuario_app,
        }
        if tipo:
            registro["tipo"] = tipo
        registros.append(registro)
        _guardar_historial(registros)
        return True


def _registrar_reporte_final(trabajo):
    escrito = _agregar_registro_historial(
        trabajo.get("id"),
        trabajo.get("ruta_reporte"),
        trabajo.get("cursos", []),
        trabajo.get("etapa", "finalizado"),
        trabajo.get("usuario_app"),
    )
    if escrito or trabajo.get("historial_registrado"):
        trabajo["historial_registrado"] = True


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
        trabajo["usuario_prizma_temporal"] = usuario_prizma
        trabajo["contrasena_prizma_temporal"] = contrasena_prizma
        trabajo["credenciales_prizma"] = {"usuario": usuario_prizma, "clave": contrasena_prizma}
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


print(
    "Cargues simultaneos:",
    MAX_CARGUES_SIMULTANEOS,
)
