"""Configuracion comun de pytest.

Los tests usan un directorio de datos temporal para no leer ni escribir
usuarios, tokens, historial o reportes reales de data/.
"""

import os
import tempfile

# Debe definirse antes de que cualquier test importe main.
os.environ["AUTO_PRIZMA_DATA_DIR"] = tempfile.mkdtemp(prefix="auto_prizma_tests_")

import main  # noqa: E402

main._crear_usuario("adminlocal", "clave-de-pruebas", "Admin local")
