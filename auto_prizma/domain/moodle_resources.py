"""Reglas de dominio para preparar recursos dirigidos a cursos Moodle."""

import os
import re
import unicodedata


def normalize_key(value):
    texto = str(value or "")
    prefijos = (
        r"^\s*(?:h5p|pdf|infograf[ií]a|recurso\s+h5p|video\s+interactivo|texto|documento|presentaci[oó]n)\s*[-–—:]\s*",
        r"^\s*id\d+\s*[-–—]\s*tema(?:[_\s-]*tema)?[_\s-]*\d+\s*[-–—:_]?\s*",
        r"^\s*u\s*unidad\s*\d+\s*[-–—]\s*t+\s*tema\s*\d+\s*[-–—:_]?\s*",
        r"^\s*(?:u\d+\s*-?\s*t\d+\s*[-–—:]?\s*|ut\d+\s*[-–—:]?\s*|u\s*-\s*t\s*[-–—:]?\s*)",
    )
    for prefijo in prefijos:
        texto = re.sub(prefijo, "", texto, flags=re.IGNORECASE)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


RESOURCE_KINDS = (
    ("h5p", "Recurso H5P"),
    ("infografia", "Infografía"),
    ("video-avatar", "Video interactivo (avatar)"),
    ("pdf", "PDF"),
    ("reto", "Reto evaluativo"),
    ("otro", "Otros (no compatibles)"),
)


def resource_kind(row):
    """Tipo de recurso para agrupar y seleccionar en la vista previa (H5P, infografía, video, PDF, reto)."""
    categoria = str(row.get("category") or "").strip().upper()
    tipo = normalize_key(row.get("resourceType"))
    if categoria == "CHALLENGE" and tipo == "reto evaluativo":
        return "reto"
    if categoria in {"OVI", "OVA"}:
        if tipo == "recurso h5p":
            return "h5p"
        if tipo == "infografia" and categoria == "OVI":
            return "infografia"
        if tipo.startswith("video interactivo") and categoria == "OVA":
            return "video-avatar"
        if tipo == "pdf" and categoria == "OVI":
            return "pdf"
    return "otro"


BLOCK_LABELS = {
    "digital": "Recurso educativo digital",
    "audiovisual": "Recurso educativo audiovisual",
    "challenge": "Reto Evaluativo",
}
BLOCK_ORDER = ("digital", "audiovisual", "challenge")


def _blocks_for_row(row):
    """Bloques (etiquetas) del curso que necesita una fila de la matriz; None si no se sabe."""
    destination = destination_for(row)
    if destination:
        return {destination["block"]}
    if "video" in normalize_key(row.get("resourceType")):
        # Videos a cámara, intro o cierre: no se publican solos; por precaución se conserva el bloque audiovisual.
        return {"audiovisual"}
    return None


def label_cleanup_plan(rows, incomplete_rows=()):
    """Etiquetas que cada semana no usa según la matriz (candidatas a borrarse en Moodle).

    Una semana con filas que no se pueden clasificar (incompletas o de tipo desconocido) no se toca.
    """
    weeks = {}
    for row in rows:
        week = str(row.get("week") or "").strip()
        if not week:
            continue
        info = weeks.setdefault(week, {"week": week, "used": set(), "uncertain": False, "sourceRow": row.get("sourceRow") or 0})
        blocks = _blocks_for_row(row)
        if blocks is None:
            info["uncertain"] = True
        else:
            info["used"] |= blocks
    for row in incomplete_rows:
        week = str(row.get("week") or "").strip()
        if week in weeks:
            weeks[week]["uncertain"] = True
    plan = []
    for info in sorted(weeks.values(), key=publish_order):
        delete = [] if info["uncertain"] else [block for block in BLOCK_ORDER if block not in info["used"]]
        plan.append({
            "week": info["week"],
            "used": [block for block in BLOCK_ORDER if block in info["used"]],
            "delete": delete,
            "uncertain": info["uncertain"],
        })
    return plan


def publish_order(entry):
    """Orden de publicación: semana 1, 2, 3... y dentro de cada semana el orden de la matriz."""
    numero = re.search(r"\d+", str(entry.get("week") or ""))
    semana = int(numero.group()) if numero else float("inf")
    return (semana, entry.get("sourceRow") or 0)


def destination_for(row):
    categoria = str(row.get("category") or "").strip().upper()
    tipo = str(row.get("resourceType") or "").strip().lower()

    if categoria == "OVI" and tipo == "pdf":
        return {"block": "digital", "label": "Recurso educativo digital", "module": "file", "extension": ".pdf"}
    if categoria == "OVI" and tipo in {"infografía", "infografia", "recurso h5p"}:
        return {"block": "digital", "label": "Recurso educativo digital", "module": "h5p", "extension": ".h5p"}
    if categoria == "OVA" and tipo.startswith("video interactivo"):
        return {"block": "audiovisual", "label": "Recurso educativo audiovisual", "module": "h5p", "extension": ".h5p"}
    if categoria == "OVA" and tipo == "recurso h5p":
        return {"block": "digital", "label": "Recurso educativo digital", "module": "h5p", "extension": ".h5p"}
    if categoria == "CHALLENGE" and tipo == "reto evaluativo":
        return {"block": "challenge", "label": "Reto Evaluativo", "module": "file", "extension": ".pdf"}
    return None


def resolve_resource(row, indexed_files):
    destino = destination_for(row)
    if not destino:
        return {"status": "unsupported", "candidates": []}

    title_key = normalize_key(row.get("title"))
    link_parts = str(row.get("linkLabel") or "").split(" - ")
    link_key = normalize_key(link_parts[-1])

    def matches_prefix(expected, filename):
        if expected == filename:
            return True
        return min(len(expected), len(filename)) >= 18 and (
            expected.startswith(filename) or filename.startswith(expected)
        )

    exact = [item for item in indexed_files if item["key"] in {title_key, link_key}]
    title_matches = [item for item in indexed_files if matches_prefix(title_key, item["key"])]
    link_matches = [item for item in indexed_files if matches_prefix(link_key, item["key"])]
    candidatos = exact or title_matches or link_matches
    compatibles = [item for item in candidatos if item["extension"] == destino["extension"]]

    if len(compatibles) == 1:
        return {"status": "matched", "path": compatibles[0]["path"], "candidates": [compatibles[0]["path"]]}
    if len(compatibles) > 1:
        return {"status": "ambiguous", "candidates": [item["path"] for item in compatibles]}
    if candidatos:
        return {"status": "extension-mismatch", "candidates": [item["path"] for item in candidatos]}
    return {"status": "missing", "candidates": []}


def index_resource_files(root):
    indexed = []
    for carpeta, _directorios, nombres in os.walk(root):
        for nombre in nombres:
            extension = os.path.splitext(nombre)[1].lower()
            if extension not in {".pdf", ".h5p"}:
                continue
            ruta = os.path.join(carpeta, nombre)
            indexed.append({
                "path": ruta,
                "extension": extension,
                "key": normalize_key(os.path.splitext(nombre)[0]),
            })
    return indexed
