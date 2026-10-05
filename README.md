# Auto Prizma Pro — Interfaz de cargue automático

Aplicación web (FastAPI + Playwright) que carga actividades y tests evaluativos en PRIZMA a partir de una matriz (Excel, CSV o Google Sheets) y un ZIP o carpeta de Drive con los recursos.

## Estructura

```
main.py                  App FastAPI: login, Google OAuth, prevalidación Drive/ZIP, cola de cargues, páginas HTML
motor_prizma.py          Automatización de PRIZMA con Playwright (lectura de la matriz y cargue de actividades)
drive_resource_policy.py Reglas para decidir qué recurso de Drive corresponde a cada actividad
gestionar_usuarios.py    CLI para administrar los usuarios de la interfaz
test_module/             Módulo de tests evaluativos (parser de .docx, validación, automatización y rutas web)
tests/                   Pruebas automáticas (pytest)
scripts/                 Utilidades manuales (p. ej. probar la conexión con PRIZMA)
static/                  Archivos estáticos (logo)
uploads/ temp/ resultados/  Archivos de trabajo generados en ejecución (no se versionan)
data/                    Usuarios, tokens, historial y reportes (no se versiona; contiene secretos)
```

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
