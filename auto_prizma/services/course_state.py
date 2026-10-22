"""Estado acumulado por curso: que actividades ya quedaron en PRIZMA.

Persiste en data/estado_cursos.json un registro por curso con el resultado
ultimo y acumulado de cada actividad (hoja + fila de la matriz). De ahi salen:

- la pagina /cursos (que falta de un curso y por que),
- el pre-marcado de las fallidas al volver a subir la matriz (reintento).

Regla de negocio: una actividad "falta" mientras nunca haya quedado OK. Si ya
se subio alguna vez y un intento posterior fallo, sigue contando como subida
(el archivo ya esta en PRIZMA), pero se conserva el ultimo error visible.
"""

import threading
import unicodedata

from auto_prizma.core.clock import _ahora_colombia_iso
from auto_prizma.core.config import ESTADO_CURSOS_PATH
from auto_prizma.core.storage import read_json, write_json_atomic
from auto_prizma.services.auth import _usuario_actual
from auto_prizma.services.error_messages import extraer_codigo_error, mensaje_error


ESTADO_LOCK = threading.Lock()

ESTADO_OK = "ok"
ESTADO_ERROR = "error"


# ============================================================
# LECTURA / ESCRITURA
# ============================================================

def _cargar_estado():
    datos = read_json(ESTADO_CURSOS_PATH, {}, dict, errors=(Exception,))
    return datos if isinstance(datos, dict) else {}


def _guardar_estado(datos):
    write_json_atomic(ESTADO_CURSOS_PATH, datos)


def _clave_curso(curso, programa):
    return f"{str(programa or '').strip().casefold()}||{str(curso or '').strip().casefold()}"


def _clave_actividad(hoja, fila):
    return f"{str(hoja or '').strip()}|{str(fila or '').strip()}"


def _fila_int(fila):
    try:
        return int(fila)
    except (TypeError, ValueError):
        return None


# ============================================================
# REGISTRO (llamado desde guardar_resultado en el motor)
# ============================================================

def registrar_resultado_actividad(actividad, resultado, observacion, recurso=""):
    """Acumula el resultado de una actividad en data/estado_cursos.json.

    Nunca propaga excepciones: un fallo aqui no debe romper un cargue.
    """
    try:
        if not isinstance(actividad, dict):
            return

        curso = str(actividad.get("curso") or "").strip()
        if not curso:
            return

        programa = str(actividad.get("programa") or "").strip()
        hoja = str(actividad.get("hoja") or "").strip()
        fila = actividad.get("fila_excel")
        nombre = str(actividad.get("nombre") or "").strip()
        es_ok = str(resultado or "").strip().upper() == "OK"
        ahora = _ahora_colombia_iso()

        with ESTADO_LOCK:
            datos = _cargar_estado()
            id_curso = _clave_curso(curso, programa)

            registro = datos.get(id_curso)
            if not isinstance(registro, dict):
                registro = {
                    "curso": curso,
                    "programa": programa,
                    "actualizado": "",
                    "actividades": {},
                }
                datos[id_curso] = registro

            actividades = registro.get("actividades")
            if not isinstance(actividades, dict):
                actividades = {}
                registro["actividades"] = actividades

            clave = _clave_actividad(hoja, fila)
            item = actividades.get(clave)
            if not isinstance(item, dict):
                item = {
                    "hoja": hoja,
                    "fila": fila,
                    "nombre": nombre,
                    "recurso": "",
                    "estado": ESTADO_ERROR,
                    "codigo": "",
                    "motivo": "",
                    "intentos": 0,
                    "veces_ok": 0,
                    "fallas": 0,
                    "ok_en": "",
                    "ultimo_error_en": "",
                }
                actividades[clave] = item

            item["intentos"] = int(item.get("intentos") or 0) + 1
            item["nombre"] = nombre or item.get("nombre") or ""
            item["hoja"] = hoja
            item["fila"] = fila
            if recurso:
                item["recurso"] = str(recurso)

            if es_ok:
                item["veces_ok"] = int(item.get("veces_ok") or 0) + 1
                item["ok_en"] = str(item.get("ok_en") or "") or ahora
                item["estado"] = ESTADO_OK
                item["codigo"] = ""
                item["motivo"] = ""
            else:
                item["fallas"] = int(item.get("fallas") or 0) + 1
                item["estado"] = ESTADO_ERROR
                codigo = extraer_codigo_error(observacion)
                item["codigo"] = codigo
                item["motivo"] = mensaje_error(observacion)
                item["ultimo_error_en"] = ahora

            registro["curso"] = curso
            registro["programa"] = programa
            registro["actualizado"] = ahora
            # El hilo de cargue fija USUARIO_ACTUAL; fuera de uno (tests,
            # registro manual) no se cambia el dueno existente.
            usuario = _usuario_actual()
            if usuario:
                registro["usuario_app"] = str(usuario)

            _guardar_estado(datos)
    except Exception:
        pass


# ============================================================
# CONSULTAS
# ============================================================

def _es_faltante(item):
    """Falta mientras nunca haya quedado OK en ningun intento."""
    return not str(item.get("ok_en") or "")


def _cursos_del_usuario(datos, usuario_app=None):
    registros = []
    for registro in datos.values():
        if not isinstance(registro, dict):
            continue
        if usuario_app and registro.get("usuario_app") not in (None, "", usuario_app):
            continue
        registros.append(registro)
    return registros


def resumen_cursos(usuario_app=None):
    """Lista de cursos con progreso: total, subidas, faltantes y detalle."""
    datos = _cargar_estado()
    salida = []

    for registro in _cursos_del_usuario(datos, usuario_app):
        actividades = registro.get("actividades")
        if not isinstance(actividades, dict):
            continue

        items = []
        for item in actividades.values():
            if isinstance(item, dict):
                items.append(item)

        subidas = [i for i in items if not _es_faltante(i)]
        faltantes = [i for i in items if _es_faltante(i)]

        salida.append(
            {
                "curso": str(registro.get("curso") or "Curso sin nombre"),
                "programa": str(registro.get("programa") or ""),
                "actualizado": str(registro.get("actualizado") or ""),
                "total": len(items),
                "subidas": len(subidas),
                "faltantes": len(faltantes),
                "detalle_faltantes": _ordenar_por_fila(faltantes),
                "detalle_subidas": _ordenar_por_fila(subidas),
            }
        )

    salida.sort(key=lambda c: (c["programa"].casefold(), c["curso"].casefold()))
    return salida


def _ordenar_por_fila(items):
    def clave(item):
        fila = _fila_int(item.get("fila"))
        return (0, fila, "") if fila is not None else (1, 0, str(item.get("fila") or ""))

    return sorted(items, key=clave)


def cursos_con_faltantes(usuario_app=None, nombres_cursos=None):
    """Cursos (de la lista dada) que tienen actividades nunca subidas.

    ``nombres_cursos`` permite acotar a los cursos de la matriz recien subida.
    """
    nombres = {str(n or "").strip().casefold() for n in nombres_cursos or []}
    salida = []

    for resumen in resumen_cursos(usuario_app):
        if nombres and resumen["curso"].casefold() not in nombres:
            continue
        if resumen["faltantes"]:
            salida.append(resumen)

    return salida


def claves_faltantes(usuario_app=None, nombres_cursos=None):
    """Claves [[hoja, fila], ...] de las actividades nunca subidas.

    Solo se devuelven claves reales (fila numerica) porque son las que el motor
    puede volver a procesar via `filtrar_actividades_seleccionadas`.
    """
    claves = []
    for resumen in cursos_con_faltantes(usuario_app, nombres_cursos):
        for item in resumen["detalle_faltantes"]:
            fila = _fila_int(item.get("fila"))
            if fila is None:
                continue
            claves.append([str(item.get("hoja") or ""), fila])
    return claves


def _norm(texto):
    """Minusculas, sin acentos y con espacios colapsados (para comparar nombres)."""
    texto = str(texto or "").strip().casefold()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(texto.split())


def preseleccion_faltantes(hojas_analizadas, usuario_app=None):
    """Que claves [[hoja, fila]] pre-marcar al volver a subir una matriz.

    Cruza las actividades recien analizadas (estructura de ``analizar_excel``:
    hojas[].actividades[].fila) con las faltantes registradas del usuario.

    Solo se marca una fila si:
    - esa (hoja, fila) sigue sin subirse, y
    - el nombre coincide con el registrado (si la matriz cambio y la fila ahora
      es otra actividad, no se marca nada).

    Returns:
        (claves, cursos): claves para pre-marcar y nombres de curso afectados.
    """
    registradas = {}
    for resumen in resumen_cursos(usuario_app):
        for item in resumen["detalle_faltantes"]:
            fila = _fila_int(item.get("fila"))
            if fila is None:
                continue
            registradas[(str(item.get("hoja") or ""), fila)] = _norm(item.get("nombre"))

    claves = []
    cursos = set()

    for hoja in hojas_analizadas or []:
        if not isinstance(hoja, dict):
            continue
        nombre_hoja = str(hoja.get("hoja") or "")
        curso = str(hoja.get("curso") or "")

        for actividad in hoja.get("actividades") or []:
            fila = _fila_int(actividad.get("fila"))
            if fila is None:
                continue
            nombre_registrado = registradas.get((nombre_hoja, fila))
            if nombre_registrado is None:
                continue
            nombre_actual = _norm(actividad.get("nombre"))
            if nombre_registrado and nombre_actual != nombre_registrado:
                continue
            claves.append([nombre_hoja, fila])
            if curso:
                cursos.add(curso)

    return claves, sorted(cursos)


def total_faltantes(usuario_app=None):
    return sum(r["faltantes"] for r in resumen_cursos(usuario_app))
