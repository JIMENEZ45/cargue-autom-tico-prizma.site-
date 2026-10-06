"""Relacion de recursos de Drive con el ZIP, avisos y prevalidacion rapida.
"""

from auto_prizma.automation.prizma import engine as motor_prizma_modulo
from auto_prizma.domain.file_names import exact_name_key, file_base_name
from auto_prizma.domain.drive_resource_policy import (
    choose_drive_item,
    match_drive_resource_to_zip,
    detect_duplicate_assignments,
)
import zipfile
import os
import re
import time

from auto_prizma.integrations.google.drive import (
    _CACHE_ARCHIVOS_DRIVE,
    _CACHE_ARCHIVOS_DRIVE_LOCK,
    _CACHE_REFERENCIAS_DRIVE,
    _CACHE_REFERENCIAS_DRIVE_LOCK,
    _DRIVE_THREAD_LOCAL,
    _cache_drive_obtener,
    _clave_actividad_drive,
    _clave_cache_drive,
    _clave_hoja,
    _extraer_referencia_drive,
    _leer_enlaces_columna_g_google_sheet,
    _precargar_referencias_drive_batch,
)


_MIME_H5P_DRIVE = {
    "application/x-zip",
    "application/zip",
    "application/x-h5p",
    "application/vnd.h5p",
}


def _extension_recurso_drive(item, actividad):
    """Determina el tipo cargable de un item Drive sin descargarlo.

    Google Drive puede devolver un H5P como ``application/x-zip`` y, en
    algunos casos, el nombre visible llega sin ``.h5p``. La matriz sigue
    siendo la autoridad para el tipo esperado; el MIME solo completa la
    extension cuando Drive no la conserva en el nombre.
    """
    nombre = str((item or {}).get("nombre") or (item or {}).get("name") or "").strip()
    mime_type = str((item or {}).get("mimeType") or "").strip().lower()
    tipo = str((actividad or {}).get("tipo_archivo") or "").strip().upper()
    extension = os.path.splitext(nombre)[1].lower()

    if extension in (".h5p", ".pdf"):
        return extension

    if tipo == "H5P" and mime_type in _MIME_H5P_DRIVE:
        return ".h5p"

    if tipo == "PDF" and mime_type == "application/pdf":
        return ".pdf"

    return ""


def _indice_zip_nombre_tamano(ruta_zip):
    """Indexa el ZIP por nombre exacto (Unicode NFC)."""
    indice = {
        "exacto": {},
        "total": 0,
    }

    with zipfile.ZipFile(ruta_zip, "r") as archivo_zip:
        for info in archivo_zip.infolist():
            if info.is_dir():
                continue

            nombre = file_base_name(info.filename)
            extension = os.path.splitext(nombre)[1].lower()

            if extension not in (".h5p", ".pdf"):
                continue

            entrada = {
                "nombre": nombre,
                "tamano": int(info.file_size),
                "miembro": info.filename,
            }

            indice["exacto"].setdefault(
                exact_name_key(nombre),
                [],
            ).append(entrada)

            indice["total"] += 1

    return indice


ETIQUETAS_AVISO = {
    "NO_DRIVE_FILE": "Sin archivo en Drive",
    "NO_DRIVE_LINK": "Sin enlace Drive",
    "DRIVE_UNREADABLE": "Carpeta Drive no legible",
    "MULTIPLE_DRIVE_FILES": "Varios archivos en Drive",
    "SIZE_MISMATCH": "Tamano distinto",
    "NAME_MISMATCH_SIZE_MATCH": "Nombre distinto",
    "NAME_MISMATCH_ACTIVITY_FALLBACK": "Nombre distinto",
    "IDENTICAL_ZIP_DUPLICATE": "Copia repetida en el ZIP",
    "IDENTICAL_DRIVE_DUPLICATE": "Copia repetida en Drive",
    "CROSS_ACTIVITY_DUPLICATE": "Recurso en varias filas",
    "SIN_EQUIVALENTE_ZIP": "Sin equivalente en el ZIP",
}

# Orden de gravedad: lo que mas conviene revisar va primero.
PRIORIDAD_AVISO = {
    "Sin archivo en Drive": 0,
    "Carpeta Drive no legible": 1,
    "Varios archivos en Drive": 2,
    "Sin enlace Drive": 3,
    "Sin equivalente en el ZIP": 4,
    "Tamano distinto": 5,
    "Recurso en varias filas": 6,
    "Copia repetida en el ZIP": 7,
    "Copia repetida en Drive": 8,
    "Nombre distinto": 9,
}


def _numeros_legibles(mensaje):
    """Pone separador de miles a los tamanos que vienen en crudo."""
    return re.sub(
        r"(\d{4,})(?=\s*bytes)",
        lambda m: f"{int(m.group(1)):,}".replace(",", "."),
        str(mensaje or ""),
    )


def _aviso(actividad, codigo, mensaje):
    """Advertencia como fila de tabla, no como texto corrido."""
    actividad = actividad or {}

    return {
        "hoja": str(actividad.get("hoja") or ""),
        "fila": actividad.get("fila_excel") or "",
        "actividad": str(actividad.get("nombre") or ""),
        "tipo": ETIQUETAS_AVISO.get(
            str(codigo or "").strip().upper(),
            "Diferencia",
        ),
        "detalle": _numeros_legibles(mensaje),
    }


def _bytes_legibles(valor):
    """Formatea el tamano con separador de miles, o '?' si no se conoce."""
    try:
        return f"{int(valor):,}".replace(",", ".") + " bytes"
    except (TypeError, ValueError):
        return "tamano desconocido"


def _registrar_diagnostico_drive(
    diagnostico,
    descripcion,
    url_drive,
    drive_id,
    motivo,
    resultado_drive=None,
    fallas=None,
):
    """Guarda hasta 10 filas fallidas con TODO lo necesario para clasificarlas."""
    if len(diagnostico) >= 10:
        return

    resultado_drive = resultado_drive or {}
    detalles = resultado_drive.get("detalles") or []

    diagnostico.append({
        "fila": descripcion,
        "valor_en_G": url_drive,
        "drive_id": drive_id,
        "motivo": motivo,
        "subcarpetas_vistas": resultado_drive.get("subcarpetas", 0),
        "archivos_en_drive": [
            str(item.get("nombre") or "")
            + " | " + str(item.get("mimeType") or "")
            + " | " + str(item.get("tamano"))
            for item in detalles[:8]
        ],
        "ignorados_en_drive": [
            str(item.get("nombre") or "") + " | " + str(item.get("motivo") or "")
            for item in (resultado_drive.get("ignorados") or [])[:5]
        ],
        "resultado_vs_zip": [
            str(item.get("nombre") or "") + " -> " + str(estado)
            for item, estado, _ in (fallas or [])[:8]
        ],
    })


def _prevalidar_recursos_drive_zip_ultrarapido(
    url_google_sheet,
    ruta_excel,
    ruta_zip,
    procesar_ovi=True,
    procesar_ova=True,
    procesar_retos=True,
    hoja_objetivo=None,
):
    """Analiza la hoja actual sin detenerse por problemas de recursos.

    La matriz define la actividad y su tipo. La columna G define la carpeta
    Drive de ESA fila. Para cada actividad se muestra el archivo real de Drive
    (nombre + tamano). Si no existe un H5P/PDF compatible, se registra
    ``NO HAY ARCHIVO EN LA CARPETA`` y el analisis continua.

    Drive y ZIP solo quedan habilitados para cargue automatico cuando el nombre
    canonico del recurso coincide. El tamano se conserva solo como informacion
    visual y NO participa en la comparacion. Cualquier diferencia de nombre se
    presenta como advertencia al final, sin cortar el analisis completo.
    """

    _DRIVE_THREAD_LOCAL.hoja_objetivo = hoja_objetivo

    actividades = motor_prizma_modulo.leer_actividades_excel(
        ruta_excel,
        procesar_ovi,
        procesar_ova,
        procesar_retos,
    )

    if not actividades:
        return {
            "ok": False,
            "total_actividades": 0,
            "total_enlaces_drive": 0,
            "validadas_drive": 0,
            "coincidencias_zip": 0,
            "errores": ["No se encontraron actividades compatibles en la matriz."],
            "advertencias": [],
            "recursos": [],
            "_mapa_resueltos": {},
        }

    indice_zip = _indice_zip_nombre_tamano(ruta_zip)

    _t0 = time.perf_counter()

    enlaces_drive = _leer_enlaces_columna_g_google_sheet(
        url_google_sheet,
        hoja_objetivo,
    )

    actividades_con_drive = []
    for actividad in actividades:
        clave_fila = (
            _clave_hoja(actividad.get("hoja")),
            int(actividad.get("fila_excel") or 0),
        )
        url_drive = str(enlaces_drive.get(clave_fila) or "").strip()
        actividad["_url_drive_sheet"] = url_drive
        if url_drive:
            actividades_con_drive.append(actividad)

    _t1 = time.perf_counter()

    if actividades_con_drive:
        _precargar_referencias_drive_batch(actividades_con_drive)

    _t2 = time.perf_counter()

    advertencias = []
    recursos = []
    mapa_resueltos = {}
    diagnostico = []
    archivos_drive_encontrados = 0
    coincidencias_zip = 0

    entradas_zip = []
    for grupo in indice_zip.get("exacto", {}).values():
        entradas_zip.extend(grupo)

    def registrar_visual(
        actividad,
        archivo_drive,
        tamano_drive=None,
        archivo_zip="",
        tamano_zip=None,
        coincide_zip=False,
        estado="",
    ):
        recursos.append({
            "hoja": actividad.get("hoja", ""),
            "fila": actividad.get("fila_excel", 0),
            "actividad": actividad.get("nombre", ""),
            "archivo": str(archivo_drive or ""),
            "archivo_drive": str(archivo_drive or ""),
            "tamano_drive": tamano_drive,
            "archivo_zip": str(archivo_zip or ""),
            "tamano_zip": tamano_zip,
            "tamano": tamano_zip,
            "coincide_zip": bool(coincide_zip),
            "estado": str(estado or ""),
        })

    def bloquear_cargue(actividad, error_cargue, nombre_drive="", tamano_drive=None):
        mapa_resueltos[_clave_actividad_drive(actividad)] = {
            "cargable": False,
            "error_cargue": str(error_cargue or "ERROR_DRIVE_ZIP_NO_COINCIDEN"),
            "nombre_drive": str(nombre_drive or ""),
            "tamano_drive": tamano_drive,
        }

    for actividad in actividades:
        descripcion = (
            f'Hoja {actividad.get("hoja", "")} · '
            f'fila {actividad.get("fila_excel", "")} · '
            f'{actividad.get("nombre", "")}'
        )
        url_drive = str(actividad.get("_url_drive_sheet") or "").strip()
        extension_esperada = {
            "H5P": ".h5p",
            "PDF": ".pdf",
        }.get(str(actividad.get("tipo_archivo") or "").strip().upper(), "")

        if not url_drive:
            registrar_visual(
                actividad,
                "NO HAY ENLACE DRIVE",
                estado="SIN_ENLACE_DRIVE",
            )
            advertencias.append(_aviso(
                actividad,
                "NO_DRIVE_LINK",
                "La fila no tiene un enlace Google Drive en la columna G. "
                "El analisis continuo, pero esta actividad no se cargara automaticamente.",
            ))
            bloquear_cargue(actividad, "ERROR_SIN_ENLACE_DRIVE")
            continue

        _, drive_id = _extraer_referencia_drive(url_drive)
        if not drive_id:
            registrar_visual(
                actividad,
                "NO HAY ARCHIVO EN LA CARPETA",
                estado="ENLACE_DRIVE_INVALIDO",
            )
            advertencias.append(_aviso(
                actividad,
                "DRIVE_UNREADABLE",
                "El enlace de la columna G no pudo resolverse como recurso de Google Drive. "
                "El analisis continuo.",
            ))
            bloquear_cargue(actividad, "ERROR_ENLACE_DRIVE_INVALIDO")
            continue

        with _CACHE_REFERENCIAS_DRIVE_LOCK:
            referencia = dict(
                _CACHE_REFERENCIAS_DRIVE.get(_clave_cache_drive(drive_id))
                or {}
            )

        tipo_ref = str(referencia.get("tipo") or "")
        target_id = str(referencia.get("target_id") or drive_id)
        elegido = None
        resultado_drive = None

        if tipo_ref == "folder":
            resultado_drive = _cache_drive_obtener(target_id)

            if not resultado_drive or not resultado_drive.get("ok"):
                registrar_visual(
                    actividad,
                    "NO SE PUDO LEER LA CARPETA",
                    estado="CARPETA_NO_LEGIBLE",
                )
                advertencias.append(_aviso(
                    actividad,
                    "DRIVE_UNREADABLE",
                    "No fue posible leer la carpeta Drive de esta actividad. "
                    "El analisis continuo sin detener las demas filas.",
                ))
                bloquear_cargue(actividad, "ERROR_CARPETA_RECURSO_NO_ACCESIBLE")
                _registrar_diagnostico_drive(
                    diagnostico,
                    descripcion,
                    url_drive,
                    target_id,
                    "advertencia: carpeta no legible",
                    resultado_drive,
                )
                continue

            detalles = resultado_drive.get("detalles") or []
            candidatos_drive = []

            for item in detalles:
                extension = _extension_recurso_drive(item, actividad)
                if extension not in (".h5p", ".pdf"):
                    continue
                if extension_esperada and extension != extension_esperada:
                    continue
                candidatos_drive.append(item)

            if not candidatos_drive:
                registrar_visual(
                    actividad,
                    "NO HAY ARCHIVO EN LA CARPETA",
                    estado="SIN_ARCHIVO_DRIVE",
                )
                advertencias.append(_aviso(
                    actividad,
                    "NO_DRIVE_FILE",
                    "La carpeta de esta actividad no contiene ningun archivo "
                    + (extension_esperada.upper().replace(".", "") or "H5P/PDF")
                    + ". El analisis continuo normalmente.",
                ))
                bloquear_cargue(actividad, "ERROR_SIN_ARCHIVO_EN_CARPETA")
                _registrar_diagnostico_drive(
                    diagnostico,
                    descripcion,
                    url_drive,
                    target_id,
                    "advertencia: NO HAY ARCHIVO EN LA CARPETA",
                    resultado_drive,
                )
                continue

            eleccion_drive = choose_drive_item(
                candidatos_drive,
                expected_extension=extension_esperada,
            )

            if eleccion_drive.error or not eleccion_drive.item:
                nombres = ", ".join(
                    str(item.get("nombre") or "")
                    + " (" + _bytes_legibles(item.get("tamano")) + ")"
                    for item in candidatos_drive[:8]
                )
                registrar_visual(
                    actividad,
                    "VARIOS ARCHIVOS EN LA CARPETA",
                    estado="VARIOS_ARCHIVOS_DRIVE",
                )
                advertencias.append(_aviso(
                    actividad,
                    "MULTIPLE_DRIVE_FILES",
                    "La carpeta contiene varios recursos diferentes: " + nombres
                    + ". El analisis continuo, pero esta fila no queda habilitada para cargue.",
                ))
                bloquear_cargue(actividad, "ERROR_VARIOS_ARCHIVOS_EN_CARPETA")
                continue

            elegido = eleccion_drive.item
            for aviso in eleccion_drive.warnings:
                advertencias.append(_aviso(actividad, aviso.code, aviso.message))

        elif tipo_ref == "file":
            elegido = referencia.get("item")
            if not elegido:
                with _CACHE_ARCHIVOS_DRIVE_LOCK:
                    elegido = _CACHE_ARCHIVOS_DRIVE.get(
                        _clave_cache_drive(drive_id)
                    )

            if elegido:
                extension = _extension_recurso_drive(elegido, actividad)
                if (
                    extension not in (".h5p", ".pdf")
                    or (extension_esperada and extension != extension_esperada)
                ):
                    elegido = None

            if not elegido:
                registrar_visual(
                    actividad,
                    "NO HAY ARCHIVO EN LA CARPETA",
                    estado="SIN_ARCHIVO_DRIVE",
                )
                advertencias.append(_aviso(
                    actividad,
                    "NO_DRIVE_FILE",
                    "El enlace Drive de esta actividad no contiene un recurso H5P/PDF "
                    "del tipo esperado. El analisis continuo normalmente.",
                ))
                bloquear_cargue(actividad, "ERROR_SIN_ARCHIVO_EN_CARPETA")
                continue

        else:
            registrar_visual(
                actividad,
                "NO HAY ARCHIVO EN LA CARPETA",
                estado="SIN_ARCHIVO_DRIVE",
            )
            advertencias.append(_aviso(
                actividad,
                "NO_DRIVE_FILE",
                "No fue posible encontrar un recurso H5P/PDF utilizable en el enlace Drive. "
                "El analisis continuo normalmente.",
            ))
            bloquear_cargue(actividad, "ERROR_SIN_ARCHIVO_EN_CARPETA")
            continue

        nombre_drive = str(elegido.get("nombre") or "").strip()
        tamano_drive = elegido.get("tamano")
        try:
            tamano_drive = int(tamano_drive) if tamano_drive is not None else None
        except (TypeError, ValueError):
            tamano_drive = None

        archivos_drive_encontrados += 1

        resultado_match = match_drive_resource_to_zip(
            elegido,
            entradas_zip,
            expected_extension=extension_esperada,
        )

        for aviso in resultado_match.warnings:
            advertencias.append(_aviso(actividad, aviso.code, aviso.message))

        zip_elegido = resultado_match.entry
        archivo_zip = str((zip_elegido or {}).get("nombre") or "")
        tamano_zip = (zip_elegido or {}).get("tamano")
        try:
            tamano_zip = int(tamano_zip) if tamano_zip is not None else None
        except (TypeError, ValueError):
            tamano_zip = None

        verificado = bool(
            zip_elegido
            and getattr(resultado_match, "verified_same_file", False)
        )

        if not zip_elegido:
            advertencias.append(_aviso(
                actividad,
                "SIN_EQUIVALENTE_ZIP",
                "Drive contiene \"" + nombre_drive + "\" ("
                + _bytes_legibles(tamano_drive)
                + "), pero no existe el mismo archivo en el ZIP. "
                "El analisis continuo; esta fila no se cargara hasta corregir el ZIP.",
            ))
        elif not verificado and not resultado_match.warnings:
            advertencias.append(_aviso(
                actividad,
                "SIN_EQUIVALENTE_ZIP",
                "Drive y ZIP no pudieron confirmarse como el mismo archivo por nombre. "
                "El analisis continuo.",
            ))

        registrar_visual(
            actividad,
            nombre_drive or "NO HAY ARCHIVO EN LA CARPETA",
            tamano_drive=tamano_drive,
            archivo_zip=archivo_zip,
            tamano_zip=tamano_zip,
            coincide_zip=verificado,
            estado="OK" if verificado else "REVISAR_ZIP",
        )

        if verificado:
            coincidencias_zip += 1
            actividad["nombre_recurso_drive"] = nombre_drive
            mapa_resueltos[_clave_actividad_drive(actividad)] = {
                "cargable": True,
                "nombre": archivo_zip,
                "nombre_drive": nombre_drive,
                "tamano": tamano_zip,
                "tamano_zip": tamano_zip,
                "tamano_drive": tamano_drive,
                "miembro_zip": str(zip_elegido.get("miembro") or ""),
                "tipo_ref": tipo_ref,
                "drive_id": target_id,
            }
        else:
            bloquear_cargue(
                actividad,
                "ERROR_DRIVE_ZIP_NO_COINCIDEN",
                nombre_drive,
                tamano_drive,
            )

    for aviso in detect_duplicate_assignments(recursos):
        advertencias.append(_aviso(None, aviso.code, aviso.message))

    vistas = set()
    advertencias_unicas = []
    for item in advertencias:
        clave = (
            str(item.get("hoja") or ""),
            str(item.get("fila") or ""),
            str(item.get("tipo") or ""),
            str(item.get("detalle") or ""),
        )
        if clave in vistas:
            continue
        vistas.add(clave)
        advertencias_unicas.append(item)

    def _orden_aviso(item):
        try:
            fila = int(item.get("fila") or 0)
        except (TypeError, ValueError):
            fila = 0
        return (
            PRIORIDAD_AVISO.get(str(item.get("tipo") or ""), 9),
            str(item.get("hoja") or ""),
            fila,
        )

    advertencias = sorted(advertencias_unicas, key=_orden_aviso)

    if advertencias:
        conteo = {}
        for item in advertencias:
            tipo = str(item.get("tipo") or "")
            conteo[tipo] = conteo.get(tipo, 0) + 1

        print("")
        print("=" * 100)
        print(
            "ADVERTENCIAS DEL ANALISIS: " + str(len(advertencias))
            + "  (NO detienen el analisis)"
        )
        print("   " + " | ".join(
            tipo + ": " + str(cantidad)
            for tipo, cantidad in sorted(conteo.items())
        ))
        print("=" * 100)
        for item in advertencias:
            print(
                "Fila", item.get("fila") or "-", "|",
                item.get("actividad") or "-", "|",
                item.get("tipo") or "-", "|",
                item.get("detalle") or "",
            )
        print("=" * 100)
        print("")

    print(
        "ZIP indexado:",
        indice_zip["total"],
        "archivo(s) .h5p/.pdf",
    )
    print(
        "TIEMPOS:",
        f"columna G {_t1 - _t0:.1f}s |",
        f"lectura Drive {_t2 - _t1:.1f}s |",
        f"comparacion ZIP {time.perf_counter() - _t2:.1f}s |",
        f"total {time.perf_counter() - _t0:.1f}s",
    )
    print(
        "Drive SOLO ENLACES:",
        len(actividades_con_drive),
        "fila(s) con Drive en G |",
        archivos_drive_encontrados,
        "archivo(s) H5P/PDF encontrado(s) en Drive |",
        coincidencias_zip,
        "coincidencia(s) exacta(s) Drive=ZIP por nombre |",
        len(advertencias),
        "advertencia(s) finales",
    )

    return {
        # Los problemas de una fila NO bloquean la pantalla de analisis.
        # Solo la ausencia total de actividades se considera estructural.
        "ok": True,
        "total_actividades": len(actividades),
        "total_enlaces_drive": len(actividades_con_drive),
        "validadas_drive": archivos_drive_encontrados,
        "coincidencias_zip": coincidencias_zip,
        "errores": [],
        "advertencias": advertencias,
        "recursos": recursos,
        "_mapa_resueltos": mapa_resueltos,
    }
