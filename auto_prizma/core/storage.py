"""Lectura y escritura de archivos de datos (JSON y texto) en disco.

La escritura es atomica: se escribe "<ruta>.tmp" y luego se reemplaza el
destino con os.replace, para que un corte a mitad de escritura nunca deje
un archivo de datos a medias (usuarios, historial, tokens).
"""

import json
import os


def read_json(path, default, expected_type, errors=(OSError, json.JSONDecodeError)):
    """Lee un archivo JSON.

    Args:
        path: ruta del archivo.
        default: valor que se devuelve si el archivo no existe, no se puede
            leer o su contenido no es del tipo esperado.
        expected_type: tipo que debe tener el contenido (por ejemplo dict o list).
        errors: excepciones que se tratan como "archivo ilegible" y devuelven
            `default`. Cualquier otra excepcion se propaga.

    Returns:
        El contenido del JSON o `default`.
    """
    if not os.path.isfile(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except errors:
        return default

    return datos if isinstance(datos, expected_type) else default


def write_text_atomic(path, text):
    """Escribe texto UTF-8 de forma atomica (archivo temporal + os.replace)."""
    temporal = path + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:
        archivo.write(text)

    os.replace(temporal, path)


def write_json_atomic(path, data):
    """Escribe JSON legible (UTF-8, sin escapar acentos, indentado) de forma atomica."""
    temporal = path + ".tmp"

    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(data, archivo, ensure_ascii=False, indent=2)

    os.replace(temporal, path)
