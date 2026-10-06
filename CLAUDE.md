# AUTO PRIZMA PRO

Guía principal para cualquier sesión de Claude (o persona) que trabaje en este repositorio.
Complementa a `README.md` (instalación, uso y despliegue). Si algo de este archivo contradice el código, **manda el código**: corrige este archivo.

> **Regla permanente del usuario:** cada cambio de código debe ir acompañado de la actualización de este `CLAUDE.md` en la misma tarea.

## Propósito

Aplicación web interna (FastAPI) que automatiza tareas en la plataforma educativa **PRIZMA** (`https://admin.prizma.site`) con un navegador Chromium controlado por Playwright:

1. **Cargue de recursos**: a partir de una **matriz** de actividades (Google Sheets por enlace, o `.xlsx`/`.csv`) y un **ZIP** con archivos `.h5p`/`.pdf`, sube cada recurso al campo "Recurso" de la actividad correspondiente (categorías **OVI**, **OVA** y **Retos Evaluativos**/`Challenge`). Antes valida los enlaces de Drive de la columna G contra el ZIP. Genera un reporte CSV por cargue.
2. **Tests evaluativos**: a partir de un `.docx` (archivo o Google Doc) crea cuestionarios en PRIZMA. Puede ejecutarse solo (`/tests`) o junto con el cargue de recursos.

Es multiusuario: usuarios locales con contraseña; cada usuario conecta su propia cuenta de Google (solo lectura) y ve solo sus trabajos, historial y reportes.

## Arquitectura

Monolito FastAPI en capas, dentro del paquete `auto_prizma/`. El HTML se genera en el servidor como strings de Python (no hay framework de frontend ni templates).

```
Navegador ──HTTP──> api/routes/*  ──> services/*  ──> integrations/google/*  ──> Google Sheets / Drive
                         │               │
                         │               └──> automation/prizma/engine.py ──Playwright──> PRIZMA
                         └──> web/views.py (HTML)
evaluative_tests/  = módulo de funcionalidad completo (rutas, estado, parser, automatización, vistas)
core/config.py     = toda la configuración; core/application.py = instancia FastAPI compartida
```

- Las rutas se registran **al importar** cada módulo de `api/routes/` sobre la instancia compartida `auto_prizma.core.application.app` (decoradores `@app.get/@app.post`). `evaluative_tests/routes.py` usa un `APIRouter` que `main.py` incluye al final.
- Estado de trabajos en memoria (`TRABAJOS`, cola, jobs de tests). Persistencia en archivos JSON/CSV bajo `DATA_DIR`.
- Cada cargue corre en su propio hilo con su propio Chromium; máximo 2 simultáneos.

### Estado de la reorganización (2026-10-06)

Se está reorganizando por fases. Hechas: **Fase 1–2** (auditoría y propuesta), **Fase 3** (estructura y nombres en inglés) y **Fase 4** (configuración centralizada) — commit `9b2c1e5`, sin cambios de comportamiento (mismas rutas, mismo HTML byte a byte). **Red de seguridad para la fase 7**: pruebas de caracterización del motor y de `drive_resource_policy` — commit `1e43574`. **Correcciones del motor** (campo Html vs H5P, diagnóstico de guardado, reintentos de sesión inicial, `import sys`) — commit `0e9ae40`. Pendientes: **5** servicios (sacar lógica de las rutas, repositorio JSON único, normalización de nombres única), **6** integraciones, **7** dividir `automation/prizma/engine.py` (~5800 líneas) y eliminar el monkeypatching, **8** rutas (pasar a `APIRouter`, layout HTML común), **9** más tests, **10** `docs/ARCHITECTURE.md`.

## Estructura del proyecto

```
auto-prizma-pro/
├── main.py                         # Arma la app: aplica overrides del motor, importa rutas, monta /tests
├── auto_prizma/
│   ├── core/
│   │   ├── application.py          # app = FastAPI(...)
│   │   └── config.py               # Carpetas, env vars, sesión, límites Google/Drive, cola, URL PRIZMA, Chromium
│   ├── api/routes/
│   │   ├── static_files.py         # Logo, CSS responsive, script de tema
│   │   ├── auth.py                 # Middleware de sesión, login, salir, cambiar clave
│   │   ├── google.py               # /google/conectar, /google/callback, /google/desconectar
│   │   ├── analysis.py             # / y POST /analizar (matriz + ZIP + opcional test .docx)
│   │   ├── uploads.py              # /iniciar, /cargue-actual, /proceso, /estado, /cancelar
│   │   └── reports.py              # /historial, /reportes, /reporte, /reporte-guardado
│   ├── services/
│   │   ├── auth.py                 # Usuarios (usuarios.json), PBKDF2, cookies HMAC, bloqueo por intentos
│   │   ├── matrix_analysis.py      # Descarga Sheets→XLSX, CSV→XLSX, análisis de matriz y ZIP
│   │   ├── drive_zip_validation.py # Prevalidación Drive ↔ ZIP, avisos
│   │   └── upload_jobs.py          # TRABAJOS, cola/hilos, historial, nombres de reporte, test dentro del cargue
│   ├── integrations/google/
│   │   ├── oauth.py                # OAuth por usuario, tokens, descarga de Google Docs para tests
│   │   └── drive.py                # Enlaces de columna G (Sheets API), listado de carpetas (Drive API)
│   ├── automation/prizma/
│   │   ├── engine.py               # Motor de cargue PRIZMA (Playwright) + lectura de matriz + reporte CSV
│   │   └── engine_overrides.py     # Reemplaza funciones del motor al importarse (ver Decisiones)
│   ├── domain/
│   │   └── drive_resource_policy.py# Reglas puras de emparejamiento Drive ↔ ZIP
│   ├── web/views.py                # HTML de la página principal (análisis y cargue)
│   └── evaluative_tests/           # Módulo de tests evaluativos
│       ├── models.py, parser.py, validation.py, serializer.py
│       ├── automation.py           # PrizmaTestAutomator (Playwright)
│       ├── execution.py            # Ejecución en segundo plano
│       ├── state.py                # Jobs en memoria, usuario PRIZMA recordado
│       ├── views.py                # HTML del módulo + parche del botón "Test"
│       └── routes.py               # APIRouter /tests/...
├── scripts/
│   ├── manage_users.py             # CLI de usuarios
│   └── check_prizma_connection.py  # Prueba manual: navegador visible, login manual, no modifica nada
├── tests/                          # pytest (PRIZMA y Playwright simulados)
├── static/auto_prizma_logo.png
├── .env.example                    # Variables soportadas (sin valores)
├── requirements.txt / requirements-dev.txt (añade pytest)
├── Dockerfile                      # python:3.12, playwright chromium, uvicorn main:app :8000
├── README.md
└── data/ uploads/ temp/ resultados/  # Generados en ejecución, no versionados (data/ contiene secretos)
```

## Componentes

| Componente | Responsabilidad | Notas |
|---|---|---|
| `main.py` | Orden de arranque | **El orden de imports importa**: primero `engine_overrides`, luego rutas, luego `/tests`. Expone `app.state.*` que usa el módulo de tests. |
| `core/config.py` | Única fuente de configuración | Ver sección Configuración. |
| `api/routes/*` | HTTP | Todavía contienen lógica y HTML (pendiente fase 8). |
| `services/auth.py` | Sesión y usuarios | `USUARIO_ACTUAL` (contextvar) propaga el usuario a endpoints e hilos. |
| `services/upload_jobs.py` | Ciclo de vida del cargue | `_encolar_trabajo` → `_despachar_cargues_pendientes` → hilo → `ejecutar_cargue_con_historial` → `engine.ejecutar_cargue`. |
| `automation/prizma/engine.py` | Todo lo que toca PRIZMA en el cargue | Funciones clave: `leer_actividades_excel`, `determinar_tipo_archivo`, `resolver_recurso`, `validar_credenciales_prizma`, `iniciar_sesion_prizma`, `procesar_actividad`, `ejecutar_cargue`, `guardar_resultado`, `EQUIVALENCIAS_PROGRAMAS`. |
| `evaluative_tests/` | Funcionalidad completa de tests | Se integra con el cargue vía `upload_jobs._ejecutar_test_en_cargue` y con historial/reportes vía `app.state`. |

## Convenciones

- Datos como `dict` simples; errores del motor como strings `ERROR_*` que terminan en reportes, historial y UI (no renombrarlos).
- HTML en raw strings con marcadores `__NOMBRE__` + `.replace`, valores escapados con `html.escape`.
- Escritura atómica de JSON: `*.tmp` + `os.replace`.
- Logging con `print()` (no hay módulo `logging`).
- Concurrencia con `threading.Lock/RLock/Condition`; fechas de usuario en `America/Bogota` (`ZONA_HORARIA_COLOMBIA`).
- Archivos `.py` del working tree con finales CRLF (`core.autocrlf=true`).
- No guardar copias `*_backup*.py`, `parche_*.py` ni `.zip` (bloqueados en `.gitignore`): git conserva el historial.

## Idioma

| Elemento | Idioma | Regla |
|---|---|---|
| Archivos y carpetas de código | **Inglés** | Obligatorio para todo archivo nuevo. |
| Funciones, clases, variables, módulos **nuevos** | **Inglés** | `get_user()`, `upload_resource()`. |
| Funciones/variables **existentes** en español | Se conservan | No traducir en masa: rompe imports, tests y `patch("...")`. Traducir solo con análisis de consumidores y en un cambio dedicado. |
| Comentarios y docstrings | **Español** | Incluso en código nuevo en inglés. |
| URLs, campos de formulario, claves JSON, env vars, archivos de `data/`, códigos `ERROR_*` | Sin cambios | Son contratos (navegador/JS, Railway, datos históricos). |

`auto_prizma` es el nombre del producto y se mantiene como nombre del paquete (no se usa `app/` porque `import app.x` en `main.py` taparía la instancia `main:app`).

## FastAPI

- Instancia: `auto_prizma.core.application.app`; ASGI: `main:app`.
- Middleware `exigir_sesion` (`api/routes/auth.py`): exige cookie `ap_sesion` salvo `RUTAS_PUBLICAS`; sin sesión → 303 a `/login`, o JSON 401 si la ruta empieza por `/estado/` o se acepta JSON. Fija `request.state.usuario` y `USUARIO_ACTUAL`.
- Rutas principales: ver tabla en `README.md` (sección "Rutas principales"). `/docs` existe pero exige sesión.
- Endpoints que usan Playwright sync deben ser `def` (threadpool) o hilos propios, **nunca `async def`**.

## Services

`auth`, `matrix_analysis`, `drive_zip_validation`, `upload_jobs`. Reglas:
- La lógica de negocio nueva va aquí, no en las rutas.
- Un servicio no importa módulos de `api/`.
- Hoy existen dependencias circulares resueltas con imports dentro de funciones (`upload_jobs` ↔ `evaluative_tests.execution`, `api/routes/analysis` → `evaluative_tests`). No añadir más; resolverlas en la fase 5.

## Integrations

- `integrations/google/oauth.py`: flujo OAuth web con PKCE y `state` (TTL 10 min, ligado al usuario de la sesión), scopes de solo lectura (`config.GOOGLE_SCOPES`), token por usuario en `DATA_DIR/tokens/<slug>-<hash>.json`, refresco automático, descarga de Google Docs para tests.
- `integrations/google/drive.py`: Sheets API (enlace real de la columna G, incluidos Smart Chips; pestaña por `gid`) y Drive API en lotes (`DRIVE_BATCH_MAX`, `DRIVE_PROFUNDIDAD_MAX`). **Solo metadatos**: nunca descarga H5P/PDF.
- Cualquier integración nueva va en `integrations/<servicio>/` y lee su configuración de `core/config.py`.

## Automation

- `automation/prizma/engine.py`: motor del cargue de recursos (mezcla aún lectura de matriz, índice ZIP, reporte CSV y Playwright; se dividirá en la fase 7).
- `automation/prizma/engine_overrides.py`: sustituye en el módulo `engine` las funciones `leer_actividades_excel`, `resolver_recurso` y `validar_carpeta_drive_para_actividad` para usar la pestaña objetivo y los recursos ya prevalidados (vía `threading.local`).
- `evaluative_tests/automation.py`: `PrizmaTestAutomator` para crear tests.

## Playwright

- API **síncrona**, Chromium (`python -m playwright install chromium`; versión fijada `playwright==1.61.0`).
- Config común en `core/config.py`: `CHROMIUM_ARGS` (`--no-sandbox`, `--disable-dev-shm-usage`) y `VIEWPORT_NAVEGADOR` (1440×900). Usar `list(...)`/`dict(...)` al pasarlos.
- Headless en servidor. `scripts/check_prizma_connection.py` abre navegador visible.
- Cada cargue reinicia navegador + login ante errores estructurales (`_es_error_estructural_prizma`), con un reintento por actividad.
- **Sesión inicial con reintentos** (`_abrir_sesion_inicial`): al empezar el cargue, si PRIZMA no responde (p. ej. `Page.goto: Timeout 60000ms exceeded`) se reintenta con las esperas de `config.PRIZMA_ESPERAS_REINTENTO_SESION` (5 s y 15 s → 3 intentos), atendiendo la cancelación. Nunca reintenta `ERROR_LOGIN_PRIZMA` (las credenciales ya se validaron en `/iniciar`; repetir logins fallidos podría bloquear la cuenta). Si se agotan, el usuario ve un mensaje legible con el detalle técnico al final.
- Selectores y textos dependen del DOM de PRIZMA: es la zona más frágil (búsqueda estable, paginación, recuperación de fila, confirmación del PATCH).
- **Confirmación del guardado** (`procesar_actividad`, pasos 10–11): tras pulsar "Guardar" se espera hasta 45 s la respuesta `PATCH .../academic/activity/...` (`expect_response`), luego 2 s el listener global (`esperar_patch`) y, como último respaldo, se reabre la actividad para ver si el archivo quedó (`verificar_guardado_por_reapertura`, busca el nombre del archivo local). Si todo falla → `ERROR_PATCH_NO_CONFIRMADO: <diagnóstico>`. Ojo: un clic en Guardar que no puede ejecutarse (botón tapado por un overlay o deshabilitado) lanza el MISMO `PlaywrightTimeoutError` que la espera del PATCH; `_resumir_error_clic` los distingue leyendo el call log de Playwright. El diagnóstico (`_diagnostico_guardado_sin_patch`) se toma ANTES de reabrir e incluye el motivo del clic fallido, alertas visibles de PRIZMA (`[role="alert"]`, errores de campos MUI), respuestas HTTP no-GET y peticiones fallidas (listener `requestfailed`, guardadas en `captura["fallidas"]`), siempre sin dominio ni query string, y guarda una captura en `temp/<trabajo>/sin_patch_fila_<n>.png` (`_guardar_captura_diagnostico`).

## Google

Necesario solo para la matriz por enlace y Google Docs de tests. Configuración de Google Cloud y variables: `README.md` → "Configurar Google (OAuth)". En local, `GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/google/callback` (con `http://127.0.0.1`/`localhost` se activa `OAUTHLIB_INSECURE_TRANSPORT`). Abrir la app con el mismo host que la URI de retorno (la cookie es por host).

## PRIZMA

- URL: `config.URL_PRIZMA` (`PRIZMA_BASE_URL + "/inicio-sesion"`).
- Credenciales PRIZMA: las escribe el usuario en cada cargue; se validan antes de encolar (`validar_credenciales_prizma`), viajan en el trabajo como `usuario_prizma_temporal`/`contrasena_prizma_temporal` y se eliminan al arrancar el hilo o cancelar. Nunca se persisten. El módulo de tests solo recuerda el **nombre de usuario** PRIZMA (`<raíz>/data/tokens/prizma_<usuario>.json`).
- Equivalencias de nombres de programa: `EQUIVALENCIAS_PROGRAMAS` en `engine.py` (explícitas; sin coincidencia aproximada a propósito).
- Matriz esperada: A1 programa, A2 curso, cabecera "Semana correspondiente" en columna A (primeras 30 filas); columnas A semana, B unidad, D actividad, E categoría, F tipo de recurso, G enlace Drive.
- **Campo Html vs H5P — política TEMPORAL (decisión del usuario, 2026-10-06): mientras se carguen H5P, si el campo "Html" tiene contenido el motor lo VACÍA antes de guardar** (PRIZMA no permite Html y H5P a la vez: "Solo puedes subir un H5P o completar el campo Html, no ambos"). Interruptor: `config.PRIZMA_VACIAR_HTML_CON_H5P` (`True` hoy). Cuando se deje de usar H5P y se implemente HTML, ponerlo en `False`: el motor nunca borrará el Html, cancelará sin guardar y reportará `ERROR_HTML_Y_H5P`.
  - Solo aplica a actividades H5P (o si aparece el aviso). El editor se busca únicamente entre el título "Html" y el título "Recurso…" (`_XPATH_EDITOR_HTML`), así nunca toca la Descripción. Soporta `textarea`, `contenteditable`, CodeMirror y Monaco; se verifica que quedó vacío o que desapareció el aviso (`_vaciar_editor_html`).
  - Dos momentos: antes del primer clic en Guardar (si se detecta contenido) y, si PRIZMA solo avisa al guardar, se vacía y se reintenta el guardado UNA vez (`_resolver_campo_html`, `_intentar_guardado`).
  - El contenido eliminado queda en la columna Observación del reporte CSV (`_observacion_guardado`, clave `html_vaciado` del resultado).
  - Si no se puede vaciar: cancela sin guardar → `ERROR_LIMPIANDO_HTML` + copia de la estructura del campo en `temp/<trabajo>/campo_html_fila_<n>.html` y captura, para ajustar el selector. La estructura real del editor Html de PRIZMA no se ha inspeccionado: el selector se validó con réplicas en Chromium.
- Un cargue real **modifica PRIZMA**: no ejecutarlo para "probar" sin autorización explícita.

## Usuarios

- `services/auth.py`: `usuarios.json` en `DATA_DIR`, PBKDF2-SHA256 (`PBKDF2_ITERACIONES`), mínimo 8 caracteres, cookie firmada HMAC sin estado en servidor (12 h), bloqueo tras `MAX_INTENTOS` fallos por usuario+IP durante `BLOQUEO_SEGUNDOS`.
- CLI (contraseñas con `getpass`):

```powershell
python scripts/manage_users.py listar | crear | clave | desactivar | activar | borrar
```

## Configuración

Todo en `auto_prizma/core/config.py`. Variables de entorno documentadas en `.env.example` (la app **no** lee `.env`; definirlas en el entorno o en Railway):

| Variable | Se lee | Uso |
|---|---|---|
| `AUTO_PRIZMA_DATA_DIR` | al importar | Datos persistentes (def. `<raíz>/data`) |
| `AUTO_PRIZMA_SECRET` | al importar `services/auth` | Clave HMAC de cookies (si falta: `data/secreto_sesion.txt`) |
| `AUTO_PRIZMA_COOKIE_SECURE` | en cada request | `"1"` fuerza cookie Secure |
| `AUTO_PRIZMA_MAX_SIMULTANEOS` | al importar | `1` o `2` (otro valor → 2) |
| `GOOGLE_CLIENT_ID` / `_SECRET` / `_REDIRECT_URI` | en cada llamada | OAuth |

Otros parámetros: `PRIZMA_ESPERAS_REINTENTO_SESION` (reintentos de la sesión inicial), `PRIZMA_VACIAR_HTML_CON_H5P` (política temporal del campo Html), `CHROMIUM_ARGS`, `VIEWPORT_NAVEGADOR`, límites de Google/Drive.

Reglas: no leer `os.environ` fuera de `config.py`; añadir constantes nuevas (URLs, límites, timeouts) a `config.py` y a `.env.example` si son variables; mantener el "momento de lectura" al mover algo. Los timeouts de Playwright del motor siguen dispersos en `engine.py` (pendiente fase 7).

## Ejecución

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python scripts/manage_users.py crear
python -m uvicorn main:app --reload
```

URL de desarrollo: `http://127.0.0.1:8000`. `--reload` reinicia el proceso y **pierde los trabajos en memoria**. Producción: `Dockerfile` (`uvicorn main:app --host 0.0.0.0 --port 8000`), desplegado en Railway.

## Tests

- Framework: **pytest** (`requirements-dev.txt`). `tests/conftest.py` fija `AUTO_PRIZMA_DATA_DIR` en una carpeta temporal y crea el usuario `adminlocal`. PRIZMA y Playwright están simulados (`unittest.mock.patch`).

```powershell
python -m pytest -q                                   # todo (≈45 s, 156 pruebas al 2026-10-06)
python -m pytest tests/test_test_parser.py -q         # un archivo
python -m pytest tests/test_automation.py -k nombre   # una prueba
```

- Los `patch("auto_prizma.evaluative_tests....")` usan rutas de módulo en texto: al mover/renombrar módulos hay que actualizarlas.
- **Pruebas de caracterización** (`test_engine_characterization.py`, `test_drive_resource_policy.py`): fijan el comportamiento ACTUAL (lectura de matriz, tipo de archivo, índice ZIP, `resolver_recurso`, CSV, reglas de Retos, emparejamiento Drive↔ZIP). Si fallan tras un refactor, el refactor cambió comportamiento: no "arreglar" la prueba sin decidirlo explícitamente. Usan las funciones originales del motor guardadas en `engine_overrides` (`_LEER_ACTIVIDADES_EXCEL_ORIGINAL`, `_RESOLVER_RECURSO_ORIGINAL`), porque al importar `main` el motor queda parcheado.
- Sin cobertura: el motor de cargue real contra PRIZMA, OAuth real, Drive real.
- Verificación adicional tras refactors: `python -m compileall -q main.py auto_prizma scripts tests` y arrancar uvicorn comprobando `/login` (200) y `/` (303 → `/login`).

## Seguridad

- Nunca escribir contraseñas, tokens ni secretos en el código; configuración sensible solo por variables de entorno.
- Nunca versionar `data/`, `.env`, `client_secret*.json` (ya en `.gitignore`). No leer ni mostrar `data/secreto_sesion.txt`, `data/tokens/*` ni hashes de `usuarios.json` salvo necesidad explícita.
- No registrar credenciales PRIZMA en `print()`, reportes, historial ni en la respuesta de `/estado`.
- Mantener: `state`+PKCE en OAuth, comprobación de usuario en el callback, `hmac.compare_digest`, bloqueo por intentos, comprobación de propietario (`_es_de`) en rutas de trabajos, `os.path.basename` al servir reportes, scopes de Google de solo lectura.

## Git

- Rama principal: `main` (PRs). Rama de trabajo del usuario: `Jeremy`. Equipo: Kevin Torres, Luis, danilo0413, JIMENEZ45 (aprueba PRs). Commits en español, con prefijos `fix:`/`refactor:`/`docs:`/`chore:`.
- Antes de cambiar nada:

```powershell
git status
git branch --show-current
git log -1 --oneline
git fetch origin; git rev-list --count HEAD..origin/main   # ¿rama atrasada?
```

- Prohibido salvo autorización explícita: commit, push, force push, borrar ramas, `reset --hard`, sobrescribir cambios locales, cambiar de rama.
- Mover archivos con `git mv` (conserva historial). Los renombrados masivos afectan a ramas de otros: coordinarlos y mantener el PR pequeño.

## Reglas para modificar código

1. Leer el código relacionado y sus consumidores antes de editar (incluido `engine.py` ↔ `engine_overrides.py`).
2. Cambios mínimos; no reescribir módulos completos si basta un cambio pequeño.
3. No eliminar funcionalidades ni código sin demostrar que no se usa (`grep` del nombre, también en strings de `patch(...)` y `sys.modules.get(...)`).
4. No cambiar contratos sin analizar consumidores: URLs, campos de formulario, JSON de `/estado`, columnas del CSV, formato de `usuarios.json`/`historial.json`, `app.state.*`, firmas de funciones del motor reemplazadas por `engine_overrides`.
5. No duplicar lógica: reutilizar `normalizar_texto`, `drive_resource_policy`, helpers de `services/`.
6. Configuración nueva solo en `core/config.py`.
7. Código nuevo en el módulo de su capa (ver "Cómo agregar una nueva funcionalidad").
8. Mantener compatibilidad con Windows (rutas con `os.path`, `encoding="utf-8"`).
9. Ejecutar pruebas después de cada cambio y revisar `git diff`.
10. Actualizar este `CLAUDE.md` (y `README.md` si cambia algo de uso) en la misma tarea.
11. Informar qué archivos se modificaron. No hacer commit ni push salvo petición explícita.

## Archivos que no deben modificarse

| Tipo | Rutas |
|---|---|
| Datos y secretos | `data/` (usuarios, `secreto_sesion.txt`, `tokens/`, `historial.json`, `reportes/`) |
| Generados en ejecución | `uploads/*`, `temp/*`, `resultados/*` (conservar `.gitkeep`) |
| Entornos y caches | `.venv/`, `.venv-1/`, `__pycache__/`, `.pytest_cache/` |
| Binarios | `static/auto_prizma_logo.png` (solo si se pide) |
| Contrato de despliegue | `Dockerfile` (`main:app`, puerto 8000): solo con motivo explícito |

## Cómo agregar una nueva funcionalidad

1. Identificar el dominio y buscar funcionalidad relacionada (`grep`) en `services/`, `integrations/`, `automation/`, `evaluative_tests/`.
2. Revisar contratos afectados (rutas, formularios, JSON, CSV, `app.state`) y los tests existentes.
3. Ubicar cada parte en su capa:
   - Ruta HTTP → `api/routes/<dominio>.py` (fina: valida, llama al servicio, devuelve respuesta). Si es un módulo nuevo, importarlo en `main.py` respetando el orden.
   - Lógica de negocio → `services/<dominio>.py`.
   - API externa → `integrations/<servicio>/`.
   - Navegador/PRIZMA → `automation/prizma/`.
   - Reglas puras sin I/O → `domain/`.
   - HTML → `web/` (o `views.py` del módulo).
   - Constantes/env → `core/config.py` (+ `.env.example`).
   - Funcionalidad grande y autocontenida → paquete propio como `evaluative_tests/`.
4. Nombres de archivos/funciones nuevas en inglés; comentarios y docstrings en español.
5. Añadir pruebas en `tests/` (simular PRIZMA/Playwright/Google con `unittest.mock`).
6. `python -m pytest -q`, revisar `git diff`, actualizar `CLAUDE.md`/`README.md`.

## Checklist antes de modificar

- [ ] Leí `CLAUDE.md` (y `README.md` si aplica).
- [ ] `git status`, rama actual y si está atrasada respecto a `origin/main`.
- [ ] Entendí el flujo afectado y localicé módulos, consumidores y tests relacionados.
- [ ] Revisé integraciones afectadas (Google, PRIZMA, Playwright).
- [ ] Propuse el plan antes de tocar código.

## Checklist después de modificar

- [ ] `python -m pytest -q` en verde.
- [ ] Sin errores de importación (`python -c "import main"`).
- [ ] Endpoints afectados probados (uvicorn + `/login`, páginas tocadas).
- [ ] Integraciones afectadas revisadas.
- [ ] `git diff` revisado; sin secretos.
- [ ] Sin lógica duplicada.
- [ ] Comentarios nuevos en español; archivos nuevos con nombre en inglés.
- [ ] `CLAUDE.md` (y `README.md` si corresponde) actualizados.

## Problemas conocidos

- **Monkeypatching del motor** (`engine_overrides.py`) y del botón "Test" (`evaluative_tests/views.py::_patch_main_nav`, vía `sys.modules.get("auto_prizma.api.routes.uploads")`): acople oculto; si se mueve el código parcheado, el parche deja de aplicarse sin error visible.
- **`ERROR_PATCH_NO_CONFIRMADO` en actividades con campo Html** (causa encontrada el 2026-10-06): PRIZMA no envía el guardado si el campo "Html" tiene contenido y se sube un H5P. Ahora se vacía el Html (política temporal, ver PRIZMA). Si vuelve a aparecer `ERROR_PATCH_NO_CONFIRMADO`, el mensaje trae el diagnóstico y la captura `temp/<trabajo>/sin_patch_fila_<n>.png`.
- **`print()` con caracteres no ASCII en el motor** (`→`, emojis): si la salida estándar no es UTF-8 (Windows con la salida redirigida a archivo/pipe, p. ej. `uvicorn ... > log.txt`), `resolver_recurso` y otras funciones lanzan `UnicodeEncodeError` en pleno cargue. En Railway (Linux) no ocurre. Mitigación local: `$env:PYTHONIOENCODING = "utf-8"`. Corrección pendiente (fase 7: logging en lugar de `print`).
- **Ruta de datos inconsistente** en `evaluative_tests/state.py`: el usuario PRIZMA recordado se guarda en `<raíz>/data/tokens/` ignorando `AUTO_PRIZMA_DATA_DIR` (en Railway puede no ser persistente). Las pruebas lo confirman: escriben `data/tokens/prizma_adminlocal.json` en el `data/` real (solo `usuario`/`recordar`, sin contraseña). El nombre de archivo usa el usuario sin sanear. Corregirlo cambia dónde se guarda el dato (los usuarios tendrían que reescribir su usuario PRIZMA una vez).
- **Estado en memoria**: trabajos, cola, `state` OAuth y jobs de tests se pierden al reiniciar.
- **Sin limpieza** de `uploads/<id>` y `temp/<id>` tras el cargue (solo si falla la prevalidación).
- `resultados/` no se usa (los reportes van a `DATA_DIR/reportes/`).
- `/cargue-actual` muestra cargues activos de **todos** los usuarios (las acciones sí exigen ser el dueño), aunque el README dice "del usuario".
- Docstring de `_resolver_hoja_objetivo` (`integrations/google/drive.py`) dice que sin `gid` devuelve `None`, pero lanza `ValueError`.
- Código sin uso: `prevalidar_recursos_drive_zip` del motor; scraping público de Drive del motor (anulado por el override); `BackgroundTasks` en `/iniciar`.
- Archivos grandes pendientes de dividir: `engine.py` (~5200), `web/views.py` (~1500), `evaluative_tests/automation.py` (~1090), `integrations/google/drive.py` (~920), `evaluative_tests/routes.py` (~910), `services/drive_zip_validation.py` (~880).
- Duplicaciones pendientes: normalización de nombres de archivo en 3 sitios (`_clave_nombre_drive_zip`, `clave_nombre_archivo_exacto`, `drive_resource_policy._normalized_name`); escritura atómica de JSON repetida; layout HTML (barra lateral/estilos) copiado en varias páginas; lógica de login en PRIZMA repetida.
- `.venv` local creado antes de que `main` añadiera `python-docx`: ejecutar `python -m pip install -r requirements-dev.txt` o la app no arranca.

## Decisiones arquitectónicas

- **Paquete `auto_prizma/` por capas** (core / api / services / integrations / automation / domain / web) + módulos de funcionalidad autocontenidos (`evaluative_tests/`).
- **`main:app` como contrato** de arranque (Dockerfile/Railway); `main.py` solo ensambla.
- **Configuración centralizada** en `core/config.py`; los módulos reexportan los mismos nombres para no romper consumidores; las variables que se leían en cada llamada siguen leyéndose en cada llamada.
- **Overrides del motor al importar** (heredado): el preflight Drive↔ZIP se reutiliza durante el cargue sin volver a consultar Drive. Se planea sustituir por inyección explícita (fase 7).
- **Identidad Drive↔ZIP solo por nombre canónico**; el tamaño es informativo; las ambigüedades no se adivinan (la fila queda no cargable). Diferencias = advertencias, no bloqueo del análisis completo.
- **Solo la pestaña del `gid`** y **solo la columna G** definen qué se procesa y qué carpeta Drive corresponde a cada fila.
- **Google solo lectura y solo metadatos**; token por usuario.
- **Sesión con cookie HMAC sin estado** y usuarios en JSON local gestionados por CLI.
- **Un hilo + un Chromium por cargue**, máximo 2 simultáneos; cancelación cooperativa entre actividades.
- **HTML renderizado en servidor** con CSS común en `/estilos-responsive.css` y tema oscuro.
- **Hora de Colombia** para historial y nombres de reporte.
