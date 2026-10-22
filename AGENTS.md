# AGENTS.md — Instrucciones para agentes de IA

Runbook operativo para instalar, arrancar y mantener **Auto Prizma Pro** en local. Sigue estos pasos exactos. Lee también `CLAUDE.md` para reglas del código y `GUIA_DETALLADA.md` para detalle funcional.

---

## 1. Contexto del proyecto

- **Stack:** Python 3.12+, FastAPI, Uvicorn, Playwright (Chromium), openpyxl, google-api-python-client.
- **Entrada:** `main.py` arma `app` e importa rutas. Se corre con `uvicorn main:app`.
- **Entorno virtual:** `.venv/` en la raíz. **Siempre** usar su Python/binarios, nunca el del sistema.
- **Datos:** todo vive en `data/` (usuarios, tokens, `historial.json`, reportes CSV). `data/estado_cursos.json` acumula por curso qué actividades ya quedaron en PRIZMA y la causa de las que faltan: lo escribe `auto_prizma/services/course_state.py` desde `guardar_resultado()` y lo usan la página `/cursos` y el pre-marcado de pendientes en `/analizar`. Los códigos `ERROR_*` se traducen con `auto_prizma/services/error_messages.py` (el CSV conserva el código en `Observación` y el texto humano en `Motivo`).
- **Producción:** Railway despliega cada push a `main`. Rama de trabajo del usuario: `Jeremy`.

---

## 2. Comandos exactos (macOS/Linux; en Windows usa `.venv\Scripts\`)

```bash
# Activar entorno (en Windows: .\.venv\Scripts\Activate.ps1)
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# OBLIGATORIO: instalar el navegador. Sin esto los cargues fallan con
# "Chromium no disponible" y la validación contra PRIZMA da
# "No fue posible conectar con PRIZMA".
playwright install chromium

# Arrancar (recarga en caliente)
uvicorn main:app --reload --port 8000
# o, que además carga .env si existe:
./arrancar.sh

# Gestión de usuarios (interactiva; contraseña mínimo 8 caracteres)
python scripts/manage_users.py crear
python scripts/manage_users.py listar
python scripts/manage_users.py clave
python scripts/manage_users.py desactivar
python scripts/manage_users.py activar
python scripts/manage_users.py borrar

# Cerrar la app
kill $(lsof -ti :8000)
```

**Logs:** si arrancaste con `nohup ./arrancar.sh > /tmp/prizma.log 2>&1 &`, revisa `/tmp/prizma.log`.

---

## 3. Reglas críticas (no romper)

1. **Usar el Python del venv**, no el del sistema. `ModuleNotFoundError` = venv no activado.
2. **`playwright install chromium` es obligatorio** tras instalar deps. La versión de Chromium debe corresponder a la de `playwright` en `requirements.txt` (si el caché tiene otra, se reinstala con el mismo comando).
3. **La app NO lee `.env` automáticamente.** Si necesitas variables, expórtalas en la terminal o usa `./arrancar.sh` (las carga con `set -a`).
4. **`.env` está en `.gitignore`** — nunca subir secretos. El ID/secret de Google viven ahí.
5. **PRIZMA producción = `https://admin.prizma.site`.** Para pruebas, define `AUTO_PRIZMA_URL_PRIZMA=https://admin.prizma.solutions` y reinicia. Cuidado: los cargues tocan producción.
6. **Commits en español**, con prefijos `fix:`/`refactor:`/`docs:`/`chore:`/`feat:`.

---

## 4. Variables de entorno (ver `auto_prizma/core/config.py`)

| Variable | Efecto | Default |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | OAuth Google (Sheets/Drive, solo lectura) | vacío (Google deshabilitado) |
| `AUTO_PRIZMA_SECRET` | Firma de cookies de sesión | se genera en `data/secreto_sesion.txt` |
| `AUTO_PRIZMA_COOKIE_SECURE` | `"1"` fuerza cookie Secure | — |
| `AUTO_PRIZMA_URL_PRIZMA` | URL base de PRIZMA | `https://admin.prizma.site` (producción) |
| `AUTO_PRIZMA_DATA_DIR` | Carpeta de datos persistentes | `./data` |
| `AUTO_PRIZMA_MAX_SIMULTANEOS` | Cargues simultáneos (1 o 2; otro = 2) | `2` |

Se leen en CADA llamada (Google y cookie) o al importar (`AUTO_PRIZMA_URL_PRIZMA`, `MAX_SIMULTANEOS`). Para cambiar las de importar: reiniciar la app.

---

## 5. Diagnóstico rápido

| Síntoma | Causa / acción |
|---|---|
| `ModuleNotFoundError: No module named 'google'` | Venv no activado → `source .venv/bin/activate` |
| "Chromium no disponible" (indicador rojo) | `playwright install chromium`; reiniciar la app |
| "No fue posible conectar con PRIZMA para validar el acceso" | Chromium faltante o PRIZMA caído. Verificar con `curl -I https://admin.prizma.site` |
| `ERROR_LIMPIANDO_DESCRIPCION` en cargues | Editor rico de PRIZMA no se limpia. Ver `limpiar_descripcion()` en `auto_prizma/automation/prizma/engine.py` (ya con reintentos + respaldo JS) |
| `ERROR_RECURSO_NO_ENCONTRADO` | La fila del Excel no tiene archivo en la columna Recurso (dato faltante, no bug) |
| Puerto 8000 ocupado | `lsof -i :8000` y matar los PIDs |
| Login rechazado | Bloqueo 120 s tras 5 fallos |

---

## 6. Verificación tras cambios

1. `python -m pytest tests/ -q` → la suite completa debe pasar en verde (incluye `tests/test_course_state.py`).
2. `python -c "import ast; ast.parse(open('auto_prizma/automation/prizma/engine.py').read())"` (sintaxis).
3. Arrancar con `--reload` y comprobar `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/login` → debe dar `200`.
4. Probar el flujo afectado en un entorno **de pruebas** antes de tocar producción.
