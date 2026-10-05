# Auto Prizma Pro — Interfaz de cargue automático

Aplicación web (FastAPI + Playwright) que carga actividades y tests evaluativos en PRIZMA a partir de una matriz (Excel, CSV o Google Sheets) y un ZIP o carpeta de Drive con los recursos.

## Estructura

```
main.py                     Punto de entrada: arma la app (uvicorn main:app)
auto_prizma/                Código de la aplicación web
  aplicacion.py             Instancia FastAPI compartida
  config.py                 Rutas de carpetas de trabajo y de datos
  sesiones.py               Usuarios, contraseñas, bloqueo por intentos y cookies de sesión
  google_oauth.py           Conexión OAuth con Google por usuario
  drive.py                  Lectura de enlaces en Google Sheets y listado de carpetas de Drive
  drive_zip.py              Relación Drive ↔ ZIP, avisos y prevalidación rápida
  integracion_motor.py      Ajustes que se aplican sobre motor_prizma al arrancar
  trabajos.py               Estado de cargues, historial, reportes y cola de ejecución
  analisis.py               Lectura de la matriz (CSV/Excel/Sheets) y análisis de matriz y ZIP
  vistas.py                 HTML de la página principal de análisis y cargue
  rutas/                    Rutas web
    estaticos.py            Logo, estilos y script de tema
    sesion.py               Middleware de sesión, login, salir y cambio de contraseña
    google.py               Conectar / desconectar Google
    analisis.py             Inicio y análisis previo al cargue
    cargues.py              Iniciar, seguir, cancelar y estado de cargues
    reportes.py             Historial, reportes guardados y descargas
motor_prizma.py             Automatización de PRIZMA con Playwright (lectura de la matriz y cargue de actividades)
drive_resource_policy.py    Reglas para decidir qué recurso de Drive corresponde a cada actividad
gestionar_usuarios.py       CLI para administrar los usuarios de la interfaz
tests_evaluativos/          Módulo de tests evaluativos (cuestionarios en PRIZMA a partir de un .docx)
  models.py                 Estructuras de datos del documento (tests, secciones, preguntas)
  parser.py                 Lectura del .docx y conversión a esas estructuras
  validation.py             Validación del documento (errores y advertencias)
  serializer.py             Exportación a JSON
  automation.py             Automatización de PRIZMA con Playwright para crear los tests
  estado.py                 Estado en memoria de los trabajos y credenciales de PRIZMA
  vistas.py                 HTML del módulo (layout, revisión y tarjeta de estado)
  ejecucion.py              Ejecución del cargue de tests en segundo plano
  web.py                    Rutas /tests/...
tests/                      Pruebas automáticas (pytest)
scripts/                    Utilidades manuales (p. ej. probar la conexión con PRIZMA)
static/                     Archivos estáticos (logo)
uploads/ temp/ resultados/  Archivos de trabajo generados en ejecución (no se versionan)
data/                       Usuarios, tokens, historial y reportes (no se versiona; contiene secretos)
```

### Flujo general

1. El usuario inicia sesión (`rutas/sesion.py`) y, si lo necesita, conecta su cuenta de Google (`rutas/google.py`).
2. En el inicio sube o enlaza la matriz y el ZIP / carpeta de Drive; `rutas/analisis.py` los analiza con `analisis.py`, `drive.py` y `drive_zip.py` y muestra el resultado (`vistas.py`).
3. Al iniciar el cargue, `rutas/cargues.py` lo pone en la cola de `trabajos.py`, que ejecuta `motor_prizma.py` (con los ajustes de `integracion_motor.py`).
4. Al terminar se guarda el reporte y el historial, consultables desde `rutas/reportes.py`.

Tests evaluativos (`/tests`): el .docx se lee con `parser.py` y se valida con `validation.py`; el usuario lo revisa y corrige en pantalla y luego `ejecucion.py` lo carga en PRIZMA con `automation.py`. Un test también puede cargarse junto con un cargue de actividades (`_ejecutar_test_en_cargue` en `auto_prizma/trabajos.py`).

## Ejecutar en local

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\playwright install chromium
.\.venv\Scripts\uvicorn main:app --reload
```

Crear el primer usuario:

```powershell
.\.venv\Scripts\python gestionar_usuarios.py crear
```

## Pruebas

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Docker

```powershell
docker build -t auto-prizma .
docker run -p 8000:8000 -v ${PWD}/data:/app/data auto-prizma
```

## Respaldos

No guardes copias como `main_backup_*.py`: el historial de git ya conserva cada versión (`git log -- main.py`, `git show <commit>:main.py`).
