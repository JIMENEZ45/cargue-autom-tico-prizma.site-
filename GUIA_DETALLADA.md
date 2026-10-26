# Auto Prizma Pro — Interfaz de cargue automático

Aplicación web que automatiza el cargue de contenidos académicos en **PRIZMA**. A partir de una matriz de diseño instruccional (Google Sheets, Excel o CSV) y los recursos del curso (ZIP o carpeta de Google Drive), la aplicación entra a PRIZMA con un navegador automatizado y carga las actividades **OVI**, **OVA** y **Retos evaluativos (Challenge)**. También crea **tests evaluativos** a partir de un documento Word (.docx).

Construida con **FastAPI** y **Playwright (Chromium)**. Se despliega en **Railway** con Docker.

---

## Contenido

- [Funcionalidades](#funcionalidades)
- [Cómo funciona](#cómo-funciona)
- [Tecnologías](#tecnologías)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Instalación local](#instalación-local)
- [Variables de entorno y credenciales](#variables-de-entorno-y-credenciales)
- [Configurar Google (OAuth)](#configurar-google-oauth)
- [Administración de usuarios](#administración-de-usuarios)
- [Uso: cargue de actividades](#uso-cargue-de-actividades)
- [Uso: tests evaluativos](#uso-tests-evaluativos)
- [Datos y persistencia](#datos-y-persistencia)
- [Seguridad](#seguridad)
- [Despliegue en Railway](#despliegue-en-railway)
- [Pruebas](#pruebas)
- [Notas para mantenimiento](#notas-para-mantenimiento)
- [Solución de problemas](#solución-de-problemas)

---

## Funcionalidades

- **Inicio de sesión por usuario.** Cada persona ve únicamente sus propios cargues, historial y reportes.
- **Matriz por link o por archivo.** Lee la matriz desde Google Sheets (con la cuenta de Google del usuario) o desde un archivo Excel/CSV subido.
- **Análisis previo.** Antes de cargar nada, muestra qué actividades se encontraron, qué recurso le corresponde a cada una y las advertencias (recurso faltante, diferencias entre Drive y el ZIP, duplicados).
- **Selección de actividades.** El usuario elige qué actividades cargar después de revisar el análisis.
- **Cola de cargues.** Hasta **2 cargues simultáneos**; los demás esperan en cola y se muestra su posición.
- **Seguimiento en vivo.** Página de progreso por cargue, con opción de cancelar.
- **Historial y reportes.** Cada cargue genera un reporte CSV que se puede ver en pantalla o descargar.
- **Tests evaluativos.** Lee un .docx con preguntas, lo valida, permite corregirlo en pantalla y lo crea en PRIZMA. Puede hacerse por separado (`/tests`) o junto con un cargue de actividades.
- **Cargue Moodle local.** En `/moodle` analiza una matriz CSV/XLSX y un ZIP de PDF/H5P, muestra la vista previa por semana y publica en un curso Prizma con Chromium visible e inicio de sesión manual.
- **Tema claro/oscuro** y diseño adaptable a móvil.

---

## Cómo funciona

```mermaid
flowchart LR
    A[Usuario inicia sesión] --> B[Matriz<br/>Sheets / Excel / CSV]
    A --> C[Recursos<br/>ZIP / Drive]
    B --> D[Análisis previo<br/>actividades + recursos + advertencias]
    C --> D
    D --> E[Usuario revisa y<br/>selecciona actividades]
    E --> F[Cola de cargues<br/>máx. 2 a la vez]
    F --> G[Playwright carga<br/>en PRIZMA]
    G --> H[Reporte CSV<br/>+ historial]
```

1. El usuario inicia sesión y, si va a usar la matriz por link, conecta su cuenta de Google.
2. Suministra la matriz y el ZIP, y marca las categorías a cargar (OVI, OVA, Retos, Test evaluativo).
3. La aplicación analiza la matriz, relaciona cada actividad con su recurso y muestra el resultado.
4. El usuario selecciona las actividades, ingresa sus credenciales de PRIZMA e inicia el cargue.
5. El cargue entra en la cola; un navegador Chromium sin interfaz entra a PRIZMA y carga cada actividad.
6. Al terminar se guarda el reporte y queda registrado en el historial.

---

## Tecnologías

| Componente | Uso |
|---|---|
| Python 3.12 | Lenguaje (imagen Docker `python:3.12-bookworm`) |
| FastAPI + Uvicorn | Servidor web y rutas |
| Playwright (Chromium) | Automatización del navegador en PRIZMA |
| openpyxl | Lectura y escritura de matrices Excel |
| python-docx | Lectura de los tests en Word |
| Google API Client + OAuth | Lectura de Google Sheets y Google Drive (solo lectura) |
| pytest | Pruebas automáticas |

---

## Estructura del proyecto

```
main.py                       Punto de entrada: arma la app (uvicorn main:app)
auto_prizma/                  Código de la aplicación
  core/
    application.py            Instancia FastAPI compartida
    config.py                 Configuración central: carpetas, variables de entorno, sesión,
                              límites de Google/Drive, cola de cargues, URL de PRIZMA y navegador
    storage.py                Lectura y escritura atómica de archivos de datos (JSON y texto)
    clock.py                  Hora de Colombia para historial, reportes y estados
  api/routes/                 Rutas web (cada módulo registra sus rutas sobre la app)
    static_files.py           Logo y recursos comunes de la interfaz (/app.css y /app.js)
    auth.py                   Middleware de sesión, login, salir y cambio de contraseña
    google.py                 Conectar / desconectar Google
    analysis.py               Inicio y análisis previo al cargue
    uploads.py                Iniciar, seguir, cancelar y estado de cargues
    reports.py                Historial, reportes guardados y descargas
    health.py                 Estado del servicio en JSON (Chromium y PRIZMA)
    moodle_resources.py       Vista previa, publicación y reportes del cargue Moodle local
  services/                   Lógica de negocio
    auth.py                   Usuarios, contraseñas, bloqueo por intentos y cookies de sesión
    matrix_analysis.py        Lectura de la matriz (CSV/Excel/Sheets) y análisis de matriz y ZIP
    drive_zip_validation.py   Relación Drive ↔ ZIP, avisos y prevalidación rápida
    upload_jobs.py            Estado de cargues, cola de ejecución y servicios que usan las rutas
                              (crear, iniciar, cancelar y consultar trabajos)
    history.py                Historial de cargues y reportes CSV (por usuario)
    health.py                 Comprueba que Chromium esté instalado y que PRIZMA responda
    moodle_resources.py       Lee matrices, extrae el ZIP, arma la vista previa y controla la publicación Moodle
  integrations/google/        Integración con Google
    oauth.py                  Conexión OAuth con Google por usuario
    drive.py                  Lectura de enlaces en Google Sheets, listado de carpetas de Drive y
                              comprobación del enlace de la matriz al pegarlo
  automation/prizma/          Automatización de PRIZMA con Playwright
    engine.py                 Motor de cargue: lectura de la matriz y automatización de PRIZMA
    engine_overrides.py       Ajustes que se aplican sobre el motor al arrancar
    html_field.py             Formato HTML: leer el .html, escribirlo en el campo Html y quitar el archivo previo de Recurso
  automation/moodle/          Cliente visible para cursos Moodle/Prizma
    client.py                 Inicio de sesión manual, detección de duplicados, publicación PDF/H5P y borrado de etiquetas
  domain/
    drive_resource_policy.py  Reglas para decidir qué recurso de Drive corresponde a cada actividad
    file_names.py             Nombre base y clave exacta de nombres de archivo
    moodle_resources.py       Reglas de destinos, tipos de recurso, orden por semana y etiquetas sin uso (Moodle)
  web/
    layout.py                 Marco común de todas las páginas: menú lateral, estado del servicio,
                              tema claro/oscuro y menú del usuario
    icons.py                  Íconos SVG de la interfaz
    views.py                  Página de Inicio (análisis) y revisión antes del cargue
    moodle_views.py           Vista previa, progreso y reporte del cargue Moodle
  evaluative_tests/           Módulo de tests evaluativos (cuestionarios en PRIZMA a partir de un .docx)
    models.py                 Estructuras de datos del documento (tests, secciones, preguntas)
    parser.py                 Lectura del .docx y conversión a esas estructuras
    validation.py             Validación del documento (errores y advertencias)
    serializer.py             Exportación a JSON
    automation.py             Automatización de PRIZMA con Playwright para crear los tests
    state.py                  Estado en memoria de los trabajos y usuario de PRIZMA recordado
    views.py                  HTML del módulo (layout, revisión y tarjeta de estado)
    execution.py              Ejecución del cargue de tests en segundo plano
    routes.py                 Rutas /tests/...
scripts/
  manage_users.py             Herramienta de consola para administrar usuarios
  check_prizma_connection.py  Prueba manual de conexión con PRIZMA (navegador visible)
static/                       Logo, app.css (estilos comunes) y app.js (comportamiento común de la interfaz)
.env.example                  Variables de entorno soportadas (sin valores)
tests/                      Pruebas automáticas (pytest)
uploads/ temp/ resultados/  Archivos de trabajo generados en ejecución (no se versionan)
data/                       Usuarios, tokens, historial y reportes (no se versiona; contiene secretos)
Dockerfile                  Imagen para despliegue
```

### Rutas principales

| Ruta | Descripción |
|---|---|
| `GET /login`, `POST /login` | Inicio de sesión |
| `GET /salir` | Cerrar sesión |
| `GET/POST /cambiar-clave` | Cambio de contraseña del usuario |
| `GET /` | Inicio: formulario de matriz, recursos y categorías |
| `POST /analizar` | Análisis previo de la matriz y los recursos |
| `POST /iniciar/{trabajo_id}` | Inicia (encola) el cargue con las actividades seleccionadas |
| `GET /cargue-actual` | Cargues en curso del usuario |
| `GET /proceso/{trabajo_id}` | Progreso de un cargue |
| `GET /estado/{trabajo_id}` | Estado del cargue en JSON (lo consulta la página de progreso) |
| `POST /cancelar/{trabajo_id}` | Cancela un cargue |
| `GET /historial`, `GET /reportes` | Historial de cargues y reportes generados |
| `GET /reporte/{trabajo_id}`, `GET /reporte-guardado/{registro_id}` | Ver o descargar un reporte |
| `GET /google/conectar`, `GET /google/callback`, `POST /google/desconectar` | Conexión de la cuenta de Google |
| `GET /google/validar-matriz?url=...` | Comprueba el enlace de Google Sheets al pegarlo en Inicio (JSON) |
| `GET /estado-servicio` | Estado de Chromium y de PRIZMA (JSON; lo consultan todas las páginas) |
| `GET /app.css`, `GET /app.js` | Estilos y script comunes de la interfaz (públicos) |
| `GET /tests` y `/tests/...` | Módulo de tests evaluativos |
| `GET /moodle` y `/moodle/...` | Análisis, vista previa y publicación Moodle local (solo desde el mismo equipo) |

---

## Instalación local

**Requisitos:** Windows 10/11 (los ejemplos siguientes son PowerShell), Git y Python 3.12 o posterior. Para usar el cargue Moodle local, ejecuta el servidor directamente en tu equipo: necesita abrir Chromium visible en tu escritorio.

```powershell
git clone https://github.com/JIMENEZ45/cargue-autom-tico-prizma.site-.git
Set-Location cargue-autom-tico-prizma.site-

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

`requirements-dev.txt` instala la aplicación y pytest. No se necesita Node.js para ejecutar Auto Prizma; MOODLE ya está integrado en la aplicación Python. Para instalar las dependencias de producción solamente, usa `requirements.txt` en lugar de `requirements-dev.txt`.

Antes de arrancar, decide si usarás el panel administrativo PRIZMA de pruebas o producción. **Para desarrollo, apunta al ambiente de pruebas** y configura las variables en la misma ventana de PowerShell. No configures OAuth si solo vas a usar matrices CSV/XLSX:

```powershell
$env:AUTO_PRIZMA_URL_PRIZMA = 'https://admin.prizma.solutions'
$env:AUTO_PRIZMA_SECRET = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))").Trim()
# Opcional: carpeta persistente fuera del repositorio.
# $env:AUTO_PRIZMA_DATA_DIR = 'C:\AutoPrizma\data'
```

Si usarás Sheets o Google Docs, define también las tres variables OAuth descritas en **Crear credenciales de Google OAuth**. Después crea el usuario local de Auto Prizma:

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py crear
```

El comando pide usuario y contraseña dos veces; la contraseña no aparece en pantalla y debe tener al menos 8 caracteres. Después inicia el servidor en el mismo terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Abre exactamente `http://127.0.0.1:8000` e inicia sesión con el usuario recién creado. Mantén el terminal abierto mientras uses la aplicación; `Ctrl+C` detiene el servidor. No uses `localhost` para el flujo OAuth: el URI de retorno local está registrado como `127.0.0.1`.

**Importante:** si omites `AUTO_PRIZMA_URL_PRIZMA`, el panel administrativo apunta a producción. No ejecutes un cargue real para “probar”; usa el ambiente de pruebas y datos autorizados. El cargue Moodle publica en el curso de la URL que ingreses.

En Linux/macOS los ejecutables están en `.venv/bin/`. Instala Chromium con `python -m playwright install --with-deps chromium` (Linux) y arranca con `python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload`.

---

## Variables de entorno y credenciales

La referencia completa de variables sin valores está en `.env.example`. **La aplicación no lee archivos `.env` automáticamente**: define las variables en el entorno antes de arrancar Uvicorn, o configúralas en el servicio de despliegue. En PowerShell, `$env:NOMBRE = "valor"` solo afecta esa ventana y sus procesos hijos; vuelve a definirlas al abrir otro terminal.

### Variables de la aplicación

| Variable | ¿Obligatoria? | Uso y valor predeterminado |
|---|---:|---|
| `AUTO_PRIZMA_DATA_DIR` | No | Carpeta para usuarios, tokens, sesión, historial, reportes y perfil Moodle. Predeterminado: `<proyecto>\data`. En local puedes dejar el predeterminado o elegir una ruta persistente fuera del repositorio. |
| `AUTO_PRIZMA_SECRET` | No | Clave de firma de las cookies de sesión. Si se omite, la app crea `data/secreto_sesion.txt`; define una para conservar sesiones de forma estable. |
| `AUTO_PRIZMA_COOKIE_SECURE` | No | Déjala sin definir para `http://127.0.0.1`. `1` fuerza la cookie `Secure`; también se activa automáticamente si `GOOGLE_REDIRECT_URI` usa HTTPS. |
| `AUTO_PRIZMA_MAX_SIMULTANEOS` | No | Cargues administrativos simultáneos: `1` o `2`. Predeterminado: `2`. |
| `AUTO_PRIZMA_URL_PRIZMA` | No | URL base del **panel administrativo** PRIZMA. Vacía = producción `https://admin.prizma.site`. El ambiente de pruebas es `https://admin.prizma.solutions`. |
| `GOOGLE_CLIENT_ID` | Solo Google | ID del cliente OAuth tipo aplicación web, obtenido en Google Cloud Console. |
| `GOOGLE_CLIENT_SECRET` | Solo Google | Secreto de ese cliente OAuth; mantenlo fuera de Git y no lo compartas. |
| `GOOGLE_REDIRECT_URI` | Solo Google | URI local exacta: `http://127.0.0.1:8000/google/callback`. Debe registrarse también en Google Cloud Console. |

Para crear una clave local `AUTO_PRIZMA_SECRET` aleatoria en PowerShell:

```powershell
$env:AUTO_PRIZMA_SECRET = (& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))").Trim()
```

La app acepta el secreto en memoria del entorno y no lo muestra. No lo pegues en el README, el código, capturas o reportes. Si no defines la variable, la clave se genera y guarda localmente en `data/secreto_sesion.txt`, que está excluido de Git. Mantén el mismo secreto entre reinicios para conservar las sesiones firmadas.

### Crear credenciales de Google OAuth

Esto solo hace falta para leer matrices por enlace Google Sheets y Google Docs usados por los tests. Para matrices locales CSV/XLSX, el login de Auto Prizma, PRIZMA o Moodle, no necesitas configurar OAuth.

1. En [Google Cloud Console](https://console.cloud.google.com/) crea o selecciona un proyecto.
2. Habilita **Google Sheets API** y **Google Drive API**.
3. Configura la pantalla de consentimiento OAuth. Si la aplicación queda en modo de prueba, agrega como usuario de prueba cada cuenta Google que se conectará.
4. Crea un **ID de cliente OAuth** de tipo **Aplicación web**.
5. En **URI de redireccionamiento autorizados**, registra exactamente `http://127.0.0.1:8000/google/callback`.
6. Define las credenciales en el mismo PowerShell antes de arrancar:

   ```powershell
   $env:GOOGLE_CLIENT_ID = '<ID de cliente>'
   $env:GOOGLE_CLIENT_SECRET = '<secreto del cliente>'
   $env:GOOGLE_REDIRECT_URI = 'http://127.0.0.1:8000/google/callback'
   ```

   Los valores entre `< >` son marcadores: reemplázalos localmente y no subas esos valores a Git.

7. Inicia sesión en Auto Prizma y pulsa **Conectar Google**. Cada usuario autoriza su propia cuenta; la app solicita permisos de solo lectura para Sheets y Drive. El token autorizado se guarda en `data/tokens/` (o en `AUTO_PRIZMA_DATA_DIR/tokens/`).

### Qué credenciales usa cada flujo

| Credencial | Cómo se crea/ingresa | ¿Se guarda? |
|---|---|---|
| Usuario y contraseña de **Auto Prizma** | Crea el usuario con `scripts/manage_users.py crear`. | Contraseña cifrada en `usuarios.json`. |
| Cuenta de **Google** | Crea el cliente OAuth una vez; cada usuario conecta su cuenta desde la interfaz. | Token OAuth local por usuario; solo lectura. |
| Cuenta del panel **PRIZMA** (`admin.prizma.site`) | La persona la ingresa cuando inicia un cargue administrativo. | No; se usa temporalmente durante ese cargue. |
| Sesión del curso **Moodle/Prizma** | Inicia sesión manualmente en la ventana Chromium visible que abre `/moodle`. | Se conserva en el perfil local de Chromium de ese usuario; la contraseña no se almacena. |

`AUTO_PRIZMA_URL_PRIZMA` configura el panel administrativo y no cambia el dominio del curso Moodle. El cargue Moodle requiere abrir Auto Prizma desde el mismo equipo en `http://127.0.0.1:8000`; no está disponible desde Railway, Oracle Cloud u otro servidor remoto.

Las cuentas del panel administrativo PRIZMA y del curso Moodle las proporciona tu institución. Auto Prizma no las crea: solo crea usuarios para entrar a la aplicación local.

### Usar el ambiente de pruebas del panel PRIZMA

Para evitar modificar producción mientras validas el flujo administrativo, define la URL **antes de iniciar Uvicorn**:

```powershell
$env:AUTO_PRIZMA_URL_PRIZMA = 'https://admin.prizma.solutions'
```

Después arranca la aplicación como se indicó arriba. Verás un aviso de ambiente de pruebas. Las credenciales que ingreses deben corresponder a ese ambiente. Para volver a producción, cierra el terminal o ejecuta `Remove-Item Env:AUTO_PRIZMA_URL_PRIZMA` y reinicia. La variable se lee al importar la app. El flujo Moodle sigue usando la dirección del curso que ingreses en `/moodle`.

---

## Configurar Google (OAuth)

La matriz por enlace usa Google Sheets y Drive con permisos de solo lectura. Sigue los pasos de **Crear credenciales de Google OAuth** en la sección de variables. Cada usuario conecta su propia cuenta desde **Conectar Google**; su token se guarda localmente por usuario y puede desconectarlo desde el menú.

---

## Administración de usuarios

Los usuarios se gestionan desde la consola con `scripts/manage_users.py`. Todas las opciones piden los datos de forma interactiva y la contraseña no se muestra en pantalla.

```powershell
.\.venv\Scripts\python.exe scripts\manage_users.py listar       # Lista usuarios y si tienen Google conectado
.\.venv\Scripts\python.exe scripts\manage_users.py crear        # Crea un usuario
.\.venv\Scripts\python.exe scripts\manage_users.py clave        # Cambia la contraseña de un usuario
.\.venv\Scripts\python.exe scripts\manage_users.py desactivar   # Impide el acceso sin borrar el usuario
.\.venv\Scripts\python.exe scripts\manage_users.py activar      # Vuelve a permitir el acceso
.\.venv\Scripts\python.exe scripts\manage_users.py borrar       # Elimina usuario y token Google (pide confirmación)
```

La contraseña debe tener al menos 8 caracteres. Cada usuario también puede cambiar la suya desde **Mi contraseña** dentro de la app.

> En Railway estos comandos se ejecutan desde la consola del servicio, para que actúen sobre el volumen de datos de producción.

---

## Uso: cargue de actividades

### Formato de la matriz

La matriz puede tener varias hojas; cada hoja que tenga la cabecera esperada se procesa como un curso.

| Celda / columna | Contenido |
|---|---|
| `A1` | Nombre del programa |
| `A2` | Nombre del curso (si está vacío se usa el nombre de la hoja) |
| Columna `A` (fila de cabecera) | El texto **Semana correspondiente**, en alguna de las primeras 30 filas. Las actividades empiezan en la fila siguiente. |
| Columna `A` | Semana |
| Columna `B` | Unidad |
| Columna `D` | Nombre de la actividad |
| Columna `E` | Categoría: `OVI`, `OVA` o `Challenge` (reto evaluativo). Las filas con otra categoría se ignoran. |
| Columna `F` | Tipo de recurso |
| Columna `G` | Enlace al recurso (por ejemplo, el enlace de Google Drive) |

Las filas sin nombre o sin categoría se omiten.

### Pasos en la aplicación

1. **Matriz:** elegir *Por link* (pegar el enlace de Google Sheets; requiere Google conectado) o *Por archivo* (subir `.xlsx` o `.csv`; no requiere Google). Al pegar el enlace, la app comprueba con tu cuenta de Google que la hoja y la pestaña existan y se puedan leer, y muestra *Enlace válido* o el motivo del problema.
2. **Recursos:** subir el ZIP con los archivos H5P (o HTML) y PDF de las actividades.
3. **Categorías:** marcar OVI, OVA, Retos evaluativos y/o Test evaluativo, y elegir el **formato de los recursos interactivos**: *H5P* o *HTML* (ver abajo).
4. **Analizar:** revisar las actividades encontradas, el recurso asignado a cada una y las advertencias.
5. **Iniciar:** seleccionar las actividades, ingresar usuario y contraseña de PRIZMA e iniciar. Si ya hay 2 cargues en curso, el nuevo espera en cola.
6. **Seguimiento:** ver el avance en *Cargue actual*; se puede cancelar en cualquier momento.

Arriba a la derecha están el botón de tema claro/oscuro y el menú del usuario (*Mi contraseña*, *Desconectar Google*, *Salir*). Los indicadores de Inicio y la tarjeta del menú lateral muestran el estado real: *Chromium activo* si el navegador de Playwright está instalado y *Servicio estable* si PRIZMA responde (se comprueba cada pocos minutos). *Ver guía* abre los pasos y consejos. En *Reportes* se puede buscar, filtrar por programa, curso y fecha, ordenar columnas y copiar el enlace de un reporte; en el detalle, buscar en la tabla y copiar la observación de una fila.

### Formato H5P o HTML

Las actividades con recurso interactivo (OVA y OVI de tipo H5P o infografía) se pueden cargar de dos formas; los PDF no cambian:

- **H5P:** el archivo `.h5p` del ZIP se sube al campo *Recurso* de la actividad.
- **HTML:** el código completo del archivo `.html` (o `.htm`) del ZIP se pega en el campo *Html* de la actividad.
  - Cada archivo debe llamarse igual que su actividad (por ejemplo `Presupuestar Paso a Paso.html`); si dos archivos coinciden con la misma actividad, la fila no se carga.
  - El archivo debe estar en UTF-8 y ser **autocontenido**: CSS, JavaScript e imágenes incrustados o con URL absoluta (las rutas relativas no funcionan una vez pegado en PRIZMA).
  - Antes de guardar se verifica que el campo Html quedó idéntico al archivo.
  - PRIZMA no permite un archivo en *Recurso* y Html a la vez: si la actividad ya tenía **cualquier archivo** en *Recurso* (un H5P u otro; a veces PRIZMA solo lo muestra como "Archivo"), se elimina (papelera y confirmación *Eliminar*) y queda anotado en el reporte con su nombre (configurable con `PRIZMA_VACIAR_RECURSO_CON_HTML` en `auto_prizma/core/config.py`). Antes de quitar nada se comprueba que el `.html` se puede leer; si no, la actividad no se toca.
  - En formato HTML no se valida contra las carpetas de Drive de la columna G: los HTML solo vienen en el ZIP.

### Reporte

Cada cargue genera un CSV con las columnas: `Fila Excel`, `Programa`, `Curso`, `Semana`, `Unidad`, `Actividad`, `Categoría`, `Tipo`, `Recurso`, `Resultado` y `Observación`. Se consulta en **Reportes** o **Historial**.

---

## Uso: cargue Moodle

El apartado **Cargue Moodle** (`/moodle`) publica recursos PDF y H5P directamente en un curso de Prizma (Moodle). Es independiente del cargue del panel administrativo (`/analizar`).

1. Ejecuta Auto Prizma **en el mismo equipo** donde vas a iniciar sesión y abre `http://127.0.0.1:8000/moodle`. No está disponible desde un servidor remoto (Railway u Oracle Cloud), porque necesita abrir Chromium visible en tu escritorio.
2. Sube la matriz exportada (CSV/XLSX), el ZIP con los PDF/H5P y el enlace HTTPS del curso (`prizma.americana.edu.co/course/view.php?id=...`) y pulsa **Generar vista previa**.
3. Revisa la vista previa:
   - Un resumen (listos para publicar, por corregir, se suben a mano, semanas) y la lista **«Necesitan atención»** con lo que falta corregir en el ZIP o la matriz y por qué.
   - **«Recursos por semana»**, organizada como el curso: cada semana con sus bloques *Recurso educativo digital*, *Recurso educativo audiovisual* y *Reto Evaluativo*. Los títulos de tema de la matriz se ignoran (no son recursos).
   - Cada archivo se empareja por nombre con el «Nombre del recurso»; se quitan prefijos como `H5P -`, `PDF -` o `Infografía -`. Si varios archivos coinciden, la fila no se publica.
4. En **«¿Qué quieres publicar?»** marca tipos de recurso (H5P, infografía, video avatar, PDF, reto) y semanas, o filas sueltas. Usa **Probar con 1 recurso** primero y luego **Publicar seleccionados**.
5. Se abre Chromium: inicia sesión a mano (se espera hasta 2 minutos). La app activa el **Modo de edición**, publica **desde la semana 1** y, antes de cada recurso, comprueba si ya está en la semana para **no duplicarlo**. La pantalla muestra el avance en vivo y permite **Pausar**, **Reanudar** y **Cancelar** (actúan entre recursos, nunca a mitad de una subida).
6. Opcional: marca **«Al terminar, borrar las etiquetas que la matriz no usa»**. Al final, en cada semana publicada, borra las etiquetas de bloque sin recursos en la matriz (⋮ → Borrar → confirmar). Nunca en la prueba de 1 recurso y nunca recursos, solo etiquetas. No se puede deshacer.
7. Revisa el resultado (con **Reintentar los que no se cargaron**) y descarga el reporte CSV/JSON.

Los archivos de trabajo quedan en `uploads/moodle/`, los reportes en `data/reportes/moodle/` y el perfil local de Chromium (con la sesión de Moodle, sin contraseña) en `data/moodle_profiles/`. La matriz original no se modifica.

---

## Uso: tests evaluativos

Los tests se crean en PRIZMA a partir de un documento Word. Se pueden cargar desde **Test** (`/tests`) o marcando *Test evaluativo* en el cargue de actividades. En este último caso se piden los datos académicos en el formato `CódigoPrograma CódigoPensum CódigoAsignatura NombreAsignatura`, separados por espacios o guiones, y el semestre.

### Formato del documento (.docx)

- **Título:** una línea como `Título del TEST` seguida del nombre del test.
- **Semana y corte:** por ejemplo `Semana 1 - Corte 1`.
- **Secciones:** un encabezado por tipo de pregunta:
  - `Verdadero/Falso`
  - `Selección múltiple`, `Única respuesta` u `Opción múltiple`
  - `Emparejamiento` o `Relacione`
  - `Pregunta abierta` o `Respuesta corta`
- **Preguntas** numeradas: `1. Enunciado...`
- **Respuesta correcta** al final de la pregunta o en una línea aparte:
  - Verdadero/falso: `[R: Verdadero]`, `[R: F]` o `(V)`
  - Selección: `[R: b]` o `Respuesta: b`

Ejemplo:

```text
Título del TEST
Prueba de conocimientos
Semana 1 - Corte 1
Verdadero/Falso
1. El sol es una estrella. [R: Verdadero]
Selección múltiple
2. ¿Cuánto es 2 + 2? a) 3 b) 4 c) 5 [R: b]
```

También acepta encabezados en inglés, francés y portugués (por ejemplo `True/False`, `Multiple choice`, `Matching`).

### Flujo

1. Subir el .docx o pegar el enlace de un Google Doc.
2. Revisar el resultado: la app marca en rojo las preguntas con errores (por ejemplo, sin respuesta correcta) y permite corregir títulos y enunciados en pantalla.
3. Ejecutar en PRIZMA. Si la asignatura de los datos no coincide exactamente, la app pide elegir la asignatura correcta entre las que encontró y reutiliza esa elección para los siguientes tests.
4. Seguir el avance en la página de estado. También existe un modo de **solo simulación**, que recorre el proceso sin guardar en PRIZMA.

---

## Datos y persistencia

Todo lo que debe sobrevivir a un reinicio se guarda en `AUTO_PRIZMA_DATA_DIR` (por defecto `data/`):

| Archivo / carpeta | Contenido |
|---|---|
| `usuarios.json` | Usuarios de la app con su contraseña cifrada |
| `secreto_sesion.txt` | Clave de firma de cookies (si no se usa `AUTO_PRIZMA_SECRET`) |
| `tokens/` | Tokens de Google de cada usuario |
| `historial.json` | Registro de cargues realizados |
| `reportes/` | Reportes CSV de cada cargue |
| `reportes/moodle/` | Reportes JSON/CSV de los cargues Moodle |
| `moodle_profiles/` | Perfil local de Chromium para Moodle, separado por usuario |

Las carpetas `uploads/` y `temp/` guardan archivos de trabajo temporales.

> **Importante:** el módulo de tests guarda el **usuario** de PRIZMA recordado (nunca la contraseña) en `<proyecto>/data/tokens/prizma_<usuario>.json`. Esta ruta es fija y no usa `AUTO_PRIZMA_DATA_DIR`.

La carpeta `data/` está en `.gitignore` y **nunca debe subirse al repositorio**.

---

## Seguridad

- **Contraseñas de la app:** se guardan con PBKDF2-SHA256 (240 000 iteraciones y sal propia por usuario); nunca en texto plano.
- **Sesión:** cookie firmada con HMAC-SHA256 que dura 12 horas. El servidor no guarda sesiones, así que reiniciar no cierra las sesiones abiertas.
- **Intentos fallidos:** tras 5 intentos fallidos el acceso se bloquea 120 segundos.
- **Aislamiento entre usuarios:** cada persona solo ve y controla sus propios cargues, reportes e historial.
- **Credenciales de PRIZMA:** se piden en cada cargue y se mantienen solo en memoria mientras dura; no se escriben en archivos.
- **Moodle local:** `/moodle` solo acepta solicitudes desde el mismo equipo (loopback) y cada usuario solo ve sus trabajos. El perfil de Chromium guarda la sesión de Moodle por usuario en `data/moodle_profiles/`, nunca la contraseña.
- **Google:** cada usuario autoriza su propia cuenta, con permisos de solo lectura.

---

## Despliegue en Railway

El proyecto se despliega con el `Dockerfile` del repositorio:

- Imagen base `python:3.12-bookworm`, instala las dependencias y Chromium con `playwright install --with-deps chromium`.
- Arranca con `uvicorn main:app --host 0.0.0.0 --port 8000`.

**Despliegue automático:** cada `push` a la rama `main` dispara un nuevo despliegue en Railway.

Configuración recomendada del servicio:

1. **Volumen persistente** montado, por ejemplo, en `/app/data`, y `AUTO_PRIZMA_DATA_DIR=/app/data` para no perder usuarios, tokens ni reportes en cada despliegue.
2. **Variables de entorno:** `AUTO_PRIZMA_SECRET` (una cadena larga y aleatoria) y las de Google, con `GOOGLE_REDIRECT_URI=https://<dominio>/google/callback`.
3. **Red:** el contenedor escucha en el puerto **8000**.
4. **Volver atrás:** si un despliegue falla, en *Deployments* se puede hacer *Rollback* al anterior.

### Alternativa gratuita: Oracle Cloud Always Free

Para desplegar sin pagar servidor, en una máquina virtual gratuita de Oracle Cloud con HTTPS automático (Caddy) y un subdominio gratis (DuckDNS): ver [`docs/DEPLOY_ORACLE.md`](docs/DEPLOY_ORACLE.md). Los archivos están en `deploy/oracle/` y reutilizan el mismo `Dockerfile`. El cargue Moodle no funciona allí (necesita Chromium visible en tu equipo).

---

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas usan una carpeta de datos temporal (ver `tests/conftest.py`), así que no tocan los usuarios ni los reportes reales. Las pruebas de automatización simulan PRIZMA: no abren el navegador ni se conectan al sitio real.

Para probar manualmente la conexión con PRIZMA (abre un navegador visible y espera el inicio de sesión, sin modificar nada):

```powershell
.\.venv\Scripts\python scripts\check_prizma_connection.py
```

---

## Notas para mantenimiento

- **Orden de arranque (`main.py`):** primero se importa `auto_prizma.automation.prizma.engine_overrides`, que reemplaza en memoria algunas funciones del motor (`auto_prizma/automation/prizma/engine.py`) (`leer_actividades_excel`, `resolver_recurso`, `validar_carpeta_drive_para_actividad`), y luego se registran las rutas. Al modificar esas funciones hay que revisar ambos archivos.
- **Páginas nuevas:** se arman con `render_page(...)` de `auto_prizma/web/layout.py` (menú, tema y usuario ya incluidos); los colores son variables de `static/app.css`, así el tema oscuro funciona sin reglas extra.
- **Equivalencias de programas:** si PRIZMA usa un nombre de programa distinto al de la matriz, se agrega explícitamente en `EQUIVALENCIAS_PROGRAMAS` (`auto_prizma/automation/prizma/engine.py`). No se usa coincidencia aproximada a propósito.
- **Límite de navegadores:** el máximo de 2 cargues simultáneos está fijado en `auto_prizma/core/config.py` para no saturar el servidor.
- **Respaldos:** no guardes copias como `main_backup_*.py`; git ya conserva cada versión (`git log -- archivo`, `git show <commit>:archivo`).

---

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| Al conectar Google aparece *"Faltan variables de entorno de Google"* | Definir `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI`. |
| Google responde *redirect_uri_mismatch* | La URL de `GOOGLE_REDIRECT_URI` debe estar registrada exactamente igual en Google Cloud Console. |
| *"La autorizacion de Google expiro"* | El proceso de autorización dura 10 minutos; volver a pulsar **Conectar con Google**. |
| No permite iniciar sesión tras varios intentos | Bloqueo de 120 segundos después de 5 intentos fallidos; esperar e intentar de nuevo. |
| Tras un despliegue desaparecieron los usuarios o reportes | Falta el volumen persistente o `AUTO_PRIZMA_DATA_DIR` no apunta a él. |
| En el log aparece *"AVISO: existe data/google_token.json"* | Es un token compartido de una versión anterior que ya no se usa; revocarlo en https://myaccount.google.com/permissions y borrar el archivo. |
| Una hoja de la matriz no aparece en el análisis | Revisar que la columna A tenga el texto **Semana correspondiente** en alguna de las primeras 30 filas. |
| `ModuleNotFoundError: playwright` o falta el ejecutable Chromium | Desde la raíz instala `requirements-dev.txt` y ejecuta `.\.venv\Scripts\python.exe -m playwright install chromium`. |
| La autorización Google falla con `redirect_uri_mismatch` | Usa el mismo host y puerto al abrir la app y en Google Cloud: `127.0.0.1:8000`; la ruta debe terminar en `/google/callback`. |
| `/moodle` muestra que solo está disponible localmente | Abre la app en el mismo equipo con `http://127.0.0.1:8000`; la ruta no funciona en Railway, Oracle Cloud ni por una IP remota. |
| Moodle no reconoce un `.h5p` | Revisa que la vista previa muestre una coincidencia única, que el nombre corresponda al recurso y que el ZIP incluya el `.h5p`. Durante publicación debe abrirse Chromium visible; completa allí el inicio de sesión y deja la ventana abierta. |
| PRIZMA de administración abre producción | Define `AUTO_PRIZMA_URL_PRIZMA=https://admin.prizma.solutions` antes de iniciar Uvicorn y confirma que el aviso de ambiente de pruebas aparezca en la app. |
