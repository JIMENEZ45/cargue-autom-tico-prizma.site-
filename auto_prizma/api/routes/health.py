"""Estado real del servicio (Chromium y PRIZMA) para la interfaz.
"""

from fastapi.responses import JSONResponse

from auto_prizma.core.application import app
from auto_prizma.services.health import service_status


@app.get("/estado-servicio")
def estado_servicio():
    """Lo pide static/app.js al cargar cada pagina (y cada 5 minutos).

    Es `def` (no async) porque la comprobacion de Chromium usa Playwright
    sincrono y puede tardar un momento: corre en el threadpool.
    """
    return JSONResponse(service_status(), headers={"Cache-Control": "no-store"})
