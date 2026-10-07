"""Logo y recursos comunes de la interfaz (hoja de estilos y script).

Los archivos viven en static/. Las paginas los piden con ?v=<fecha de
modificacion> (web/layout.asset_url), asi que se pueden guardar en cache.
"""

from fastapi.responses import FileResponse

from auto_prizma.core.application import app
from auto_prizma.core.config import APP_CSS_PATH, APP_JS_PATH, LOGO_PATH

_CACHE_LARGO = {"Cache-Control": "public, max-age=86400"}


@app.get("/favicon.ico")
@app.get("/auto-prizma-logo.png")
def auto_prizma_logo():
    return FileResponse(
        LOGO_PATH,
        media_type="image/png",
        headers=_CACHE_LARGO,
    )


@app.get("/app.css")
def app_css():
    return FileResponse(
        APP_CSS_PATH,
        media_type="text/css; charset=utf-8",
        headers=_CACHE_LARGO,
    )


@app.get("/app.js")
def app_js():
    return FileResponse(
        APP_JS_PATH,
        media_type="application/javascript; charset=utf-8",
        headers=_CACHE_LARGO,
    )
