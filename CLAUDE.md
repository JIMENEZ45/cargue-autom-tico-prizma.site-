# AUTO PRIZMA PRO

Guía principal para cualquier sesión de Claude (o persona) que trabaje en este repositorio.
Complementa a `README.md` (instalación, uso y despliegue). Si algo de este archivo contradice el código, **manda el código**: corrige este archivo.

> **Regla permanente del usuario:** cada cambio de código debe ir acompañado de la actualización de este `CLAUDE.md` en la misma tarea.

## Propósito

Aplicación web interna (FastAPI) que automatiza tareas en la plataforma educativa **PRIZMA** (`https://admin.prizma.site`) con un navegador Chromium controlado por Playwright:

1. **Cargue de recursos**: a partir de una **matriz** de actividades (Google Sheets por enlace, o `.xlsx`/`.csv`) y un **ZIP** con archivos `.h5p`/`.pdf`, sube cada recurso al campo "Recurso" de la actividad correspondiente (categorías **OVI**, **OVA** y **Retos Evaluativos**/`Challenge`). Antes valida los enlaces de Drive de la columna G contra el ZIP. Genera un reporte CSV por cargue.
2. **Tests evaluativos**: a partir de un `.docx` (archivo o Google Doc) crea cuestionarios en PRIZMA. Puede ejecutarse solo (`/tests`) o junto con el cargue de recursos.
3. **Cargue Moodle local**: sección `/moodle` que analiza matriz CSV/XLSX y ZIP de PDF/H5P, muestra vista previa y publica en el curso Prizma con Chromium visible e inicio de sesión manual.

Es multiusuario: usuarios locales con contraseña; cada usuario conecta su propia cuenta de Google (solo lectura) y ve solo sus trabajos, historial y reportes.

## Arquitectura

Monolito FastAPI en capas, dentro del paquete `auto_prizma/`. El HTML se genera en el servidor como strings de Python (no hay framework de frontend ni templates).

```
Navegador ──HTTP──> api/routes/*  ──> services/*  ──> integrations/google/*  ──> Google Sheets / Drive
                         │               │
                         │               └──> automation/prizma/engine.py ──Playwright──> PRIZMA
                         └──> web/views.py y vistas de cada ruta ──> web/layout.py (marco comun)
                                                                  + static/app.css / app.js
evaluative_tests/  = módulo de funcionalidad completo (rutas, estado, parser, automatización, vistas)
core/config.py     = toda la configuración; core/application.py = instancia FastAPI compartida
```

- Las rutas se registran **al importar** cada módulo de `api/routes/` sobre la instancia compartida `auto_prizma.core.application.app` (decoradores `@app.get/@app.post`). `evaluative_tests/routes.py` usa un `APIRouter` que `main.py` incluye al final.
- Estado de trabajos en memoria (`TRABAJOS`, cola, jobs de tests). Persistencia en archivos JSON/CSV bajo `DATA_DIR`.
- Cada cargue corre en su propio hilo con su propio Chromium; máximo 2 simultáneos.
- **Interfaz**: todas las páginas se arman con el marco común `web/layout.py` (`render_page`; el login con `render_public_page`): menú lateral con íconos, estado real del servicio, barra superior con tema claro/oscuro y menú de usuario, y aviso de ambiente de pruebas. El aspecto común vive en `static/app.css` (colores como variables; el tema oscuro solo redefine variables) y el comportamiento común en `static/app.js` (tema, menús, copiar, diálogos, estado del servicio, tablas con búsqueda/filtros/orden/paginación). Cada página agrega solo su contenido y su CSS/JS propio.

### Estado de la reorganización (2026-10-06)

Se está reorganizando por fases. Hechas: **Fase 1–2** (auditoría y propuesta), **Fase 3** (estructura y nombres en inglés) y **Fase 4** (configuración centralizada) — commit `9b2c1e5`, sin cambios de comportamiento (mismas rutas, mismo HTML byte a byte). **Red de seguridad para la fase 7**: pruebas de caracterización del motor y de `drive_resource_policy` — commit `1e43574`. **Correcciones del motor** (campo Html vs H5P, diagnóstico de guardado, reintentos de sesión inicial, `import sys`) — commit `0e9ae40`. **Fase 5** (servicios): lógica de `/analizar`, `/iniciar`, `/cargue-actual`, `/cancelar`, `/estado` y reportes movida a `services/`; historial en `services/history.py`; escritura atómica única (`core/storage.py`); hora en `core/clock.py`; nombres de archivo en `domain/file_names.py`; código muerto eliminado; la contraseña PRIZMA ya no se retiene en el trabajo. Verificado: mismas rutas, mismo HTML y misma salida de `/analizar` que el código original. **Formato HTML para los recursos interactivos** (ver PRIZMA): probado en el ambiente de pruebas de PRIZMA e integrado en `main` el 2026-10-07. **Fase 8, parte visual** (aprobada por el usuario e integrada en `main` el 2026-10-07): marco HTML común (`web/layout.py` + `static/app.css`/`app.js`) en todas las páginas, rediseño de Inicio, Reportes y Detalle según las imágenes del usuario, estado real del servicio, validación del enlace de Sheets y eliminación de `_patch_main_nav`. Pendientes: **6** integraciones, **7** dividir `automation/prizma/engine.py` (~5800 líneas) y eliminar el monkeypatching del motor, **8** rutas (pasar a `APIRouter`), **9** más tests, **10** `docs/ARCHITECTURE.md`.

## Estructura del proyecto

```
auto-prizma-pro/
├── main.py                         # Arma la app: aplica overrides del motor, importa rutas, monta /tests
├── auto_prizma/
│   ├── core/
│   │   ├── application.py          # app = FastAPI(...)
│   │   ├── config.py               # Carpetas, env vars, sesión, límites Google/Drive, cola, URL PRIZMA, Chromium
│   │   ├── storage.py              # read_json / write_json_atomic / write_text_atomic (escritura atómica)
│   │   └── clock.py                # _ahora_colombia / _ahora_colombia_iso
│   ├── api/routes/
│   │   ├── static_files.py         # Logo, /app.css y /app.js (públicos)
│   │   ├── auth.py                 # Middleware de sesión y login
│   │   ├── google.py               # /google/conectar, /google/callback, /google/desconectar
│   │   ├── analysis.py             # / y POST /analizar (matriz + ZIP + opcional test .docx)
│   │   ├── uploads.py              # /iniciar, /cargue-actual, /proceso, /estado, /cancelar
│   │   ├── reports.py              # /historial, /reportes, /reporte, /reporte-guardado
│   │   ├── health.py               # /estado-servicio (JSON con el estado de Chromium y PRIZMA)
│   │   └── moodle_resources.py     # /moodle: análisis, revisión y publicación local Moodle
│   ├── services/
│   │   ├── auth.py                 # Usuarios (usuarios.json), PBKDF2, cookies HMAC, bloqueo por intentos
│   │   ├── matrix_analysis.py      # Descarga Sheets→XLSX, CSV→XLSX, análisis de matriz y ZIP
│   │   ├── drive_zip_validation.py # Prevalidación Drive ↔ ZIP, avisos
│   │   ├── upload_jobs.py          # TRABAJOS, cola/hilos, test dentro del cargue y servicios de las rutas
│   │   │                           # (create_analyzed_job, validate_access_and_enqueue, active_jobs, cancel_job, public_job_status)
│   │   ├── history.py              # historial.json, nombres/rutas de reportes, consulta por usuario, lectura del CSV
│   │   ├── health.py               # Estado real: Chromium instalado y PRIZMA responde (con memoria de unos minutos)
│   │   └── moodle_resources.py     # Vista previa, extracción ZIP, jobs y reportes Moodle
│   ├── integrations/google/
│   │   ├── oauth.py                # OAuth por usuario, tokens, descarga de Google Docs para tests
│   │   └── drive.py                # Enlaces de columna G (Sheets API), listado de carpetas (Drive API),
│   │                               # check_sheet_link (valida el enlace de la matriz al pegarlo)
│   ├── automation/prizma/
│   │   ├── engine.py               # Motor de cargue PRIZMA (Playwright) + lectura de matriz + reporte CSV
│   │   ├── engine_overrides.py     # Reemplaza funciones del motor al importarse (ver Decisiones)
│   │   └── html_field.py           # Formato HTML: leer el .html, escribirlo en el campo Html, quitar el archivo previo de Recurso
│   ├── automation/moodle/
│   │   └── client.py                # Chromium visible, login manual y publicación Moodle PDF/H5P
│   ├── domain/
│   │   ├── drive_resource_policy.py# Reglas puras de emparejamiento Drive ↔ ZIP
│   │   ├── file_names.py           # file_base_name / exact_name_key (nombres de archivo)
│   │   └── moodle_resources.py     # Reglas de destinos y matching Moodle
│   ├── web/
│   │   ├── layout.py               # Marco común: render_page / render_public_page, menú, estado, tema, usuario
│   │   ├── icons.py                # Íconos SVG (icon(nombre))
│   │   ├── views.py                # Inicio (formulario de análisis) y revisión antes del cargue
│   │   └── moodle_views.py         # /moodle: formulario, vista previa con selección por tipo/semana, progreso en vivo, reporte
│   └── evaluative_tests/           # Módulo de tests evaluativos
│       ├── models.py, parser.py, validation.py, serializer.py
│       ├── automation.py           # PrizmaTestAutomator (Playwright)
│       ├── execution.py            # Ejecución en segundo plano
│       ├── state.py                # Jobs en memoria, usuario PRIZMA recordado
│       ├── views.py                # HTML del módulo (usa el marco común vía _layout)
│       └── routes.py               # APIRouter /tests/...
├── scripts/
│   ├── manage_users.py             # CLI de usuarios
│   └── check_prizma_connection.py  # Prueba manual: navegador visible, login manual, no modifica nada
├── tests/                          # pytest (PRIZMA y Playwright simulados)
├── static/                        # auto_prizma_logo.png, app.css (estilos comunes) y app.js (comportamiento común)
├── .env.example                    # Variables soportadas (sin valores)
├── requirements.txt                     # pytest ya incluido (no hay requirements-dev.txt)
├── Dockerfile                      # python:3.12, playwright chromium, uvicorn main:app :8000
├── deploy/oracle/                  # Despliegue gratuito en Oracle Cloud: docker-compose (app + Caddy HTTPS),
│                                   # Caddyfile, .env.example, setup-server.sh
├── docs/DEPLOY_ORACLE.md           # Guía paso a paso del despliegue en Oracle Cloud
├── README.md                       # Guía corta: instalar, arrancar, crear usuario, Moodle local
├── GUIA_DETALLADA.md               # Documentación completa (antes era el README largo)
└── data/ uploads/ temp/ resultados/  # Generados en ejecución, no versionados (data/ contiene secretos)
```

## Componentes

| Componente | Responsabilidad | Notas |
|---|---|---|
| `main.py` | Orden de arranque | **El orden de imports importa**: primero `engine_overrides`, luego rutas, luego `/tests`. Expone `app.state.*` que usa el módulo de tests. |
| `core/config.py` | Única fuente de configuración | Ver sección Configuración. |
| `api/routes/*` | HTTP | Delgadas para análisis, cargues y reportes (delegan en `services/`). Aún contienen el contenido HTML de sus páginas, pero el marco es común (`web/layout.py`). |
| `web/layout.py` | Marco de todas las páginas | `render_page(title, content, active=..., page_css=..., page_js=..., after_main=...)`; `NAV_ITEMS` define el menú; `status_pills()` los indicadores de Inicio; `environment_notice()` el aviso de ambiente de pruebas. |
| `services/auth.py` | Sesión y usuarios | `USUARIO_ACTUAL` (contextvar) propaga el usuario a endpoints e hilos. |
| `services/upload_jobs.py` | Ciclo de vida del cargue | `create_analyzed_job` → `validate_access_and_enqueue` → `_encolar_trabajo` → `_despachar_cargues_pendientes` → hilo → `ejecutar_cargue_con_historial` → `engine.ejecutar_cargue`. `cancel_job`, `public_job_status` y `active_jobs` para las rutas. |
| `services/history.py` | Historial y reportes | `_agregar_registro_historial` (sin duplicar id), `_historial_del_usuario` (solo registros propios), `find_user_record`, `saved_report_path` (solo basename dentro de `RESULTADOS_DIR`). |
| `services/moodle_resources.py` | Análisis y jobs Moodle | Lee matriz CSV/XLSX, extrae PDF/H5P de ZIP, aplica matching, mantiene jobs en memoria y genera reportes por usuario. |
| `automation/moodle/client.py` | Publicación Moodle | Chromium visible local con login manual, detección de duplicados y publicación PDF/H5P. Independiente del motor administrativo. |
| `core/storage.py` | Archivos de datos | Toda escritura de JSON/texto en `data/` debe ser atómica con estas funciones. |
| `automation/prizma/engine.py` | Todo lo que toca PRIZMA en el cargue | Funciones clave: `leer_actividades_excel`, `determinar_tipo_archivo`, `resolver_recurso`, `validar_credenciales_prizma`, `iniciar_sesion_prizma`, `procesar_actividad`, `ejecutar_cargue`, `guardar_resultado`, `EQUIVALENCIAS_PROGRAMAS`. |
| `evaluative_tests/` | Funcionalidad completa de tests | Se integra con el cargue vía `upload_jobs._ejecutar_test_en_cargue` y con historial/reportes vía `app.state`. |

## Convenciones

- Datos como `dict` simples; errores del motor como strings `ERROR_*` que terminan en reportes, historial y UI (no renombrarlos).
- HTML en raw strings con marcadores `__NOMBRE__` + `.replace`, valores escapados con `html.escape`.
- **Páginas**: toda página con sesión se arma con `web/layout.render_page(...)` (nunca copiar el menú ni el `<head>`); colores solo con las variables de `static/app.css` (`--panel`, `--texto`, `--acento`, `--verde-suave`, ...), sin colores fijos ni reglas `html[data-theme="dark"] ... !important`; íconos con `web/icons.icon()`. Los componentes comunes (`.panel`, `.boton`, `.chip`, `.badge-*`, `.mosaico`, `.tabla`, `.aviso`, `.dropzone`, `.menu-desplegable`, `.dialogo`) están en `app.css`. Una tabla con `data-tabla` + controles `data-control-tabla="<id>"` obtiene búsqueda, filtros, orden y paginación de `app.js` sin JS propio.
- Si un recurso estático cambia, la URL cambia sola (`?v=<fecha de modificación>`, `layout.asset_url`).
- Archivos de datos: usar `core/storage.py` (`read_json`, `write_json_atomic`, `write_text_atomic`; escritura atómica `*.tmp` + `os.replace`). `read_json` recibe qué errores cuentan como "ilegible": `usuarios.json` solo trata errores de lectura/JSON (otros se propagan para no sobrescribir un archivo dañado al crear un usuario).
- Un servicio que falla por una regla de negocio lanza `ValueError` con el mensaje para el usuario y la ruta lo muestra (p. ej. `create_analyzed_job` si la prevalidación Drive↔ZIP falla).
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
- **Uso local sin login** (decisión del usuario, 2026-10-26: trabaja solo en local): con `AUTO_PRIZMA_SIN_LOGIN=<usuario>` (`config.local_login_user()`, se lee en cada petición) el middleware y `GET /login` aceptan como ese usuario las peticiones **desde loopback** (`services.auth.local_login_user_for`, `is_loopback_request`), si el usuario existe y está activo. Desde otra IP se sigue pidiendo login aunque la variable esté definida: nunca definirla en Railway ni en servidores. Sin la variable, todo igual. `main.py` imprime «LOGIN DESACTIVADO…» al arrancar. Cubierto por `tests/test_local_login_bypass.py`. Las credenciales de PRIZMA de cada cargue NO cambian (son de la plataforma).
- `/moodle` y sus endpoints de preview/publicación/reportes requieren sesión y comprueban que el cliente sea loopback. Se habilita localmente porque Chromium aparece en el mismo escritorio para login manual; no se publica en Railway ni en host remoto.
- Rutas principales: ver tabla en `README.md` (sección "Rutas principales"). `/docs` existe pero exige sesión. `/app.css` y `/app.js` son públicas (están en `RUTAS_PUBLICAS`, las usa el login). `/estado-servicio` y `/google/validar-matriz` devuelven JSON (401 sin sesión si se pide JSON).
- Endpoints que usan Playwright sync deben ser `def` (threadpool) o hilos propios, **nunca `async def`**.

## Services

`auth`, `matrix_analysis`, `drive_zip_validation`, `upload_jobs`, `history`, `health`. Reglas:
- La lógica de negocio nueva va aquí, no en las rutas. Las funciones nuevas que los servicios exponen a las rutas tienen nombre en inglés (`create_analyzed_job`, `cancel_job`, ...).
- Un servicio no importa módulos de `api/`.
- `upload_jobs` importa `evaluative_tests.state/execution` DENTRO de `_ejecutar_test_en_cargue` a propósito: es enlace tardío y las pruebas parchean `auto_prizma.evaluative_tests.execution.ejecutar_test_job`; no subir ese import a nivel de módulo. `evaluative_tests` ya no importa `upload_jobs` (usa `services/history`), así que no hay ciclo.
- La creación de jobs de test es única: `evaluative_tests.state.register_test_job` (la usan `/tests/analizar` y `/analizar`).
- `health` (decisión del usuario, 2026-10-07: indicadores reales, no texto fijo): `check_chromium` pregunta a Playwright por la ruta del ejecutable (no abre el navegador; también vale `chromium_headless_shell-<rev>`), `check_prizma` hace un GET a `URL_PRIZMA` (cualquier respuesta < 500 = disponible). Cada resultado se guarda `HEALTH_CHROMIUM_TTL_SECONDS` / `HEALTH_PRIZMA_TTL_SECONDS`. Las páginas pintan lo que haya en memoria (`cached_service_status`, nunca bloquea) y `app.js` pide `/estado-servicio` al cargar y cada 5 min.
- `moodle_resources` analiza matriz/ZIP, controla ownership del job y guarda reportes. Realimentación (2026-10-20, a pedido del usuario): las filas con solo «Nombre del recurso» son **títulos de tema** (`reason: "section-heading"`, se informan aparte, no son error); las filas incompletas guardan qué campos faltan (`missing`). Cada entrada lleva `kind` (`domain.resource_kind`: `h5p`, `infografia`, `video-avatar`, `pdf`, `reto`, `otro`) para seleccionar por tipo y semana en la vista. **Pausar/reanudar/cancelar** (`pause_moodle_publish`, `resume_moodle_publish`, `cancel_moodle_publish`; rutas `POST /moodle/{id}/pausar|reanudar|cancelar`, JSON): actúan entre recursos, nunca a mitad de una subida; el estado `paused` espera en `_wait_while_paused`. `/moodle/{id}/estado` (`public_moodle_status`) devuelve también `results` en vivo (`live_results`), `started_at` y las banderas de pausa/cancelación. El reporte guarda `previewKey` y `kind` por fila (solo JSON; el CSV mantiene sus columnas) para el botón «Reintentar los que no se cargaron». Estado final `cancelled` si se canceló. **Vista** (decisión del usuario, 2026-10-21): mientras se publica, `/moodle/{id}` muestra SOLO la pantalla «Cargue Moodle en progreso» (como `/proceso` del cargue PRIZMA: % y barra, contadores, lista `job["queue"]` con cada recurso pendiente/en curso/resultado, panel con recurso actual y Pausar/Reanudar/Cancelar), sin la tabla de la matriz; al terminar muestra el resultado y la matriz solo con `?vista=previa`. **Sin duplicados** (2026-10-21, el usuario vio recursos repetidos en el curso): (1) `open_week` espera a que cargue la página de la semana (`wait_for_url` con `section=N` + `networkidle`; antes revisaba a los 250 ms la página anterior y no veía nada) y `find_existing_resource` espera a que aparezcan los bloques de la semana; (2) `_published_before`: cualquier registro del historial local cuenta como publicado (antes solo los `verified-`), y también uno de otra versión de la matriz con el mismo curso, semana, título y bloque. `automation/moodle/client.py` es un cliente distinto del motor administrativo PRIZMA; inicia Chromium visible, espera login manual hasta 120 s y conserva perfil aislado por usuario en `DATA_DIR/moodle_profiles/`.

## Integrations

- `integrations/google/oauth.py`: flujo OAuth web con PKCE y `state` (TTL 10 min, ligado al usuario de la sesión), scopes de solo lectura (`config.GOOGLE_SCOPES`), token por usuario en `DATA_DIR/tokens/<slug>-<hash>.json`, refresco automático, descarga de Google Docs para tests.
- `integrations/google/drive.py`: Sheets API (enlace real de la columna G, incluidos Smart Chips; pestaña por `gid`) y Drive API en lotes (`DRIVE_BATCH_MAX`, `DRIVE_PROFUNDIDAD_MAX`). **Solo metadatos**: nunca descarga H5P/PDF.
  - **Sin memoria entre análisis** (corregido el 2026-10-22): `_precargar_referencias_drive_batch` vuelve a consultar en CADA análisis los enlaces `open?id=` (tipo real) y a listar las carpetas. Antes se saltaba lo que ya estaba en `_CACHE_REFERENCIAS_DRIVE`/`_CACHE_CARPETAS_DRIVE`, incluidos los errores: un fallo momentáneo de Google dejaba 40 filas como «NO HAY ARCHIVO EN LA CARPETA» hasta reiniciar el servidor, aunque las carpetas tuvieran el H5P. `_obtener_metadatos_drive_en_lote` reintenta los fallidos (`config.DRIVE_ESPERAS_REINTENTO`) y guarda el motivo (`_texto_error_drive`: 404/403/429) en la entrada `"tipo": "error"`; la fila muestra «NO SE PUDO CONSULTAR EL ENLACE» con ese motivo en vez de «sin archivo».
- `check_sheet_link(url)` (decisión del usuario, 2026-10-07): al pegar el enlace en Inicio, `app.js`/`views.py` llaman a `/google/validar-matriz`, que pide a Sheets solo `properties(title),sheets.properties(sheetId,title)` con la cuenta del usuario y responde `{ok, documento, pestana}` o `{ok: false, motivo, conectar}`. Es solo un aviso: el análisis vuelve a validar todo.
- Cualquier integración nueva va en `integrations/<servicio>/` y lee su configuración de `core/config.py`.

## Automation

- `automation/prizma/engine.py`: motor del cargue de recursos (mezcla aún lectura de matriz, índice ZIP, reporte CSV y Playwright; se dividirá en la fase 7).
- `automation/prizma/engine_overrides.py`: sustituye en el módulo `engine` las funciones `leer_actividades_excel`, `resolver_recurso` y `validar_carpeta_drive_para_actividad` para usar la pestaña objetivo y los recursos ya prevalidados (vía `threading.local`).
- `automation/moodle/client.py`: replica el flujo de MOODLE: pestaña visible de semana, revisión de duplicados en la sección activa, selector original de actividad, nombres manuales para PDF, notificaciones desactivadas, guardado y verificación del módulo. El worker por usuario conserva el Chromium visible entre trabajos.
  - **Modo de edición primero** (decisión del usuario, 2026-10-20): `ensure_edit_mode` activa el interruptor «Modo de edición» (`.editmode-switch-form input[name="setmode"]`, respaldo por rol checkbox) tras el login y en cada `open_course`; si ya está activo no lo pulsa (lo apagaría). Sin él Moodle no muestra «Añade actividad o recursos». Los recursos se publican **desde la semana 1** en adelante (`domain.publish_order`: número de semana y luego fila de la matriz).
  - **Etiquetas sin uso** (decisión del usuario, 2026-10-21): las etiquetas de bloque («Recurso educativo digital», «Recurso educativo audiovisual», «Reto Evaluativo»; `domain.BLOCK_LABELS`) que una semana no usa según la matriz se pueden borrar. `domain.label_cleanup_plan` calcula por semana qué bloques sobran (los videos a cámara/intro/cierre conservan «audiovisual» por precaución; una semana con filas incompletas o de tipo desconocido no se toca) y se guarda en `job["label_plan"]`. Solo si el usuario marca `clean_labels` y en modo `batch` (nunca en la prueba de 1), y solo en las semanas que se están publicando (`job["label_weeks"]`), `_clean_unused_labels` las borra AL FINAL de la publicación (las etiquetas marcan dónde se inserta cada recurso). `client.delete_unused_label`: solo módulos `modtype_label` (o una tarjeta corta con solo ese texto), nunca si hay dos; ⋮ → «Borrar» → confirma «Borrar» solo si el diálogo nombra la etiqueta o el texto de esa misma tarjeta (si no, Cancelar y el error incluye el texto del diálogo). Corregido el 2026-10-21: el diálogo rellena «Esto eliminará X» un instante después de abrirse y X es el nombre interno de la etiqueta (puede diferir en mayúsculas o texto extra); antes se comparaba de inmediato y exacto, y solo se borró 1 de 7. `_dialog_text_with_target` espera hasta 10 s y `_dialog_names_card` compara normalizado. **`open_week`** va directo a la dirección `?section=N` del enlace con el nombre de la semana (aunque esté oculto en el índice lateral); hacer clic fallaba con «element is not visible». Resultado en `job["label_results"]` y `report["labels"]` (`Borrada` / `No estaba` / `No se pudo borrar`). Como pueden faltar etiquetas, `begin_add_resource` inserta antes de la siguiente etiqueta que exista (`_next_present_block`) o con el botón final de la semana; antes daba `DESTINATION_BLOCK_UNAVAILABLE`.
  - **Vista previa organizada** (2026-10-21): resumen en una línea, «Necesitan atención» con lo que hay que corregir, selección por tipo/semana con la opción de etiquetas, y «Recursos por semana» (`<details>` por semana; dentro, un grupo por bloque como en el curso, los bloques sin uso tachados y «Se suben a mano»). Ya no hay tabla plana.
  - **H5P igual que `MOODLE/src/resource-publishers.js`** (corregido el 2026-10-20; el cargue H5P fallaba): (1) **no** se rellena `#id_name` (en "Contenido interactivo" Moodle toma el título del paquete y el campo no es visible: esperarlo agotaba 30 s); (2) el modo Upload se activa con clic en la pestaña visible "Upload" del editor (el radio oculto `input[value="upload"]` solo como respaldo: marcarlo no cambia la pestaña); (3) el `.h5p` se pone directo en el `input[type=file]` del editor (sin el botón «Upload a file» ni diálogo de archivos), luego «Use»; (4) si Moodle rechaza el paquete se pulsa Cancelar y se reporta `H5P_PACKAGE_VALIDATION_FAILED`.
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

- URL: `config.URL_PRIZMA` (`PRIZMA_BASE_URL + "/inicio-sesion"`). Producción por defecto (`admin.prizma.site`); con `AUTO_PRIZMA_URL_PRIZMA` se apunta a otro ambiente, p. ej. el de **pruebas `https://admin.prizma.solutions`** (mismo formulario de login, verificado el 2026-10-07). Fuera de producción la página principal muestra un aviso (`views._aviso_ambiente_prizma`) y `main.py` imprime `PRIZMA: ... (AMBIENTE DE PRUEBAS)`. **Probar cambios del motor siempre en el ambiente de pruebas, nunca en producción.** Decisión del usuario (2026-10-07): la variable se conserva para probar en local; Railway no la define, así que allí siempre se usa producción.
- Credenciales PRIZMA: las escribe el usuario en cada cargue; se validan antes de encolar (`validar_credenciales_prizma`), viajan en el trabajo como `usuario_prizma_temporal`/`contrasena_prizma_temporal` y se eliminan al arrancar el hilo o cancelar. Nunca se persisten. El módulo de tests solo recuerda el **nombre de usuario** PRIZMA (`<raíz>/data/tokens/prizma_<usuario>.json`).
- Equivalencias de nombres de programa: `EQUIVALENCIAS_PROGRAMAS` en `engine.py` (explícitas; sin coincidencia aproximada a propósito).
- Matriz esperada: A1 programa, A2 curso, cabecera "Semana correspondiente" en columna A (primeras 30 filas); columnas A semana, B unidad, D actividad, E categoría, F tipo de recurso, G enlace Drive.
- **Campo Html vs H5P — política TEMPORAL (decisión del usuario, 2026-10-06): mientras se carguen H5P, si el campo "Html" tiene contenido el motor lo VACÍA antes de guardar** (PRIZMA no permite Html y H5P a la vez: "Solo puedes subir un H5P o completar el campo Html, no ambos"). Interruptor: `config.PRIZMA_VACIAR_HTML_CON_H5P` (`True` hoy). Cuando se deje de usar H5P y se implemente HTML, ponerlo en `False`: el motor nunca borrará el Html, cancelará sin guardar y reportará `ERROR_HTML_Y_H5P`.
  - Solo aplica a actividades H5P (o si aparece el aviso). El editor se busca únicamente entre el título "Html" y el título "Recurso…" (`_XPATH_EDITOR_HTML`), así nunca toca la Descripción. Soporta `textarea`, `contenteditable`, CodeMirror y Monaco; se verifica que quedó vacío o que desapareció el aviso (`_vaciar_editor_html`).
  - Dos momentos: antes del primer clic en Guardar (si se detecta contenido) y, si PRIZMA solo avisa al guardar, se vacía y se reintenta el guardado UNA vez (`_resolver_campo_html`, `_intentar_guardado`).
  - El contenido eliminado queda en la columna Observación del reporte CSV (`_observacion_guardado`, clave `html_vaciado` del resultado).
  - Si no se puede vaciar: cancela sin guardar → `ERROR_LIMPIANDO_HTML` + copia de la estructura del campo en `temp/<trabajo>/campo_html_fila_<n>.html` y captura, para ajustar el selector. El editor real es un `<textarea class="htmlCodeField-textarea">` y el selector funciona contra PRIZMA (ambiente de pruebas, 2026-10-07).
- **Formato de los recursos interactivos: H5P o HTML** (decisiones del usuario, 2026-10-06). Se elige en cada cargue (`formato_recurso` en el formulario, el trabajo y el resultado; `FORMATOS_RECURSO_INTERACTIVO`). Solo afecta a las actividades que hoy son H5P (OVA y OVI H5P/infografía): `engine.aplicar_formato_recurso` las convierte a tipo `HTML`; los PDF no cambian. Ojo con los nombres: `tipo_recurso` es el texto de la columna F de la matriz (y los filtros de la tabla); `formato_recurso` es la elección H5P/HTML.
  - Los `.html`/`.htm` vienen en el ZIP (se indexan como `.html`) y se emparejan por nombre con la actividad, con las mismas reglas que el H5P (ambigüedad = fila no cargable). En formato HTML **no** se valida contra Drive (`create_analyzed_job` no llama a la prevalidación; `resultado["drive"]["modo"] == "html"`).
  - En PRIZMA (`procesar_actividad`, rama `es_html`): (1) lee el `.html` completo (`leer_archivo_html`) **antes de tocar el formulario**: si no es UTF-8 o está vacío (`ERROR_HTML_NO_ES_UTF8`/`ERROR_HTML_VACIO`) cancela sin quitar nada de "Recurso"; (2) `_resolver_recurso_para_html` quita **cualquier archivo** que haya en "Recurso", sea H5P o no (decisión del usuario, 2026-10-07: PRIZMA a veces solo muestra el nombre genérico "Archivo"; política `PRIZMA_VACIAR_RECURSO_CON_HTML`, `True` hoy; con `False` cancela y reporta `ERROR_RECURSO_Y_HTML`); (3) `_cargar_html_en_formulario` escribe el código con `fill` y **verifica que el campo quedó idéntico** antes de guardar; (4) guarda y confirma el PATCH como siempre. Si PRIZMA avisa del conflicto al guardar, se quita el archivo y se reintenta una vez. **En formato HTML nunca se borra el Html pegado** (cubierto por `tests/test_html_mode.py`, con pruebas de mutación).
  - Solo se escribe en `textarea`/`input`; con otro tipo de editor se cancela sin guardar (`ERROR_ESCRIBIENDO_HTML: editor no soportado ...`) y se guarda la estructura del campo. Los fallos al quitar el archivo dejan `ERROR_QUITANDO_RECURSO` y `temp/<trabajo>/campo_recurso_fila_<n>.html` (copia del formulario completo).
  - **Estructura real del formulario** (volcada del ambiente de pruebas el 2026-10-07; ver comentario en `html_field.py`): Html = `<textarea class="htmlCodeField-textarea">`; aviso de conflicto = `<p class="form-error">`; archivo = `<p class="form-label">Recurso (H5P)</p>` (en OVI el título es solo "Recurso") + `div.btnFile > div.fileItem` con el nombre (`div.box-info-file > p`) y dos botones **[descargar, papelera]**; la etiqueta de tipo muestra el MIME (`.octet-stream`), no sirve para saber si es H5P. La papelera abre "¿Estás seguro? / ¿Deseas eliminar este archivo?" con Cancelar / **Eliminar**.
  - Retiro del archivo (`quitar_archivo_de_recurso`), tenga el nombre que tenga: pulsa el ÚLTIMO botón de la tarjeta (papelera), exige que aparezca la confirmación (si no, se detiene: así nunca se confunde con el botón de descarga), pulsa Eliminar y verifica que la tarjeta desapareció. Selectores validados en Chromium contra el HTML real volcado (OVA y OVI).
  - Reporte: tipo `HTML` y observación "HTML pegado (N caracteres[, reemplaza el Html previo]) [- se quito el archivo previo de Recurso ("<nombre>")]" (clave `recurso_quitado` del resultado; sin el nombre si PRIZMA no lo muestra).
  - Validación (2026-10-07, ambiente de pruebas): el 1.er intento falló sin guardar nada (el selector suponía una etiqueta `.H5P`; se rehízo con la estructura real), el 2.º también (PRIZMA mostraba el nombre genérico "Archivo" y la regla de entonces solo quitaba `.h5p`) y el 3.º funcionó; el usuario lo aprobó para producción.
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
| `AUTO_PRIZMA_URL_PRIZMA` | al importar | URL de PRIZMA (vacía = producción `https://admin.prizma.site`; pruebas: `https://admin.prizma.solutions`) |
| `AUTO_PRIZMA_SIN_LOGIN` | en cada petición | Usuario con el que se entra sin login, solo desde 127.0.0.1 (vacía = login normal). Solo para uso local |
| `GOOGLE_CLIENT_ID` / `_SECRET` / `_REDIRECT_URI` | en cada llamada | OAuth |

Otros parámetros: `PRIZMA_ESPERAS_REINTENTO_SESION` (reintentos de la sesión inicial), `PRIZMA_VACIAR_HTML_CON_H5P` (política temporal del campo Html en formato H5P), `FORMATOS_RECURSO_INTERACTIVO` / `FORMATO_RECURSO_POR_DEFECTO` / `EXTENSIONES_HTML` / `PRIZMA_VACIAR_RECURSO_CON_HTML` (formato HTML), `CHROMIUM_ARGS`, `VIEWPORT_NAVEGADOR`, límites de Google/Drive, `STATIC_DIR` / `APP_CSS_PATH` / `APP_JS_PATH` (recursos comunes de la interfaz), `HEALTH_CHROMIUM_TTL_SECONDS` / `HEALTH_PRIZMA_TTL_SECONDS` / `HEALTH_PRIZMA_TIMEOUT_SECONDS` (estado del servicio).

Reglas: no leer `os.environ` fuera de `config.py`; añadir constantes nuevas (URLs, límites, timeouts) a `config.py` y a `.env.example` si son variables; mantener el "momento de lectura" al mover algo. Los timeouts de Playwright del motor siguen dispersos en `engine.py` (pendiente fase 7).

## Ejecución

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/manage_users.py crear
python -m uvicorn main:app --reload
```

URL de desarrollo: `http://127.0.0.1:8000`. Para probar contra el ambiente de pruebas de PRIZMA: `$env:AUTO_PRIZMA_URL_PRIZMA = "https://admin.prizma.solutions"` antes de arrancar. `--reload` reinicia el proceso y **pierde los trabajos en memoria**. Producción: `Dockerfile` (`uvicorn main:app --host 0.0.0.0 --port 8000`), desplegado en Railway.

**Despliegue gratuito en Oracle Cloud Always Free** (decisión del usuario, 2026-10-20: no hay presupuesto para servidor; Vercel descartado porque no admite Chromium, procesos largos ni disco persistente). Guía: `docs/DEPLOY_ORACLE.md`. `deploy/oracle/docker-compose.yml` construye el mismo `Dockerfile` (sin modificarlo) y lo pone detrás de **Caddy** (HTTPS automático de Let's Encrypt para `APP_DOMAIN`, subdominio gratis de DuckDNS). Detalles: la app no publica puertos (solo Caddy 80/443); el `command` añade `--proxy-headers --forwarded-allow-ips *` para que el bloqueo de login (`request.client.host`) vea la IP real; `./data` se monta en `/app/data` con `AUTO_PRIZMA_DATA_DIR=/app/data` (cubre también `<raíz>/data/tokens` de los tests evaluativos); la configuración va en `deploy/oracle/.env` (ignorado por git; compose lo lee como `env_file`, la app sigue sin leer `.env`). OAuth funciona detrás del proxy porque `/google/callback` arma `authorization_response` con `GOOGLE_REDIRECT_URI`, no con la URL de la petición. Pendiente de validar en un servidor real (ARM64 `VM.Standard.A1.Flex`).

## Tests

- Framework: **pytest** (incluido en `requirements.txt`). `tests/conftest.py` fija `AUTO_PRIZMA_DATA_DIR` en una carpeta temporal y crea el usuario `adminlocal`. PRIZMA y Playwright están simulados (`unittest.mock.patch`).

```powershell
python -m pytest -q                                   # todo (≈50 s, 340 pruebas al 2026-10-26)
python -m pytest tests/test_test_parser.py -q         # un archivo
python -m pytest tests/test_automation.py -k nombre   # una prueba
```

- Los `patch("auto_prizma.evaluative_tests....")` usan rutas de módulo en texto: al mover/renombrar módulos hay que actualizarlas.
- **Pruebas de caracterización** (`test_engine_characterization.py`, `test_drive_resource_policy.py`): fijan el comportamiento ACTUAL (lectura de matriz, tipo de archivo, índice ZIP, `resolver_recurso`, CSV, reglas de Retos, emparejamiento Drive↔ZIP). Si fallan tras un refactor, el refactor cambió comportamiento: no "arreglar" la prueba sin decidirlo explícitamente. Usan las funciones originales del motor guardadas en `engine_overrides` (`_LEER_ACTIVIDADES_EXCEL_ORIGINAL`, `_RESOLVER_RECURSO_ORIGINAL`), porque al importar `main` el motor queda parcheado.
- Sin cobertura: el motor de cargue real contra PRIZMA, OAuth real, Drive real y la prevalidación Drive↔ZIP en modo link (`_prevalidar_recursos_drive_zip_ultrarapido`, requiere Google).
- `/analizar` escribe en `uploads/` y `temp/` reales (dependen de `BASE_DIR`, no de `AUTO_PRIZMA_DATA_DIR`): las pruebas que lo llamen deben borrar lo que crean (ver la fixture `limpiar_trabajos` en `tests/test_analysis_flow.py`).
- Interfaz: `test_layout.py` (marco en todas las páginas, recursos públicos, contrato de campos del formulario de Inicio), `test_reports_pages.py`, `test_health.py`, `test_sheet_link_check.py`. Para revisar el aspecto: levantar una segunda instancia con `AUTO_PRIZMA_DATA_DIR` temporal (usuario y reportes de ejemplo) en otro puerto y sacar capturas con Playwright en claro/oscuro a 1600 y 400 px; comprobar que `document.documentElement.scrollWidth` no supere el ancho de la ventana.
- Verificación adicional tras refactors: `python -m compileall -q main.py auto_prizma scripts tests` y arrancar uvicorn comprobando `/login` (200) y `/` (303 → `/login`).

## Seguridad

- Nunca escribir contraseñas, tokens ni secretos en el código; configuración sensible solo por variables de entorno.
- Nunca versionar `data/`, `.env`, `client_secret*.json` (ya en `.gitignore`). No leer ni mostrar `data/secreto_sesion.txt`, `data/tokens/*` ni hashes de `usuarios.json` salvo necesidad explícita.
- No registrar credenciales PRIZMA en `print()`, reportes, historial ni en la respuesta de `/estado`. Solo pueden vivir en `usuario_prizma_temporal`/`contrasena_prizma_temporal` del trabajo hasta que arranca el hilo o se cancela. (Hasta el 2026-10-06 `_encolar_trabajo` las copiaba además en `trabajo["credenciales_prizma"]`, que nadie leía y retenía la contraseña en memoria; eliminado y cubierto por `tests/test_upload_jobs.py`.)
- `/moodle` se restringe a loopback y comprueba ownership del trabajo; extrae del ZIP solo `.pdf`/`.h5p` y rechaza rutas absolutas o `..`. El perfil persistente contiene la sesión Moodle del usuario y vive en `DATA_DIR/moodle_profiles/`, fuera de Git.
- Mantener: `state`+PKCE en OAuth, comprobación de usuario en el callback, `hmac.compare_digest`, bloqueo por intentos, comprobación de propietario (`_es_de`) en rutas de trabajos, `os.path.basename` al servir reportes, scopes de Google de solo lectura.

## Git

- Rama principal: `main` (PRs). **Railway despliega cada push a `main`**: lo que llega a `main` llega a producción. Rama de trabajo del usuario: `Jeremy`. Equipo: Kevin Torres, Luis, danilo0413, JIMENEZ45 (aprueba PRs). Commits en español, con prefijos `fix:`/`refactor:`/`docs:`/`chore:`.
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
   - Persistencia de archivos de datos → `core/storage.py` (no escribir JSON a mano).
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

- **Monkeypatching del motor** (`engine_overrides.py`): acople oculto; si se mueve el código parcheado, el parche deja de aplicarse sin error visible. (El parche del botón "Test", `_patch_main_nav`, se eliminó el 2026-10-07: el marco común ya incluye "Test" en todas las páginas.)
- **Sin confirmar: cuándo borra PRIZMA el archivo de "Recurso"** (2026-10-07). Si la papelera lo borra en el servidor al pulsar Eliminar (y no al guardar), un fallo posterior (pegado o guardado) deja la actividad sin archivo y sin HTML aunque el reporte diga "No se guardo nada". Se arregla volviendo a cargarla en formato HTML (ya no habrá archivo que quitar). Para reducir el riesgo, el `.html` se lee y valida antes de quitar nada.
- **`ERROR_PATCH_NO_CONFIRMADO` en actividades con campo Html** (causa encontrada el 2026-10-06): PRIZMA no envía el guardado si el campo "Html" tiene contenido y se sube un H5P. Ahora se vacía el Html (política temporal, ver PRIZMA). Si vuelve a aparecer `ERROR_PATCH_NO_CONFIRMADO`, el mensaje trae el diagnóstico y la captura `temp/<trabajo>/sin_patch_fila_<n>.png`.
- **`print()` con caracteres no ASCII en el motor** (`→`, emojis): si la salida estándar no es UTF-8 (Windows con la salida redirigida a archivo/pipe, p. ej. `uvicorn ... > log.txt`), `resolver_recurso` y otras funciones lanzan `UnicodeEncodeError` en pleno cargue. En Railway (Linux) no ocurre. Mitigación local: `$env:PYTHONIOENCODING = "utf-8"`. Corrección pendiente (fase 7: logging en lugar de `print`).
- **Ruta de datos inconsistente** en `evaluative_tests/state.py`: el usuario PRIZMA recordado se guarda en `<raíz>/data/tokens/` ignorando `AUTO_PRIZMA_DATA_DIR` (en Railway puede no ser persistente). Las pruebas lo confirman: escriben `data/tokens/prizma_adminlocal.json` en el `data/` real (solo `usuario`/`recordar`, sin contraseña). El nombre de archivo usa el usuario sin sanear. Corregirlo cambia dónde se guarda el dato (los usuarios tendrían que reescribir su usuario PRIZMA una vez).
- **Estado en memoria**: trabajos, cola, `state` OAuth y jobs de tests se pierden al reiniciar.
- **Sin limpieza** de `uploads/<id>` y `temp/<id>` tras el cargue (solo si falla la prevalidación).
- `resultados/` no se usa (los reportes van a `DATA_DIR/reportes/`).
- `/cargue-actual` muestra cargues activos de **todos** los usuarios (las acciones sí exigen ser el dueño), aunque el README dice "del usuario".
- Docstring de `_resolver_hoja_objetivo` (`integrations/google/drive.py`) dice que sin `gid` devuelve `None`, pero lanza `ValueError`.
- Código sin uso: `prevalidar_recursos_drive_zip` del motor; scraping público de Drive del motor (anulado por el override); `BackgroundTasks` en `/iniciar`; variable `programa_sugerido` en `evaluative_tests/views.py`. (En la fase 5 se eliminaron 5 funciones muertas y el índice "flexible" de `drive_zip_validation.py`.)
- Archivos grandes pendientes de dividir: `engine.py` (~5800), `web/views.py` (~1300, la mitad es CSS/JS propio de Inicio), `evaluative_tests/automation.py` (~1090), `integrations/google/drive.py` (~920), `evaluative_tests/routes.py` (~910), `services/upload_jobs.py` (~700; candidato: separar creación de trabajos y cola), `services/drive_zip_validation.py` (~680).
- Duplicaciones pendientes: lógica de login en PRIZMA repetida (motor, validación y tests evaluativos). Nombres de archivo: el nombre base y la clave exacta ya están unificados en `domain/file_names.py`; quedan dos normalizaciones con semántica DISTINTA a propósito — `engine.clave_nombre_archivo_exacto` (ignora mayúsculas) y `drive_resource_policy._normalized_name` (canónica: guiones, espacios y mayúsculas). Unificarlas cambiaría qué archivos se emparejan: requiere decisión del usuario.
- **Interfaz**: en las capturas de página completa el fondo blanco del menú lateral termina a la altura de la ventana (el menú es `sticky`); en el navegador no se nota. El módulo de tests conserva su propio CSS (en `evaluative_tests/views.py`, ya con variables de color) con reglas globales (`button`, `input`, `label`, `p`): los controles del marco usan selectores más específicos para no heredarlas.
- `.venv` local creado antes de que `main` añadiera `python-docx`: ejecutar `python -m pip install -r requirements.txt` o la app no arranca.

## Decisiones arquitectónicas

- **Paquete `auto_prizma/` por capas** (core / api / services / integrations / automation / domain / web) + módulos de funcionalidad autocontenidos (`evaluative_tests/`).
- **`main:app` como contrato** de arranque (Dockerfile/Railway); `main.py` solo ensambla.
- **Rutas delgadas y lógica en servicios**: las rutas validan entradas, llaman a `services/` y renderizan; el historial está separado del ciclo de vida de los trabajos (`services/history.py`).
- **Escritura atómica de archivos de datos** en un único módulo (`core/storage.py`).
- **Configuración centralizada** en `core/config.py`; los módulos reexportan los mismos nombres para no romper consumidores; las variables que se leían en cada llamada siguen leyéndose en cada llamada.
- **Overrides del motor al importar** (heredado): el preflight Drive↔ZIP se reutiliza durante el cargue sin volver a consultar Drive. Se planea sustituir por inyección explícita (fase 7).
- **Identidad Drive↔ZIP solo por nombre canónico**; el tamaño es informativo; las ambigüedades no se adivinan (la fila queda no cargable). Diferencias = advertencias, no bloqueo del análisis completo.
- **Solo la pestaña del `gid`** y **solo la columna G** definen qué se procesa y qué carpeta Drive corresponde a cada fila.
- **Google solo lectura y solo metadatos**; token por usuario.
- **Sesión con cookie HMAC sin estado** y usuarios en JSON local gestionados por CLI.
- **Un hilo + un Chromium por cargue**, máximo 2 simultáneos; cancelación cooperativa entre actividades.
- **Moodle es local y separado**: utiliza su matching por matriz/archivo (normaliza prefijos como `H5P -`, `PDF -` e `Infografía -`), jobs y reportes propios, y Chromium visible con login manual; no consume `/analizar` ni el motor administrativo PRIZMA. Los perfiles y reportes viven bajo `DATA_DIR`; los archivos temporales bajo `uploads/moodle/`.
- **HTML renderizado en servidor con un marco común** (`web/layout.py`) y recursos estáticos versionados (`static/app.css`, `static/app.js`). Tema claro/oscuro por variables CSS, recordado en el navegador (`localStorage` `autoPrizmaTema`). Diseño según las imágenes del usuario (2026-10-07). **Tema oscuro negro + violeta** (imagen del usuario, 2026-10-26): fondo `#000000`, paneles `#0b0b0f`/`#131318`, bordes grises tenues `#26262c`, acento violeta `#8b5cf6`/`#7c3aed` con relleno `#1b1233`, verdes `#22c55e`; solo cambian las variables de `html[data-theme="dark"]` en `app.css` (más el degradado de `.boton.grande` y el fondo de `.prizma-loader`), así aplica a todas las páginas.
- **Hora de Colombia** para historial y nombres de reporte.
- **Formato HTML reutilizando el flujo del H5P**: solo cambia el paso de carga (pegar en el campo Html en lugar de subir el archivo); emparejamiento, reporte, historial, cancelación y reintentos son los mismos. El código nuevo de bajo nivel vive en `automation/prizma/html_field.py`, sin dependencias del motor.
