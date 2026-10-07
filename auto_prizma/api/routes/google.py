"""Rutas para conectar y desconectar la cuenta de Google del usuario.
"""

from fastapi import Request as FastAPIRequest
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from google_auth_oauthlib.flow import Flow
import os

from auto_prizma.core.application import app
from auto_prizma.services.auth import (
    _normalizar_usuario,
    _usuario_actual,
)
from auto_prizma.integrations.google.drive import check_sheet_link
from auto_prizma.integrations.google.oauth import (
    GOOGLE_SCOPES,
    _consumir_estado_oauth,
    _google_client_config,
    _guardar_credenciales_google,
    _guardar_estado_oauth,
    _ruta_token_google,
)
from auto_prizma.web.views import generar_html


# ============================================================
# GOOGLE OAUTH (por usuario)
# ============================================================

@app.get("/google/conectar")
def google_conectar():
    try:
        client_config, redirect_uri = _google_client_config()
        usuario = _usuario_actual()

        if not usuario:
            raise RuntimeError(
                "No hay una sesion activa para conectar Google."
            )

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            autogenerate_code_verifier=True,
        )
        flow.redirect_uri = redirect_uri

        authorization_url, estado_generado = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        _guardar_estado_oauth(
            estado_generado,
            usuario,
            flow.code_verifier,
        )

        return RedirectResponse(
            authorization_url,
            status_code=302,
        )

    except Exception as error:
        return HTMLResponse(
            generar_html(
                error=(
                    "No fue posible iniciar la autorizacion de Google. "
                    + str(error)
                )
            ),
            status_code=500,
        )


@app.get("/google/callback")
def google_callback(request: FastAPIRequest):
    try:
        client_config, redirect_uri = _google_client_config()

        estado = str(request.query_params.get("state") or "").strip()
        error_google = str(
            request.query_params.get("error") or ""
        ).strip()

        if error_google:
            if estado:
                try:
                    _consumir_estado_oauth(estado)
                except RuntimeError:
                    pass

            descripcion = str(
                request.query_params.get("error_description") or ""
            ).strip()
            detalle = descripcion or error_google

            return HTMLResponse(
                generar_html(
                    error=(
                        "Google no autorizo el acceso solicitado. "
                        + detalle
                    )
                ),
                status_code=400,
            )

        codigo = str(request.query_params.get("code") or "").strip()

        if not codigo:
            return HTMLResponse(
                generar_html(
                    error=(
                        "Google no devolvio el codigo de autorizacion. "
                        "Vuelve a pulsar Conectar con Google."
                    )
                ),
                status_code=400,
            )

        datos_estado = _consumir_estado_oauth(estado)
        usuario_del_flujo = datos_estado["usuario"]
        usuario_actual = _usuario_actual()

        if _normalizar_usuario(usuario_actual) != _normalizar_usuario(
            usuario_del_flujo
        ):
            raise RuntimeError(
                "La sesion actual no coincide con la persona que inicio "
                "la autorizacion de Google. Vuelve a conectar tu cuenta."
            )

        flow = Flow.from_client_config(
            client_config,
            scopes=GOOGLE_SCOPES,
            state=estado,
            code_verifier=datos_estado.get("code_verifier") or None,
            autogenerate_code_verifier=False,
        )
        flow.redirect_uri = redirect_uri

        authorization_response = (
            redirect_uri
            + ("?" + request.url.query if request.url.query else "")
        )

        flow.fetch_token(
            authorization_response=authorization_response
        )

        _guardar_credenciales_google(
            flow.credentials,
            usuario_del_flujo,
        )

        return RedirectResponse(
            "/",
            status_code=303,
        )

    except Exception as error:
        return HTMLResponse(
            generar_html(
                error=(
                    "No fue posible completar la autorizacion de Google. "
                    + str(error)
                )
            ),
            status_code=500,
        )


@app.get("/google/validar-matriz")
def google_validar_matriz(url: str = ""):
    """Comprueba el enlace de Google Sheets que se pega en Inicio (JSON)."""
    return JSONResponse(check_sheet_link(url))


@app.post("/google/desconectar")
def google_desconectar():
    try:
        ruta = _ruta_token_google(_usuario_actual())

        if os.path.isfile(ruta):
            os.remove(ruta)
    except OSError:
        pass

    return RedirectResponse(
        "/",
        status_code=303,
    )
