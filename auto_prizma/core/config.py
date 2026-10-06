"""Configuracion central de Auto Prizma Pro.

Reune en un solo lugar las carpetas de trabajo y de datos, las variables de
entorno, los parametros de sesion, los limites de Google/Drive, la cola de
cargues, las URLs de PRIZMA y la configuracion del navegador.

Los modulos importan desde aqui los valores con el mismo nombre que usaban
antes, para no cambiar su comportamiento.
"""

import os
from zoneinfo import ZoneInfo


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================
#
# Variables soportadas (ver .env.example):
#   AUTO_PRIZMA_DATA_DIR        carpeta de datos persistentes (por defecto ./data)
#   AUTO_PRIZMA_SECRET          clave HMAC para firmar las cookies de sesion
#   AUTO_PRIZMA_COOKIE_SECURE   "1" fuerza la cookie Secure
#   AUTO_PRIZMA_MAX_SIMULTANEOS limite de cargues simultaneos (1 o 2)
#   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI
#
# Las variables de Google y de la cookie se leen en CADA llamada (no al
# importar), igual que antes de centralizarlas.


def env_str(nombre):
    """Devuelve el valor de una variable de entorno sin espacios ("" si no existe)."""
    return str(os.environ.get(nombre) or "").strip()


def google_client_id():
    return env_str("GOOGLE_CLIENT_ID")


def google_client_secret():
    return env_str("GOOGLE_CLIENT_SECRET")


def google_redirect_uri():
    return env_str("GOOGLE_REDIRECT_URI")


def session_secret_from_env():
    """Clave de firma de cookies definida por entorno ("" si no existe)."""
    return env_str("AUTO_PRIZMA_SECRET")


def cookie_secure_forced():
    """True cuando AUTO_PRIZMA_COOKIE_SECURE vale exactamente "1"."""
    return env_str("AUTO_PRIZMA_COOKIE_SECURE") == "1"


# ============================================================
# CARPETAS
# ============================================================

# Raiz del proyecto (carpeta que contiene main.py): este archivo vive en
# auto_prizma/core/config.py, por eso se suben tres niveles.
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
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


# ============================================================
# SESIONES Y USUARIOS
# ============================================================

SESION_COOKIE = "ap_sesion"
SESION_HORAS = 12
PBKDF2_ITERACIONES = 240000

# Bloqueo de login: tras MAX_INTENTOS fallos (por usuario + IP) se espera
# BLOQUEO_SEGUNDOS antes de volver a intentar.
MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 120


# ============================================================
# GOOGLE (OAUTH, SHEETS Y DRIVE)
# ============================================================

# Solo lectura: la app nunca modifica archivos de Google.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

# Tamano maximo de la matriz exportada desde Google Sheets.
GOOGLE_SHEETS_MAX_BYTES = 50 * 1024 * 1024

# Peticiones por lote al consultar metadatos en Drive.
DRIVE_BATCH_MAX = 100

# Profundidad maxima al recorrer subcarpetas de Drive.
DRIVE_PROFUNDIDAD_MAX = 3


# ============================================================
# CARGUES
# ============================================================

ZONA_HORARIA_COLOMBIA = ZoneInfo("America/Bogota")


def _resolver_max_cargues_simultaneos(valor):
    """Seguridad operativa: nunca mas de 2 Chromium de cargue a la vez.

    AUTO_PRIZMA_MAX_SIMULTANEOS puede bajarlo a 1; 0, invalidos o >2 vuelven a 2.
    """
    try:
        limite = int(valor)
    except (TypeError, ValueError):
        return 2

    if limite == 1:
        return 1

    return 2


MAX_CARGUES_SIMULTANEOS = _resolver_max_cargues_simultaneos(
    os.environ.get("AUTO_PRIZMA_MAX_SIMULTANEOS")
)


# ============================================================
# PRIZMA Y NAVEGADOR
# ============================================================

PRIZMA_BASE_URL = "https://admin.prizma.site"
URL_PRIZMA = PRIZMA_BASE_URL + "/inicio-sesion"

# Argumentos de Chromium usados por todas las automatizaciones headless.
# Se copian (list(...)) en cada uso para que nadie modifique el original.
CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]

VIEWPORT_NAVEGADOR = {"width": 1440, "height": 900}

# Reintentos al abrir la sesion de PRIZMA al INICIO de un cargue: segundos de
# espera antes de cada reintento (2 esperas = 3 intentos en total). Solo se
# reintentan fallos momentaneos (timeouts, navegador caido), nunca un login
# rechazado.
PRIZMA_ESPERAS_REINTENTO_SESION = (5, 15)

# Politica TEMPORAL del campo "Html" (decision del usuario, 2026-10-06):
# PRIZMA no permite guardar un H5P si el campo Html de la actividad tiene
# contenido. Mientras se carguen recursos H5P, True = el motor vacia el Html
# antes de guardar y deja el contenido previo en el reporte. Cuando se deje de
# usar H5P y se implemente HTML, poner False: el motor cancelara sin guardar y
# reportara ERROR_HTML_Y_H5P para revisar a mano.
PRIZMA_VACIAR_HTML_CON_H5P = True
