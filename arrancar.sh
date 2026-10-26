#!/usr/bin/env bash
# Arranca Auto Prizma Pro con lo minimo necesario.
#
# La app NO lee .env automaticamente, por eso las variables se exportan
# aqui. Para correr la app basica NO se necesita ninguna: todo tiene valor
# por defecto. Solo se llenan las de Google si vas a analizar matrices por
# enlace de Google Sheets o carpetas de Drive.

set -euo pipefail
cd "$(dirname "$0")"

# Carga las credenciales desde .env (ignorado por git). El script no lee .env
# por si mismo, por eso se importa aqui antes de arrancar.
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

# --- Google (OPCIONAL) ---
# Viven en .env. Si estan vacias, la app corre igual; ese boton simplemente
# pedira conectar Google despues.
export GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
export GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"
export GOOGLE_REDIRECT_URI="${GOOGLE_REDIRECT_URI:-http://127.0.0.1:8000/google/callback}"

# --- Opcionales (no tocar si no las necesitas) ---
# AUTO_PRIZMA_SECRET      si falta, la app genera una clave en data/secreto_sesion.txt
# AUTO_PRIZMA_URL_PRIZMA  vacio = produccion; usa https://admin.prizma.solutions para pruebas
# AUTO_PRIZMA_MAX_SIMULTANEOS  1 o 2 cargues a la vez (por defecto 2)

exec .venv/bin/uvicorn main:app --reload --port 8000
