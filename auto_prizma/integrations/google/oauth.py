"""Conexion OAuth con Google por usuario: estados, tokens y credenciales.
"""

from io import BytesIO
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import re
import threading
from datetime import datetime

from auto_prizma.core.config import (
    DATA_DIR,
    GOOGLE_AUTH_URI,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URI,
    TOKENS_DIR,
    google_client_id,
    google_client_secret,
    google_redirect_uri,
)
from auto_prizma.services.auth import (
    _normalizar_usuario,
    _slug_usuario,
    _usuario_actual,
)


# ============================================================
# GOOGLE OAUTH
# ============================================================

# GOOGLE_SCOPES vive en auto_prizma.core.config (se reexporta desde aqui).

# Token compartido de la version anterior. Ya NO se usa: cada persona
# tiene el suyo en data/tokens/. Se avisa para que se borre.
GOOGLE_TOKEN_COMPARTIDO_ANTIGUO = os.path.join(
    DATA_DIR,
    "google_token.json",
)

if os.path.isfile(GOOGLE_TOKEN_COMPARTIDO_ANTIGUO):
    print(
        "AVISO: existe data/google_token.json (token compartido de la version "
        "anterior). Ya no se usa. Revoca ese acceso en "
        "https://myaccount.google.com/permissions y borra el archivo."
    )


def _ruta_token_google(usuario):
    return os.path.join(
        TOKENS_DIR,
        _slug_usuario(usuario) + ".json",
    )


GOOGLE_OAUTH_STATES = {}
GOOGLE_OAUTH_LOCK = threading.Lock()
GOOGLE_OAUTH_STATE_TTL_SEGUNDOS = 10 * 60


def _guardar_estado_oauth(state, usuario, code_verifier):
    state = str(state or "").strip()
    usuario = _normalizar_usuario(usuario)

    if not state or not usuario:
        raise RuntimeError(
            "No fue posible iniciar de forma segura la autorizacion de Google."
        )

    ahora = datetime.now().timestamp()

    with GOOGLE_OAUTH_LOCK:
        expirados = []

        for clave, datos in GOOGLE_OAUTH_STATES.items():
            creado = float(datos.get("creado_en") or 0)
            if ahora - creado > GOOGLE_OAUTH_STATE_TTL_SEGUNDOS:
                expirados.append(clave)

        for clave in expirados:
            GOOGLE_OAUTH_STATES.pop(clave, None)

        GOOGLE_OAUTH_STATES[state] = {
            "usuario": usuario,
            "code_verifier": str(code_verifier or ""),
            "creado_en": ahora,
        }


def _consumir_estado_oauth(state):
    state = str(state or "").strip()

    if not state:
        raise RuntimeError(
            "Google no devolvio el estado de seguridad de la autorizacion."
        )

    with GOOGLE_OAUTH_LOCK:
        datos = GOOGLE_OAUTH_STATES.pop(state, None)

    if not datos:
        raise RuntimeError(
            "La autorizacion de Google ya no es valida o ya fue utilizada. "
            "Vuelve a pulsar Conectar con Google."
        )

    creado = float(datos.get("creado_en") or 0)
    antiguedad = datetime.now().timestamp() - creado

    if antiguedad > GOOGLE_OAUTH_STATE_TTL_SEGUNDOS:
        raise RuntimeError(
            "La autorizacion de Google expiro. "
            "Vuelve a pulsar Conectar con Google."
        )

    return datos


def _google_client_config():
    client_id = google_client_id()
    client_secret = google_client_secret()
    redirect_uri = google_redirect_uri()

    faltantes = []

    if not client_id:
        faltantes.append("GOOGLE_CLIENT_ID")

    if not client_secret:
        faltantes.append("GOOGLE_CLIENT_SECRET")

    if not redirect_uri:
        faltantes.append("GOOGLE_REDIRECT_URI")

    if faltantes:
        raise RuntimeError(
            "Faltan variables de entorno de Google: "
            + ", ".join(faltantes)
        )

    if (
        redirect_uri.startswith("http://127.0.0.1")
        or redirect_uri.startswith("http://localhost")
    ):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [redirect_uri],
        }
    }, redirect_uri


def _guardar_credenciales_google(credenciales, usuario=None):
    usuario = usuario or _usuario_actual()

    if not usuario:
        raise RuntimeError(
            "No hay sesion activa para guardar el token de Google."
        )

    destino = _ruta_token_google(usuario)
    temporal = destino + ".tmp"

    with open(
        temporal,
        "w",
        encoding="utf-8",
    ) as archivo:
        archivo.write(
            credenciales.to_json()
        )

    os.replace(
        temporal,
        destino,
    )


def _cargar_credenciales_google(usuario=None):
    usuario = usuario or _usuario_actual()

    if not usuario:
        return None

    ruta = _ruta_token_google(usuario)

    if not os.path.isfile(ruta):
        return None

    try:
        credenciales = Credentials.from_authorized_user_file(
            ruta,
            GOOGLE_SCOPES,
        )

        if (
            credenciales.expired
            and credenciales.refresh_token
        ):
            credenciales.refresh(
                GoogleAuthRequest()
            )

            _guardar_credenciales_google(
                credenciales,
                usuario,
            )

        if not credenciales.valid:
            return None

        return credenciales

    except Exception:
        return None


def _google_conectado(usuario=None):
    return (
        _cargar_credenciales_google(usuario)
        is not None
    )


def _descargar_google_docx_para_tests(url_google_doc, usuario=None):
    """Exporta un Google Doc privado como DOCX para el parser de tests."""
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", str(url_google_doc or ""))
    if not match:
        raise ValueError("El enlace de Google Docs no tiene un ID válido.")

    credenciales = _cargar_credenciales_google(usuario)
    if credenciales is None:
        raise RuntimeError("Conecta Google desde Inicio antes de usar un documento privado.")

    servicio = build("drive", "v3", credentials=credenciales, cache_discovery=False)
    solicitud = servicio.files().export_media(
        fileId=match.group(1),
        mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    contenido = BytesIO()
    descarga = MediaIoBaseDownload(contenido, solicitud)
    completada = False
    while not completada:
        _, completada = descarga.next_chunk()

    return contenido.getvalue(), "google_doc_" + match.group(1) + ".docx"
