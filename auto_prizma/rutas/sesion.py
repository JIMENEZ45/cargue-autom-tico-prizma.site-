"""Middleware que exige sesion, login, cierre de sesion y cambio de contrasena.
"""

from fastapi import (
    Form,
    Request as FastAPIRequest,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
import html

from auto_prizma.aplicacion import app
from auto_prizma.sesiones import (
    SESION_COOKIE,
    SESION_HORAS,
    USUARIO_ACTUAL,
    _autenticar,
    _bloqueado,
    _cargar_usuarios,
    _cookie_segura,
    _crear_usuario,
    _firmar_sesion,
    _limpiar_fallos,
    _nombre_visible,
    _normalizar_usuario,
    _registrar_fallo,
    _usuario_actual,
    _usuario_de_request,
)


# ============================================================
# GOOGLE OAUTH - CONECTAR / CALLBACK / DESCONECTAR
# ============================================================

# ============================================================
# LOGIN
# ============================================================

RUTAS_PUBLICAS = {
    "/login",
    "/salir",
    "/favicon.ico",
    "/auto-prizma-logo.png",
    "/estilos-responsive.css",
    "/tema.js",
}


def _pagina_login(error="", usuario_previo=""):
    plantilla = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ingresar - Cargue Prizma Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#f7f8fc;
color:#101828;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.caja{background:#fff;border:1px solid #e4e7ec;border-radius:18px;padding:36px 32px;
width:100%;max-width:400px;box-shadow:0 12px 40px rgba(16,24,40,.07)}
.marca{display:flex;align-items:center;gap:12px;margin-bottom:26px}
.logo{width:42px;height:42px;border-radius:12px;background:#1570ef;display:flex;
align-items:center;justify-content:center}
.logo svg{width:26px;height:26px;fill:#fff}
.marca strong{display:block;font-size:16px}
.marca span{font-size:12px;color:#667085}
h1{font-size:20px;margin-bottom:6px}
.sub{font-size:13px;color:#667085;margin-bottom:22px}
label{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
input{width:100%;padding:11px 13px;border:1px solid #d0d5dd;border-radius:10px;
font-size:14px;margin-bottom:16px;font-family:inherit}
input:focus{outline:none;border-color:#1570ef;box-shadow:0 0 0 3px rgba(21,112,239,.12)}
button{width:100%;padding:12px;background:#1570ef;color:#fff;border:none;
border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit}
button:hover{background:#1059c4}
.error{background:#fef3f2;border:1px solid #fecdca;color:#b42318;padding:11px 13px;
border-radius:10px;font-size:13px;margin-bottom:18px}
.pie{margin-top:20px;font-size:12px;color:#98a2b3;text-align:center;line-height:1.6}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head><body>
<form class="caja" method="post" action="/login">
  <div class="marca">
    <div class="logo"><img class="logo-imagen" src="/auto-prizma-logo.png" alt="Logo Cargue Prizma Pro"></div>
    <div><strong>Cargue Prizma Pro</strong><span>Cargue Prizma</span></div>
  </div>
  <h1>Ingresar</h1>
  <p class="sub">Usa el usuario que te entregaron.</p>
  __ERROR__
  <label for="usuario">Usuario</label>
  <input id="usuario" name="usuario" autocomplete="username" required
         value="__USUARIO__" autofocus>
  <label for="contrasena">Contrasena</label>
  <input id="contrasena" name="contrasena" type="password"
         autocomplete="current-password" required>
  <button type="submit">Entrar</button>
  <p class="pie">Cada persona ve unicamente sus propios cargues,<br>su historial y sus reportes.</p>
</form></body></html>"""

    bloque_error = ""
    if error:
        bloque_error = '<div class="error">' + html.escape(str(error)) + "</div>"

    return plantilla.replace(
        "__ERROR__",
        bloque_error,
    ).replace(
        "__USUARIO__",
        html.escape(str(usuario_previo or ""), quote=True),
    )


@app.middleware("http")
async def exigir_sesion(request: FastAPIRequest, call_next):
    ruta = request.url.path

    if ruta in RUTAS_PUBLICAS:
        return await call_next(request)

    usuario = _usuario_de_request(request)

    if not usuario:
        acepta = str(request.headers.get("accept") or "")

        if ruta.startswith("/estado/") or "application/json" in acepta:
            return JSONResponse(
                {"error": "Sesion expirada", "login": "/login"},
                status_code=401,
            )

        return RedirectResponse("/login", status_code=303)

    testigo = USUARIO_ACTUAL.set(usuario)
    request.state.usuario = usuario

    try:
        return await call_next(request)
    finally:
        USUARIO_ACTUAL.reset(testigo)


@app.get("/login", response_class=HTMLResponse)
def login_formulario(request: FastAPIRequest):
    if _usuario_de_request(request):
        return RedirectResponse("/", status_code=303)

    return HTMLResponse(_pagina_login())


@app.post("/login", response_class=HTMLResponse)
def login_enviar(
    request: FastAPIRequest,
    usuario: str = Form(...),
    contrasena: str = Form(...),
):
    usuario = _normalizar_usuario(usuario)

    origen = str(
        request.client.host if request.client else "desconocido"
    )
    clave_intentos = usuario + "|" + origen

    espera = _bloqueado(clave_intentos)

    if espera:
        return HTMLResponse(
            _pagina_login(
                "Demasiados intentos fallidos. Espera "
                + str(espera)
                + " segundos.",
                usuario,
            ),
            status_code=429,
        )

    if not _cargar_usuarios():
        return HTMLResponse(
            _pagina_login(
                "Todavia no hay usuarios creados. Ejecuta: "
                "python gestionar_usuarios.py crear",
                usuario,
            ),
            status_code=503,
        )

    autenticado = _autenticar(usuario, contrasena)

    if not autenticado:
        _registrar_fallo(clave_intentos)
        return HTMLResponse(
            _pagina_login("Usuario o contrasena incorrectos.", usuario),
            status_code=401,
        )

    _limpiar_fallos(clave_intentos)

    respuesta = RedirectResponse("/", status_code=303)
    respuesta.set_cookie(
        SESION_COOKIE,
        _firmar_sesion(autenticado),
        max_age=SESION_HORAS * 3600,
        httponly=True,
        samesite="lax",
        secure=_cookie_segura(),
        path="/",
    )

    print("Login OK:", autenticado, "desde", origen)

    return respuesta


@app.get("/salir")
@app.post("/salir")
def cerrar_sesion():
    respuesta = RedirectResponse("/login", status_code=303)
    respuesta.delete_cookie(SESION_COOKIE, path="/")
    return respuesta


@app.get("/cambiar-clave", response_class=HTMLResponse)
def cambiar_clave_formulario(mensaje: str = "", error: str = ""):
    plantilla = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cambiar contrasena - Cargue Prizma Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#f7f8fc;color:#101828;
min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.caja{background:#fff;border:1px solid #e4e7ec;border-radius:18px;padding:34px 32px;
width:100%;max-width:400px;box-shadow:0 12px 40px rgba(16,24,40,.07)}
h1{font-size:19px;margin-bottom:6px}
.sub{font-size:13px;color:#667085;margin-bottom:20px}
label{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
input{width:100%;padding:11px 13px;border:1px solid #d0d5dd;border-radius:10px;
font-size:14px;margin-bottom:16px;font-family:inherit}
button{width:100%;padding:12px;background:#1570ef;color:#fff;border:none;
border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;font-family:inherit}
.error{background:#fef3f2;border:1px solid #fecdca;color:#b42318;padding:11px;
border-radius:10px;font-size:13px;margin-bottom:16px}
.ok{background:#ecfdf3;border:1px solid #abefc6;color:#067647;padding:11px;
border-radius:10px;font-size:13px;margin-bottom:16px}
.volver{display:block;text-align:center;margin-top:16px;font-size:13px;color:#667085}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head><body>
<form class="caja" method="post" action="/cambiar-clave">
  <h1>Cambiar contrasena</h1>
  <p class="sub">Sesion de <strong>__USUARIO__</strong></p>
  __AVISO__
  <label>Contrasena actual</label>
  <input name="actual" type="password" autocomplete="current-password" required>
  <label>Nueva contrasena</label>
  <input name="nueva" type="password" autocomplete="new-password" required
         minlength="8">
  <label>Repite la nueva</label>
  <input name="repetir" type="password" autocomplete="new-password" required
         minlength="8">
  <button type="submit">Guardar</button>
  <a class="volver" href="/">Volver al inicio</a>
</form></body></html>"""

    aviso = ""
    if error:
        aviso = '<div class="error">' + html.escape(str(error)) + "</div>"
    elif mensaje:
        aviso = '<div class="ok">' + html.escape(str(mensaje)) + "</div>"

    return HTMLResponse(
        plantilla.replace(
            "__USUARIO__",
            html.escape(_nombre_visible(_usuario_actual())),
        ).replace("__AVISO__", aviso)
    )


@app.post("/cambiar-clave", response_class=HTMLResponse)
def cambiar_clave_enviar(
    actual: str = Form(...),
    nueva: str = Form(...),
    repetir: str = Form(...),
):
    usuario = _usuario_actual()

    if not _autenticar(usuario, actual):
        return cambiar_clave_formulario(
            error="La contrasena actual no es correcta."
        )

    if nueva != repetir:
        return cambiar_clave_formulario(
            error="La nueva contrasena y su repeticion no coinciden."
        )

    try:
        _crear_usuario(usuario, nueva)
    except ValueError as problema:
        return cambiar_clave_formulario(error=str(problema))

    return cambiar_clave_formulario(
        mensaje="Contrasena actualizada."
    )
