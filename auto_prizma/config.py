"""Carpetas de trabajo (uploads, temp) y de datos (usuarios, tokens, historial, reportes).
"""

import os


# ============================================================
# CARPETAS
# ============================================================

# Raiz del proyecto (carpeta que contiene main.py), un nivel arriba de este paquete.
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

LOGO_PATH = os.path.join(
    BASE_DIR,
    "static",
    "auto_prizma_logo.png",
)

UPLOADS_DIR = os.path.join(
    BASE_DIR,
    "uploads",
)

TEMP_DIR = os.path.join(
    BASE_DIR,
    "temp",
)

DATA_DIR = os.environ.get(
    "AUTO_PRIZMA_DATA_DIR",
    os.path.join(BASE_DIR, "data"),
)

RESULTADOS_DIR = os.path.join(
    DATA_DIR,
    "reportes",
)

HISTORIAL_PATH = os.path.join(
    DATA_DIR,
    "historial.json",
)

USUARIOS_PATH = os.path.join(
    DATA_DIR,
    "usuarios.json",
)

TOKENS_DIR = os.path.join(
    DATA_DIR,
    "tokens",
)

SECRETO_PATH = os.path.join(
    DATA_DIR,
    "secreto_sesion.txt",
)


for carpeta in [
    UPLOADS_DIR,
    TEMP_DIR,
    DATA_DIR,
    RESULTADOS_DIR,
    TOKENS_DIR,
]:

    os.makedirs(
        carpeta,
        exist_ok=True,
    )
