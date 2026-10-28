"""Punto de entrada de Auto Prizma Pro.

Arma la aplicacion web a partir del paquete auto_prizma:

    uvicorn main:app

El orden de los imports importa: primero se aplican los ajustes sobre el
motor de PRIZMA (auto_prizma.automation.prizma.engine) y luego se registran
las rutas en el mismo orden de siempre. El modulo de tests evaluativos se
monta al final.
"""

from auto_prizma.core.application import app

# Ajustes sobre el motor de PRIZMA (hoja objetivo y recursos prevalidados).
import auto_prizma.automation.prizma.engine_overrides  # noqa: F401

# Rutas. Cada modulo registra sus rutas sobre `app` al importarse.
import auto_prizma.api.routes.static_files  # noqa: F401
import auto_prizma.api.routes.auth  # noqa: F401
import auto_prizma.api.routes.google  # noqa: F401
import auto_prizma.api.routes.analysis  # noqa: F401
import auto_prizma.api.routes.uploads  # noqa: F401
import auto_prizma.api.routes.reports  # noqa: F401
import auto_prizma.api.routes.courses  # noqa: F401
import auto_prizma.api.routes.auditor  # noqa: F401
import auto_prizma.api.routes.health  # noqa: F401
import auto_prizma.api.routes.moodle_resources  # noqa: F401

from auto_prizma.core.config import PRIZMA_BASE_URL, PRIZMA_ES_PRODUCCION, RESULTADOS_DIR, local_login_user
from auto_prizma.integrations.google.oauth import _descargar_google_docx_para_tests
from auto_prizma.services.history import _historial_del_usuario
from auto_prizma.services.upload_jobs import TRABAJOS


# ============================================================
# MODULO TESTS
# ============================================================

from auto_prizma.evaluative_tests.routes import router as tests_evaluativos_router

app.state.test_google_loader = _descargar_google_docx_para_tests
app.state.trabajos_cargue = TRABAJOS
app.state.historial_cargues = _historial_del_usuario
app.state.resultados_dir = RESULTADOS_DIR
app.include_router(tests_evaluativos_router)

print(
    "PRIZMA:",
    PRIZMA_BASE_URL,
    "(produccion)" if PRIZMA_ES_PRODUCCION else "(AMBIENTE DE PRUEBAS)",
)

if local_login_user():
    print(
        "LOGIN DESACTIVADO en este equipo (127.0.0.1): se entra como",
        repr(local_login_user()),
        "| desde otra IP se sigue pidiendo usuario y contrasena",
    )
