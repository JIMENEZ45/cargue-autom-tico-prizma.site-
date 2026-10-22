# Auto Prizma Pro

App web (Python + FastAPI) que automatiza el cargue de actividades a **PRIZMA**. Corre en local y usa un navegador (Chromium) para operar la plataforma.

---

## Requisitos

- **Python 3.12 o superior**
- **Git**
- **Google Chrome/Chromium** se instala solo (paso 2)

---

## Instalación

### macOS / Linux

```bash
git clone https://github.com/JIMENEZ45/cargue-autom-tico-prizma.site-.git
cd cargue-autom-tico-prizma.site-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # <-- OBLIGATORIO, si no: "Chromium no disponible"
```

### Windows (PowerShell)

```powershell
git clone https://github.com/JIMENEZ45/cargue-autom-tico-prizma.site-.git
cd cargue-autom-tico-prizma.site-
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium          # <-- OBLIGATORIO
```

> Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope Process RemoteSigned`

---

## Variables de entorno (opcional)

La app **funciona sin ninguna**. Todas tienen valor por defecto. Solo se definen si las necesitas.

| Variable | Para qué | Por defecto |
|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth de Google (Sheets/Drive) | — |
| `GOOGLE_CLIENT_SECRET` | OAuth de Google | — |
| `GOOGLE_REDIRECT_URI` | URL de retorno OAuth | — |
| `AUTO_PRIZMA_SECRET` | Firma de cookies de sesión | Se genera en `data/secreto_sesion.txt` |
| `AUTO_PRIZMA_URL_PRIZMA` | URL de PRIZMA. Vacío = producción | `https://admin.prizma.site` |
| `AUTO_PRIZMA_DATA_DIR` | Carpeta de datos | `./data` |
| `AUTO_PRIZMA_MAX_SIMULTANEOS` | Cargues a la vez (1 o 2) | `2` |

**La app NO lee `.env` automáticamente.** Para usar Google, defines las variables en la terminal antes de arrancar (o usa `./arrancar.sh` en macOS/Linux, que las carga desde `.env`).

---

## Correr la app

### macOS / Linux

```bash
./arrancar.sh                         # carga .env si existe
# o manual:
uvicorn main:app --reload --port 8000
```

### Windows (PowerShell)

```powershell
uvicorn main:app --reload --port 8000
```

Abre **http://127.0.0.1:8000**

---

## Crear usuario

No hay registro web. Se crea desde consola (con el entorno activado):

### macOS / Linux

```bash
python scripts/manage_users.py crear      # interactive
python scripts/manage_users.py listar     # ver usuarios
python scripts/manage_users.py clave      # cambiar contraseña
```

### Windows (PowerShell)

```powershell
python scripts\manage_users.py crear
python scripts\manage_users.py listar
python scripts\manage_users.py clave
```

La contraseña debe tener **mínimo 8 caracteres**. Pedirá usuario, nombre a mostrar y contraseña (dos veces).

---

## Entrar

Ve a **http://127.0.0.1:8000/login** con el usuario y contraseña que creaste.

Dentro de la app:

- **Inicio** — sube la matriz y el ZIP y arranca el cargue.
- **Cursos** — por curso: cuántas actividades ya están en PRIZMA y **por qué falta cada una** (mensaje legible, no código). Al volver a subir la matriz del mismo curso, **las pendientes se marcan solas** y las ya cargadas quedan sin marca: es el reintento sin tener que elegir una por una.
- **Historial / Reportes** — cargues anteriores y su reporte CSV (columnas `Motivo` = explicación en español y `Hoja`).

---

## Conectar Google (opcional)

Solo si vas a analizar matrices desde enlaces de Google Sheets o carpetas de Drive.

1. En [Google Cloud Console](https://console.cloud.google.com/) crea un proyecto.
2. Habilita **Google Sheets API** y **Google Drive API**.
3. Pantalla de consentimiento OAuth → tipo **Externo**; agrega tu correo como **usuario de prueba**.
4. **Credenciales** → *ID de cliente OAuth* → tipo **Aplicación web**.
   - URI de redirección: `http://127.0.0.1:8000/google/callback`
5. Copia el **ID** y el **Secreto** a las variables de entorno y reinicia la app.
6. Dentro de la app, pulsa **"Conectar con Google"**.

---

## Problemas comunes

| Problema | Solución |
|---|---|
| `ModuleNotFoundError` | No activaste el venv. `source .venv/bin/activate` (mac) o `.\.venv\Scripts\Activate.ps1` (win) |
| "Chromium no disponible" | `playwright install chromium` |
| Puerto 8000 ocupado | `kill $(lsof -ti :8000)` (mac) o cierra la otra terminal (win) |
| Google: *Faltan variables* | Define `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` |
| Google: *redirect_uri_mismatch* | La URI debe coincidir **exactamente** con la registrada en Google Cloud |
| Login bloqueado | Espera 120 s (bloqueo tras 5 intentos fallidos) |
| Un cargue salió con errores | Entra a **Cursos**: te dice cuáles faltan y la causa en español. En el CSV, la columna `Motivo` la explica y `Observación` conserva el código `ERROR_*` |

---

## Despliegue (Railway)

Sube a `main` para desplegar. Ver `Dockerfile` (instala deps + Chromium y arranca uvicorn en el puerto 8000).

Documentación completa: ver **`GUIA_DETALLADA.md`**.
