"""Pruebas del detector de duplicados del flujo de Tests.

Al reintentar un cargue, la automatizacion revisa la lista de Tests de PRIZMA
antes de presionar 'Crear' y omite los titulos que ya estan guardados
(funcion coincide_titulo_test).
"""

from auto_prizma.evaluative_tests.automation import coincide_titulo_test


def test_detecta_titulo_ignorando_mayusculas_y_acentos():
    texto_fila = "Fundamentos de la Arquitectura del Computador\tV2305\tActivo"
    assert coincide_titulo_test(
        texto_fila, "fundamentos de la arquitectura del computador"
    )
    assert coincide_titulo_test(
        texto_fila, "FUNDAMENTOS DE LA ARQUITECTURA DEL COMPUTADOR"
    )


def test_espacios_de_mas_no_cuentan_como_diferente():
    texto_fila = "Procesador  y ejecución   de instrucciones"
    assert coincide_titulo_test(texto_fila, "Procesador y ejecución de instrucciones")


def test_no_coincide_con_un_test_de_otro_titulo():
    texto_fila = "Procesador y ejecución de instrucciones"
    assert not coincide_titulo_test(
        texto_fila, "Fundamentos de la arquitectura del computador"
    )


def test_titulo_vacio_o_demasiado_corto_no_marca_duplicado():
    # Un vacio o un titulo minusculo no debe convertir todo en "omitido".
    assert not coincide_titulo_test("cualquier texto en la pagina", "")
    assert not coincide_titulo_test("cualquier texto en la pagina", "abc")
