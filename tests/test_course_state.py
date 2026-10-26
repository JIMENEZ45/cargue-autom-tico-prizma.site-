"""Pruebas de la traduccion de errores y del estado acumulado por curso.

Cubren:
- error_messages: codigos ERROR_* a frases humanas (y textos libres intactos).
- course_state: acumulacion entre cargues, preseleccion de faltantes y /cursos.
- /analizar: pre-marcado de las actividades que faltaban (reintento).
"""

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from main import app
from auto_prizma.core.config import ESTADO_CURSOS_PATH
from auto_prizma.core.storage import write_json_atomic
from auto_prizma.services import course_state
from auto_prizma.services.auth import SESION_COOKIE, _firmar_sesion
from auto_prizma.services.error_messages import (
    MENSAJES_ERROR,
    es_codigo_error,
    extraer_codigo_error,
    mensaje_error,
)
from auto_prizma.services.upload_jobs import TRABAJOS

RAIZ = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def estado_limpio():
    """Cada prueba arranca con estado_cursos.json vacio y sin trabajos sueltos."""
    write_json_atomic(ESTADO_CURSOS_PATH, {})
    previos = set(TRABAJOS)
    yield
    for clave in set(TRABAJOS) - previos:
        TRABAJOS.pop(clave, None)


def _cliente():
    cliente = TestClient(app)
    cliente.cookies.set(SESION_COOKIE, _firmar_sesion("adminlocal"))
    return cliente


def _sembrar(entradas):
    """entradas: [(fila, nombre, resultado, observacion)] del curso fijo."""
    for fila, nombre, resultado, observacion in entradas:
        course_state.registrar_resultado_actividad(
            {
                "curso": "Contabilidad I",
                "programa": "Administración de Empresas",
                "hoja": "Curso A",
                "fila_excel": fila,
                "nombre": nombre,
            },
            resultado,
            observacion,
        )


# ============================================================
# MENSAJES DE ERROR
# ============================================================

def test_codigo_conocido_se_traduce_a_espanol():
    assert mensaje_error("ERROR_CURSO_SIN_PLANTILLA") == (
        "El curso no tiene la plantilla precargada en PRIZMA: la actividad no "
        "existe todavía y hay que crearla antes de cargar."
    )
    assert "columna Recurso" in mensaje_error("ERROR_RECURSO_NO_ENCONTRADO")


def test_codigo_desconocido_o_texto_libre_no_se_toca():
    assert mensaje_error("ERROR_INVENTADO") == "ERROR_INVENTADO"
    assert mensaje_error("Timeout 60000ms exceeded") == "Timeout 60000ms exceeded"
    assert mensaje_error("") == ""


def test_extrae_codigo_de_un_texto_con_detalle():
    texto = 'ERROR_PATCH_HTTP_500: respuesta {"detail": "no"}'
    assert extraer_codigo_error(texto) == "ERROR_PATCH_HTTP_"
    assert "PRIZMA rechazó" in mensaje_error(texto)
    assert es_codigo_error(texto)

    assert extraer_codigo_error("algo raro") == ""
    assert not es_codigo_error("algo raro")


def test_todos_los_codigos_del_motor_tienen_traduccion():
    codigos = set()
    for ruta in (RAIZ / "auto_prizma").rglob("*.py"):
        codigos.update(re.findall(r'"(ERROR_[A-Z0-9_]+)"', ruta.read_text(encoding="utf-8")))

    sin_traduccion = sorted(
        codigo
        for codigo in codigos
        if codigo not in MENSAJES_ERROR
        and not codigo.startswith("ERROR_PATCH_HTTP_")  # prefijo variable, ya cubierto
    )
    assert sin_traduccion == [], f"codigos sin mensaje humano: {sin_traduccion}"


# ============================================================
# ESTADO ACUMULADO POR CURSO
# ============================================================

def test_acumula_ok_y_error_entre_cargues():
    _sembrar([
        (5, "Infografía", "OK", ""),
        (6, "Lectura guía", "ERROR", "ERROR_RECURSO_NO_ENCONTRADO"),
        # Reintento fallido de algo ya subido: NO vuelve a contar como faltante.
        (5, "Infografía", "ERROR", "ERROR_BOTON_GUARDAR"),
    ])

    resumen = course_state.resumen_cursos()
    assert len(resumen) == 1
    curso = resumen[0]
    assert (curso["total"], curso["subidas"], curso["faltantes"]) == (2, 1, 1)
    assert curso["curso"] == "Contabilidad I"
    assert curso["programa"] == "Administración de Empresas"

    faltante = curso["detalle_faltantes"][0]
    assert faltante["fila"] == 6
    assert faltante["codigo"] == "ERROR_RECURSO_NO_ENCONTRADO"
    assert "columna Recurso" in faltante["motivo"]  # mensaje humano, no el codigo


def test_preseleccion_solo_marca_faltantes_con_mismo_nombre():
    _sembrar([
        (5, "Infografía de costos", "OK", ""),
        (6, "Lectura guía", "ERROR", "ERROR_RECURSO_NO_ENCONTRADO"),
    ])

    claves, cursos = course_state.preseleccion_faltantes([
        {
            "hoja": "Curso A",
            "curso": "Contabilidad I",
            "actividades": [
                {"fila": 5, "nombre": "Infografía de costos"},  # ya OK: no marcar
                {"fila": 6, "nombre": "Lectura guía"},          # falta: marcar
                {"fila": 7, "nombre": "Nueva"},                 # nunca vista: no marcar
                {"fila": 8, "nombre": "Otra"},                  # no registrada: no marcar
            ],
        }
    ])

    assert claves == [["Curso A", 6]]
    assert cursos == ["Contabilidad I"]


def test_preseleccion_no_marca_si_la_fila_cambio_de_actividad():
    _sembrar([(6, "Lectura guía", "ERROR", "ERROR_RECURSO_NO_ENCONTRADO")])

    claves, _ = course_state.preseleccion_faltantes([
        {
            "hoja": "Curso A",
            "curso": "Contabilidad I",
            "actividades": [{"fila": 6, "nombre": "Otra actividad ahora"}],
        }
    ])

    assert claves == []  # la fila 6 ya no es la misma actividad


def test_claves_faltantes_ignora_filas_de_test():
    _sembrar([
        (6, "Lectura guía", "ERROR", "ERROR_ACTIVIDAD_NO_ENCONTRADA"),
        ("Test 1", "Test Evaluativo: Examen", "ERROR", "ERROR_BOTON_GUARDAR"),
    ])

    claves = course_state.claves_faltantes()
    assert claves == [["Curso A", 6]]  # la fila de test no es reintentable asi


def test_estado_se_persiste_en_disco():
    _sembrar([(6, "Lectura guía", "ERROR", "ERROR_LIMPIANDO_DESCRIPCION")])

    # Recarga desde disco (simula reinicio de la app).
    recargado = course_state._cargar_estado()
    assert recargado, "debio persistir en estado_cursos.json"
    curso = next(iter(recargado.values()))
    item = curso["actividades"]["Curso A|6"]
    assert item["intentos"] == 1
    assert item["codigo"] == "ERROR_LIMPIANDO_DESCRIPCION"
    assert item["motivo"]  # frase humana


# ============================================================
# PAGINA /cursos
# ============================================================

def test_pagina_cursos_vacia():
    html = _cliente().get("/cursos").text
    assert "Todavía no hay cargues registrados" in html


def test_pagina_cursos_muestra_faltantes_con_motivo_humano_y_boton():
    _sembrar([
        (5, "Infografía de costos", "OK", ""),
        (6, "Lectura guía", "ERROR", "ERROR_CURSO_SIN_PLANTILLA"),
        (7, "Reto 1", "ERROR", "ERROR_RECURSO_NO_ENCONTRADO"),
    ])

    html = _cliente().get("/cursos").text

    assert "Contabilidad I" in html
    assert "1 de 3" in html
    assert "Reintentar las 2 pendientes" in html
    # Motivos humanos en la tabla de faltantes...
    assert "plantilla precargada" in html
    assert "columna Recurso" in html
    # ...y los codigos originales visibles (chiquitos) para diagnostico.
    assert "ERROR_CURSO_SIN_PLANTILLA" in html
    assert "Ver las 1 ya subidas" in html


def test_pagina_cursos_marca_curso_completo():
    _sembrar([(5, "Infografía de costos", "OK", "")])

    html = _cliente().get("/cursos").text
    assert "Curso completo" in html
    assert "Todas las actividades de este curso ya quedaron en PRIZMA" in html
    assert "actividad(es) pendientes" not in html  # sin banner de pendientes


def test_pagina_cursos_requiere_sesion():
    cliente = TestClient(app, follow_redirects=False)
    assert cliente.get("/cursos").status_code == 303


# ============================================================
# PRE-SELECCION EN /analizar (reintento sin volver a elegir)
# ============================================================

def _matriz_xlsx():
    from openpyxl import Workbook
    import io

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Curso A"
    hoja["A1"] = "Administración de Empresas"
    hoja["A2"] = "Contabilidad I"
    hoja["A4"] = "Semana correspondiente"
    filas = [
        (1, "Unidad 1", None, "Infografía de costos", "OVI", "Infografía", None),
        (1, "Unidad 1", None, "Lectura guía", "OVI", "PDF descargable", None),
    ]
    for numero_fila, fila in enumerate(filas, start=5):
        for columna, valor in enumerate(fila, start=1):
            if valor is not None:
                hoja.cell(row=numero_fila, column=columna, value=valor)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _zip_recursos():
    import io
    import zipfile

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as archivo:
        archivo.writestr("Infografia_de_costos.h5p", b"h5p")
        archivo.writestr("Lectura guía.pdf", b"%PDF")
    return salida.getvalue()


def _inputs_por_fila(html):
    """{fila: (tag_html, marcada?)} de los checkbox de actividades."""
    salida = {}
    for tag in re.findall(r"<input[^>]*class=\"actividad-seleccion\"[^>]*>", html, re.S):
        clave = re.search(r"value=\"([^\"]+)\"", tag)
        if not clave:
            continue
        import html as _html
        import json
        datos = json.loads(_html.unescape(clave.group(1)))
        salida[int(datos[1])] = ("checked" in tag, tag)
    return salida


def test_analizar_pre_marca_solo_las_que_faltaban():
    _sembrar([
        (5, "Infografía de costos", "OK", ""),            # ya subida
        (6, "Lectura guía", "ERROR", "ERROR_RECURSO_NO_ENCONTRADO"),  # falta
    ])

    cliente = _cliente()
    respuesta = cliente.post(
        "/analizar",
        data={"modo_matriz": "archivo", "ovi": "1"},
        files={
            "matriz_archivo": ("matriz.xlsx", _matriz_xlsx(), "application/octet-stream"),
            "recursos": ("recursos.zip", _zip_recursos(), "application/zip"),
        },
    )

    assert respuesta.status_code == 200
    html = respuesta.text
    inputs = _inputs_por_fila(html)
    assert inputs[5][0] is False, "la ya subida no debe quedar marcada"
    assert inputs[6][0] is True, "la que falta debe quedar marcada"
    assert "Reintento de cargues anteriores" in html
    assert "Quedaron 1 actividad(es) pendientes" in html


def test_analizar_sin_faltantes_lo_deja_como_antes():
    html = _cliente().post(
        "/analizar",
        data={"modo_matriz": "archivo", "ovi": "1"},
        files={
            "matriz_archivo": ("matriz.xlsx", _matriz_xlsx(), "application/octet-stream"),
            "recursos": ("recursos.zip", _zip_recursos(), "application/zip"),
        },
    ).text

    inputs = _inputs_por_fila(html)
    assert inputs and all(marcada for marcada, _ in inputs.values()), (
        "sin historial, todas deben venir marcadas (comportamiento original)"
    )
    assert "Reintento de cargues anteriores" not in html


def test_cargado_y_omitido_cuentan_como_subidas():
    """Regresion: el flujo de Tests escribe 'Cargado'/'Omitido', no 'OK'.

    Ambos significan que el archivo ya esta en PRIZMA; antes se registraban
    como error y /cursos mostraba faltantes falsas. 'Cancelado' si sigue
    contando como pendiente.
    """
    _sembrar([
        (5, "Balance general", "Cargado", ""),
        (6, "Formato APA", "Omitido", "Ya estaba cargado en PRIZMA · se omite para no duplicar"),
        (7, "Portada", "Cancelado", "Detenido por el usuario"),
    ])

    curso = course_state.resumen_cursos()[0]
    assert (curso["total"], curso["subidas"], curso["faltantes"]) == (3, 2, 1)


def test_mensaje_error_conserva_el_detalle_del_motor():
    """El detalle que anexa el motor (archivo pedido, filas repetidas)
    debe llegar al usuario junto con la frase humana."""
    texto = (
        "ERROR_RECURSO_NO_ENCONTRADO: el Excel pide "
        "'PASO A PASO-Secuencia.h5p' pero no está en el ZIP"
    )
    assert extraer_codigo_error(texto) == "ERROR_RECURSO_NO_ENCONTRADO"
    mensaje = mensaje_error(texto)
    assert mensaje.startswith("La fila no tiene recurso")
    assert "PASO A PASO-Secuencia.h5p" in mensaje

    dup = (
        "ERROR_ACTIVIDAD_DUPLICADA: aparece 2 veces en PRIZMA — "
        "«Formulación del problema Semana 3»"
    )
    assert "Semana 3" in mensaje_error(dup)
