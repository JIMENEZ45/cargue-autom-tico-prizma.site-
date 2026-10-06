from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import unicodedata
from typing import Any, Iterable


@dataclass(frozen=True)
class WarningItem:
    code: str
    message: str


@dataclass
class MatchResult:
    entry: dict[str, Any] | None = None
    warnings: list[WarningItem] = field(default_factory=list)
    error: str | None = None
    # True SOLO cuando Drive y ZIP representan el mismo recurso por
    # nombre canonico. El tamano NO participa en la identidad del recurso.
    # El analisis puede continuar con False, pero esa fila no queda habilitada
    # para cargue automatico.
    verified_same_file: bool = False


@dataclass
class DriveChoiceResult:
    item: dict[str, Any] | None = None
    warnings: list[WarningItem] = field(default_factory=list)
    error: str | None = None


def _base_name(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    return text.rsplit("/", 1)[-1].strip()


def _normalized_name(value: Any) -> str:
    text = unicodedata.normalize("NFC", _base_name(value))
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _normalized_resource_name(value: Any, expected_extension: str = "") -> str:
    """Nombre canonico para comparar Drive contra ZIP.

    Drive puede exponer un H5P como ``application/x-zip`` sin conservar
    ``.h5p`` en el nombre visible. Si la matriz ya declara el tipo esperado,
    completar esa extension NO cambia la identidad del recurso.
    """
    name = _base_name(value)
    expected = str(expected_extension or "").lower().strip()
    current = os.path.splitext(name)[1].lower()

    if expected in {".h5p", ".pdf"}:
        if not current:
            name += expected
        elif current == ".zip" and expected == ".h5p":
            name = os.path.splitext(name)[0] + expected

    return _normalized_name(name)


def _extension(value: Any) -> str:
    return os.path.splitext(_base_name(value))[1].lower()


def _size(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _same_entry(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        _normalized_name(a.get("nombre")) == _normalized_name(b.get("nombre"))
        and _size(a.get("tamano")) == _size(b.get("tamano"))
        and str(a.get("miembro") or "") == str(b.get("miembro") or "")
    )


def _filter_expected_extension(
    entries: Iterable[dict[str, Any]],
    expected_extension: str,
) -> list[dict[str, Any]]:
    expected = str(expected_extension or "").lower().strip()
    items = list(entries)
    if expected not in {".h5p", ".pdf"}:
        return items
    filtered = [item for item in items if _extension(item.get("nombre")) == expected]
    return filtered or items


def choose_drive_item(
    items: Iterable[dict[str, Any]],
    expected_extension: str = "",
) -> DriveChoiceResult:
    candidates = _filter_expected_extension(items, expected_extension)
    if not candidates:
        return DriveChoiceResult(error="NO_DRIVE_RESOURCE")

    candidates = sorted(
        candidates,
        key=lambda item: (
            _normalized_name(item.get("nombre")),
            _size(item.get("tamano")) if _size(item.get("tamano")) is not None else -1,
        ),
    )

    if len(candidates) == 1:
        return DriveChoiceResult(item=candidates[0])

    signatures = {
        (_normalized_name(item.get("nombre")), _size(item.get("tamano")))
        for item in candidates
    }
    if len(signatures) == 1:
        selected = candidates[0]
        return DriveChoiceResult(
            item=selected,
            warnings=[
                WarningItem(
                    "IDENTICAL_DRIVE_DUPLICATE",
                    "La carpeta de Drive contiene recursos repetidos con el mismo nombre y tamaño; se continuará con uno de ellos y se deja la alerta para la revisión final.",
                )
            ],
        )

    return DriveChoiceResult(error="MULTIPLE_DIFFERENT_DRIVE_RESOURCES")


def match_drive_resource_to_zip(
    drive_item: dict[str, Any],
    zip_entries: Iterable[dict[str, Any]],
    expected_extension: str = "",
    fallback_entry: dict[str, Any] | None = None,
) -> MatchResult:
    """Relaciona Drive con ZIP usando SOLO el nombre canonico del recurso.

    El tamano se conserva como metadato para mostrarlo en la interfaz, pero
    nunca decide si dos recursos son el mismo. ``fallback_entry`` se mantiene
    en la firma por compatibilidad con versiones anteriores, pero no puede
    relacionar archivos con nombres distintos.
    """
    del fallback_entry  # compatibilidad: intencionalmente no se usa

    entries = _filter_expected_extension(zip_entries, expected_extension)
    drive_name = _base_name(drive_item.get("nombre"))
    drive_name_key = _normalized_resource_name(drive_name, expected_extension)

    same_name = [
        item
        for item in entries
        if _normalized_resource_name(item.get("nombre"), expected_extension)
        == drive_name_key
    ]

    if len(same_name) == 1:
        return MatchResult(
            entry=same_name[0],
            verified_same_file=True,
        )

    if len(same_name) > 1:
        return MatchResult(error="AMBIGUOUS_SAME_NAME")

    return MatchResult(error="NO_ZIP_MATCH")

def detect_duplicate_assignments(
    resources: Iterable[dict[str, Any]],
) -> list[WarningItem]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for resource in resources:
        name = _normalized_name(resource.get("archivo_drive"))
        size = _size(resource.get("tamano_drive"))
        if not name or size is None:
            continue
        groups.setdefault((name, size), []).append(resource)

    warnings: list[WarningItem] = []
    for (_, size), items in groups.items():
        if len(items) < 2:
            continue
        ordered = sorted(items, key=lambda item: (str(item.get("hoja") or ""), int(item.get("fila") or 0)))
        locations = ", ".join(
            f'{item.get("hoja", "")} fila {int(item.get("fila") or 0)}'
            for item in ordered
        )
        name = _base_name(ordered[0].get("archivo_drive"))
        warnings.append(
            WarningItem(
                "CROSS_ACTIVITY_DUPLICATE",
                f'El mismo recurso de Drive "{name}" ({size} bytes) aparece relacionado con más de una actividad: {locations}. El análisis continuó normalmente.',
            )
        )
    return warnings
