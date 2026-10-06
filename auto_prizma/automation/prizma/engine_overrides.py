"""Ajustes que se aplican sobre motor_prizma al importar este modulo.

Reemplaza leer_actividades_excel, resolver_recurso y
validar_carpeta_drive_para_actividad para usar la hoja objetivo y los
recursos ya prevalidados. main.py lo importa al arrancar.
"""

from auto_prizma.automation.prizma import engine as motor_prizma_modulo
import zipfile
import os
import uuid
import shutil

from auto_prizma.core.config import TEMP_DIR
from auto_prizma.integrations.google.drive import (
    _DRIVE_THREAD_LOCAL,
    _misma_hoja,
    _recurso_resuelto_thread,
)
from auto_prizma.services.drive_zip_validation import _clave_nombre_drive_zip


def _validar_drive_desde_preflight(actividad):
    """Reutiliza el resultado del analisis sin volver a consultar Drive."""
    resuelto = _recurso_resuelto_thread(actividad)
    if resuelto and resuelto.get("cargable", False):
        actividad["nombre_recurso_drive"] = str(resuelto.get("nombre_drive") or "")
    return None

_LEER_ACTIVIDADES_EXCEL_ORIGINAL = motor_prizma_modulo.leer_actividades_excel


def _leer_actividades_excel_hoja_objetivo(
    ruta_excel,
    procesar_ovi=True,
    procesar_ova=True,
    procesar_retos=True,
):
    """Igual que el lector original, pero limitado a la pestaña del enlace.

    El motor llama a leer_actividades_excel como global del modulo, asi que
    reemplazarlo aqui cubre tanto el preflight como el cargue a PRIZMA.
    """
    actividades = _LEER_ACTIVIDADES_EXCEL_ORIGINAL(
        ruta_excel,
        procesar_ovi,
        procesar_ova,
        procesar_retos,
    )

    objetivo = getattr(_DRIVE_THREAD_LOCAL, "hoja_objetivo", None)

    if not objetivo:
        return actividades

    return [
        actividad for actividad in actividades
        if _misma_hoja(actividad.get("hoja"), objetivo)
    ]


motor_prizma_modulo.leer_actividades_excel = _leer_actividades_excel_hoja_objetivo


# FALTABA: esta referencia no estaba definida en ninguna parte del proyecto.
# Si _resolver_recurso_desde_preflight llegaba a ejecutarse para una fila SIN
# Drive en la columna G, reventaba con NameError.
_RESOLVER_RECURSO_ORIGINAL = motor_prizma_modulo.resolver_recurso


def _resolver_zip_por_actividad_fallback(
    actividad,
    indice_zip,
    indice_motor,
    actividades_curso,
):
    """Resuelve el binario local del ZIP para una fila ya vinculada por G.

    Se usa SOLO cuando el enlace de la columna G ya identifica un unico
    recurso compatible en Drive pero su nombre externo no coincide con el
    nombre dentro del ZIP. No consulta otras hojas ni otros enlaces Drive.

    La seleccion local reutiliza el resolver historico, que exige una
    coincidencia unica para la actividad y su tipo. Si no puede resolver de
    forma segura, devuelve None y el preflight conserva el error.
    """
    actividad_local = dict(actividad or {})
    actividad_local.pop("nombre_recurso_drive", None)

    carpeta_prueba = os.path.join(
        TEMP_DIR,
        "preflight_fallback_" + uuid.uuid4().hex,
    )

    try:
        resultado, error = _RESOLVER_RECURSO_ORIGINAL(
            actividad_local,
            indice_motor,
            carpeta_prueba,
            actividades_curso,
        )
        if error or not resultado:
            return None

        nombre = str(resultado.get("nombre_original") or "").strip()
        if not nombre:
            return None

        candidatos = list(
            indice_zip.get("exacto", {}).get(
                _clave_nombre_drive_zip(nombre),
                [],
            )
        )

        # El resolver historico ya rechaza duplicados; mantenemos la misma
        # garantia tambien al convertir su resultado al indice del preflight.
        if len(candidatos) != 1:
            return None

        return candidatos[0]
    finally:
        shutil.rmtree(carpeta_prueba, ignore_errors=True)


def _resolver_recurso_desde_preflight(
    actividad,
    indice_recursos,
    carpeta_temp,
    actividades_curso,
):
    resuelto = _recurso_resuelto_thread(actividad)
    if not resuelto:
        return _RESOLVER_RECURSO_ORIGINAL(
            actividad,
            indice_recursos,
            carpeta_temp,
            actividades_curso,
        )

    if not resuelto.get("cargable", False):
        return None, str(
            resuelto.get("error_cargue")
            or "ERROR_DRIVE_ZIP_NO_COINCIDEN"
        )

    nombre_esperado = str(resuelto.get("nombre") or "").strip()
    nombre_esperado_clave = _clave_nombre_drive_zip(nombre_esperado)
    miembro_esperado = str(resuelto.get("miembro_zip") or "").strip()

    # El preflight ya resolvio exactamente que miembro del ZIP corresponde a
    # esta fila. Esto permite continuar incluso si existen copias con el mismo
    # nombre y tamano: no volvemos a adivinar durante el cargue real.
    if miembro_esperado:
        exactos = [
            recurso
            for recurso in indice_recursos
            if recurso.get("miembro") == miembro_esperado
        ]
    else:
        exactos = [
            recurso
            for recurso in indice_recursos
            if _clave_nombre_drive_zip(recurso.get("nombre")) == nombre_esperado_clave
        ]

    if len(exactos) == 0:
        return None, "ERROR_RECURSO_DRIVE_NO_ESTA_EN_ZIP"
    if len(exactos) != 1:
        return None, "ERROR_RECURSO_DUPLICADO"

    elegido = exactos[0]
    carpeta_fila = os.path.join(
        carpeta_temp,
        "fila_" + str(actividad.get("fila_excel") or 0),
    )
    os.makedirs(carpeta_fila, exist_ok=True)
    ruta_destino = os.path.join(carpeta_fila, elegido["nombre"])

    try:
        with zipfile.ZipFile(elegido["zip"], "r") as zip_ref:
            info = zip_ref.getinfo(elegido["miembro"])
            tamano_esperado = int(
                resuelto.get("tamano_zip")
                if resuelto.get("tamano_zip") is not None
                else resuelto.get("tamano") or -1
            )
            if tamano_esperado >= 0 and int(info.file_size) != tamano_esperado:
                return None, "ERROR_RECURSO_ZIP_TAMANO_CAMBIO"

            with zip_ref.open(elegido["miembro"]) as origen:
                with open(ruta_destino, "wb") as destino:
                    shutil.copyfileobj(origen, destino)
    except KeyError:
        return None, "ERROR_RECURSO_DRIVE_NO_ESTA_EN_ZIP"
    except Exception:
        return None, "ERROR_EXTRAYENDO_RECURSO"

    if not os.path.isfile(ruta_destino):
        return None, "ERROR_EXTRAYENDO_RECURSO"

    print(
        "Recurso exacto prevalidado Drive -> ZIP:",
        elegido["nombre"],
        "|",
        int(resuelto.get("tamano_zip") or resuelto.get("tamano") or 0),
        "bytes ZIP",
    )
    return {
        "ruta": ruta_destino,
        "nombre_original": elegido["nombre"],
        "puntuacion": 10000,
    }, None


# Durante el cargue real, reutilizar exactamente lo resuelto por el preflight.
# ejecutar_cargue es una funcion del modulo motor_prizma y consulta estos
# nombres globales en tiempo de ejecucion, por eso el reemplazo aplica tambien
# al alias importado al inicio de este archivo.
motor_prizma_modulo.validar_carpeta_drive_para_actividad = _validar_drive_desde_preflight
motor_prizma_modulo.resolver_recurso = _resolver_recurso_desde_preflight
