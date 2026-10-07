"""Campo "Html" de una actividad y archivo previo en "Recurso" (modo de carga HTML).

Piezas de bajo nivel, sin dependencias del motor, para el modo HTML:
- leer el codigo de un archivo .html;
- escribirlo en el editor del campo "Html" y verificar que quedo identico;
- detectar y quitar el archivo ya cargado en el campo "Recurso", sea cual
  sea (PRIZMA no permite un archivo en "Recurso" y Html a la vez).

Los selectores salen de la estructura real del formulario (ver SELECTORES)
y todas las funciones son defensivas: ante cualquier duda devuelven un
error para que el motor cancele la edicion SIN guardar.
"""

import os


# ============================================================
# SELECTORES (estructura real del formulario de PRIZMA, 2026-10-07)
# ============================================================
#
# Campo de archivo de la actividad:
#   <p class="form-label">Recurso (H5P)</p>      (OVA; en OVI el titulo es "Recurso")
#   <div class="btnFile">
#     <div class="fileItem">                      (solo si hay un archivo cargado)
#       <div class="box-info-file"><p>Nombre.h5p</p><p>2.87 MB</p></div>
#                                                 (a veces el nombre es solo "Archivo")
#       <p class="type">.octet-stream</p>         (tipo MIME: NO sirve para saber si es H5P)
#       <button>descargar</button><button>eliminar (papelera)</button>
#
# Al pulsar la papelera PRIZMA pide confirmacion: "¿Estás seguro?" /
# "¿Deseas eliminar este archivo?" con los botones Cancelar / Eliminar.

_CLASE = "contains(concat(' ', normalize-space(@class), ' '), ' {} ')"

# "Recurso" o "Recurso (H5P)"; excluye otros textos como "Recursos:".
_TITULO_CAMPO_RECURSO = (
    "p[normalize-space(text())='Recurso' or starts-with(normalize-space(text()), 'Recurso (')]"
)

_XPATH_TARJETA_RECURSO = (
    "//" + _TITULO_CAMPO_RECURSO
    + "/following-sibling::div[" + _CLASE.format("btnFile") + "][1]"
    + "//div[" + _CLASE.format("fileItem") + "]"
)

XPATH_TARJETA_ARCHIVO_RECURSO = "xpath=" + _XPATH_TARJETA_RECURSO
_XPATH_NOMBRE_ARCHIVO_RECURSO = (
    "xpath=" + _XPATH_TARJETA_RECURSO + "//div[" + _CLASE.format("box-info-file") + "]/p[1]"
)
# Botones de la tarjeta en orden: [descargar, eliminar]. La papelera es el ultimo.
_XPATH_BOTONES_TARJETA_RECURSO = "xpath=" + _XPATH_TARJETA_RECURSO + "//button"

# Para diagnostico: el formulario completo de la actividad.
XPATH_SECCION_RECURSO = "xpath=//" + _TITULO_CAMPO_RECURSO + "/ancestor::form[1]"

# Confirmacion de PRIZMA al eliminar el archivo.
TEXTO_CONFIRMAR_ELIMINACION = "Deseas eliminar este archivo"

# Nombre que se informa si hay un archivo en "Recurso" pero no se pudo leer.
NOMBRE_ARCHIVO_DESCONOCIDO = "(sin nombre)"


# ============================================================
# ARCHIVO .HTML
# ============================================================

def leer_archivo_html(ruta):
    """Lee el codigo completo de un archivo .html.

    Args:
        ruta: ruta del archivo extraido del ZIP.

    Returns:
        (contenido, None) si se pudo leer, o (None, codigo_error):
        ERROR_LEYENDO_HTML, ERROR_HTML_NO_ES_UTF8 o ERROR_HTML_VACIO.
    """
    try:
        with open(ruta, "rb") as archivo:
            datos = archivo.read()
    except OSError:
        return None, "ERROR_LEYENDO_HTML"

    try:
        # utf-8-sig quita el BOM si el archivo lo trae.
        contenido = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "ERROR_HTML_NO_ES_UTF8"

    if not contenido.strip():
        return None, "ERROR_HTML_VACIO"

    return contenido, None


def normalizar_saltos(texto):
    """Unifica los saltos de linea (CRLF y CR pasan a LF), como hace un textarea."""
    return str(texto or "").replace("\r\n", "\n").replace("\r", "\n")


# ============================================================
# EDITOR DEL CAMPO HTML
# ============================================================

def es_campo_de_texto(editor):
    """True si el editor es un textarea o input (no un editor de codigo/enriquecido)."""
    try:
        etiqueta = editor.evaluate("e => e.tagName.toLowerCase()")
    except Exception:
        return False
    return etiqueta in ("textarea", "input")


def describir_editor(editor):
    """Etiqueta y clases del editor, para los mensajes de error ("<div class=...>")."""
    try:
        return editor.evaluate(
            "e => '<' + e.tagName.toLowerCase() + (e.className ? ' class=\"' + e.className + '\"' : '') + '>'"
        )
    except Exception:
        return "<desconocido>"


def escribir_html_en_editor(editor, contenido):
    """Escribe el codigo HTML en el editor y verifica que quedo identico.

    Solo se admiten textarea/input. En editores de codigo o enriquecidos,
    escribir caracter a caracter puede reindentar, autocerrar etiquetas o
    escapar el HTML, asi que se rechazan sin tocar nada.

    Args:
        editor: locator del campo Html.
        contenido: codigo completo del archivo .html.

    Returns:
        (True, "") si el campo quedo igual al archivo (salvo saltos de linea),
        o (False, motivo) en cualquier otro caso.
    """
    if not es_campo_de_texto(editor):
        return False, "editor no soportado " + describir_editor(editor)

    try:
        editor.fill(contenido)
        actual = editor.input_value(timeout=2000)
    except Exception as error:
        return False, "no se pudo escribir en el campo Html (" + type(error).__name__ + ")"

    esperado = normalizar_saltos(contenido)
    actual = normalizar_saltos(actual)

    if actual != esperado:
        return False, (
            "el campo Html quedo con " + str(len(actual))
            + " caracteres y el archivo tiene " + str(len(esperado))
        )

    return True, ""


# ============================================================
# ARCHIVO PREVIO EN EL CAMPO "RECURSO"
# ============================================================

def archivo_en_recurso(pagina):
    """Nombre del archivo cargado en el campo "Recurso", o "" si no hay ninguno.

    Returns:
        El nombre que muestra la tarjeta (p. ej. "Presupuesto.h5p" o el
        generico "Archivo"), NOMBRE_ARCHIVO_DESCONOCIDO si hay tarjeta pero
        no se pudo leer el nombre, o "".
    """
    try:
        tarjetas = pagina.locator(XPATH_TARJETA_ARCHIVO_RECURSO)
        if tarjetas.count() == 0 or not tarjetas.first.is_visible():
            return ""
        nombres = pagina.locator(_XPATH_NOMBRE_ARCHIVO_RECURSO)
        nombre = nombres.first.inner_text(timeout=1000) if nombres.count() > 0 else ""
        return nombre.strip() or NOMBRE_ARCHIVO_DESCONOCIDO
    except Exception:
        return ""


def _confirmar_eliminacion(pagina, timeout_ms=5000, intervalo_ms=200):
    """Pulsa "Eliminar" en la confirmacion "¿Deseas eliminar este archivo?".

    Returns:
        True si aparecio la confirmacion y se pulso Eliminar; False si no
        aparecio (por ejemplo, porque el boton pulsado no era la papelera).
    """
    transcurrido = 0
    while True:
        try:
            texto = pagina.get_by_text(TEXTO_CONFIRMAR_ELIMINACION, exact=False)
            if texto.count() > 0 and texto.first.is_visible():
                botones = pagina.get_by_role("button", name="Eliminar", exact=True)
                for indice in range(botones.count()):
                    if botones.nth(indice).is_visible():
                        botones.nth(indice).click(timeout=5000)
                        return True
        except Exception:
            pass

        if transcurrido >= timeout_ms:
            return False
        pagina.wait_for_timeout(intervalo_ms)
        transcurrido += intervalo_ms


def quitar_archivo_de_recurso(pagina, timeout_ms=6000, intervalo_ms=200):
    """Elimina el archivo del campo "Recurso" (papelera + confirmar) y lo verifica.

    Sirve para cualquier archivo, no solo .h5p (decision del usuario,
    2026-10-07): PRIZMA a veces solo muestra un nombre generico ("Archivo").

    Returns:
        (True, "") si la tarjeta del archivo desaparecio, o (False, motivo).
    """
    try:
        botones = pagina.locator(_XPATH_BOTONES_TARJETA_RECURSO)
        cantidad = botones.count()
        if cantidad == 0:
            return False, "no se encontro el boton para eliminar el archivo de Recurso"
        # La papelera es el ultimo boton de la tarjeta (el primero es descargar).
        botones.nth(cantidad - 1).click(timeout=5000)
    except Exception as error:
        return False, "no se pudo pulsar la papelera de Recurso (" + type(error).__name__ + ")"

    if not _confirmar_eliminacion(pagina):
        return False, "PRIZMA no mostro la confirmacion para eliminar el archivo"

    transcurrido = 0
    while True:
        if not archivo_en_recurso(pagina):
            return True, ""
        if transcurrido >= timeout_ms:
            return False, "el archivo sigue en Recurso despues de confirmar la eliminacion"
        pagina.wait_for_timeout(intervalo_ms)
        transcurrido += intervalo_ms


# ============================================================
# DIAGNOSTICO
# ============================================================

def guardar_estructura(pagina, xpath, carpeta_temp, nombre_archivo):
    """Guarda el HTML de una seccion del formulario para ajustar los selectores.

    Solo se usa cuando algo falla. Queda en temp/ (no se versiona).

    Returns:
        Ruta relativa del archivo guardado, o "" si no se pudo.
    """
    try:
        if not carpeta_temp:
            return ""
        seccion = pagina.locator(xpath)
        if seccion.count() == 0:
            return ""
        contenido = seccion.first.evaluate("e => e.outerHTML") or ""
        os.makedirs(carpeta_temp, exist_ok=True)
        ruta = os.path.join(carpeta_temp, nombre_archivo)
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(contenido[:200000])
        try:
            return os.path.relpath(ruta)
        except ValueError:
            return ruta
    except Exception:
        return ""
