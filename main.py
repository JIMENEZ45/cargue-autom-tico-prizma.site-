"""Punto de entrada de Auto Prizma Pro.

Arma la aplicacion web a partir del paquete auto_prizma:

    uvicorn main:app

El orden de los imports importa: primero se aplican los ajustes sobre
motor_prizma y luego se registran las rutas en el mismo orden de siempre.
El modulo de tests evaluativos se monta al final.
"""

from auto_prizma.aplicacion import app

# Ajustes sobre motor_prizma (hoja objetivo y recursos prevalidados).
import auto_prizma.integracion_motor  # noqa: F401

# Rutas. Cada modulo registra sus rutas sobre `app` al importarse.
import auto_prizma.rutas.estaticos  # noqa: F401
import auto_prizma.rutas.sesion  # noqa: F401
import auto_prizma.rutas.google  # noqa: F401
import auto_prizma.rutas.analisis  # noqa: F401
import auto_prizma.rutas.cargues  # noqa: F401
import auto_prizma.rutas.reportes  # noqa: F401

from auto_prizma.config import RESULTADOS_DIR
from auto_prizma.google_oauth import _descargar_google_docx_para_tests
from auto_prizma.rutas.reportes import _historial_del_usuario
from auto_prizma.trabajos import TRABAJOS


# ============================================================
# MODULO TESTS
# ============================================================

from test_module.web import router as test_module_router

app.state.test_google_loader = _descargar_google_docx_para_tests
app.state.trabajos_cargue = TRABAJOS
app.state.historial_cargues = _historial_del_usuario
app.state.resultados_dir = RESULTADOS_DIR
app.include_router(test_module_router)
