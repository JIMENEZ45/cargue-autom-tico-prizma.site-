"""Pruebas de las reglas puras de emparejamiento Drive <-> ZIP.

Fijan el comportamiento actual de auto_prizma/domain/drive_resource_policy.py:
la identidad del recurso es SOLO el nombre canonico (el tamano es informativo)
y las ambiguedades nunca se resuelven adivinando.
"""

from auto_prizma.domain.drive_resource_policy import (
    choose_drive_item,
    detect_duplicate_assignments,
    match_drive_resource_to_zip,
)


# ============================================================
# ELEGIR EL ARCHIVO DE LA CARPETA DE DRIVE
# ============================================================

def test_choose_drive_item_without_items_returns_error():
    resultado = choose_drive_item([])

    assert resultado.item is None
    assert resultado.error == "NO_DRIVE_RESOURCE"


def test_choose_drive_item_filters_by_expected_extension():
    resultado = choose_drive_item(
        [{"nombre": "a.pdf", "tamano": 1}, {"nombre": "b.h5p", "tamano": 2}],
        ".h5p",
    )

    assert resultado.item == {"nombre": "b.h5p", "tamano": 2}
    assert resultado.error is None


def test_choose_drive_item_identical_duplicates_continue_with_warning():
    resultado = choose_drive_item(
        [{"nombre": "A.pdf", "tamano": 5}, {"nombre": "a.pdf", "tamano": 5}],
        ".pdf",
    )

    assert resultado.item == {"nombre": "A.pdf", "tamano": 5}
    assert [w.code for w in resultado.warnings] == ["IDENTICAL_DRIVE_DUPLICATE"]


def test_choose_drive_item_different_files_are_ambiguous():
    resultado = choose_drive_item(
        [{"nombre": "a.pdf", "tamano": 5}, {"nombre": "b.pdf", "tamano": 5}],
        ".pdf",
    )

    assert resultado.item is None
    assert resultado.error == "MULTIPLE_DIFFERENT_DRIVE_RESOURCES"


def test_choose_drive_item_falls_back_to_all_items_if_no_extension_matches():
    # Comportamiento actual: si ninguno tiene la extension esperada, no filtra.
    resultado = choose_drive_item([{"nombre": "a.docx"}], ".pdf")

    assert resultado.item == {"nombre": "a.docx"}
    assert resultado.error is None


# ============================================================
# RELACIONAR DRIVE CON EL ZIP
# ============================================================

ENTRADAS_ZIP = [
    {"nombre": "Recurso – 1.h5p", "tamano": 10, "miembro": "x/Recurso – 1.h5p"},
    {"nombre": "otro.pdf", "tamano": 3, "miembro": "otro.pdf"},
]


def test_match_uses_canonical_name_ignoring_case_dashes_spaces_and_missing_extension():
    resultado = match_drive_resource_to_zip({"nombre": "recurso - 1"}, ENTRADAS_ZIP, ".h5p")

    assert resultado.entry == ENTRADAS_ZIP[0]
    assert resultado.verified_same_file is True
    assert resultado.error is None


def test_match_treats_drive_zip_extension_as_h5p_and_ignores_size():
    resultado = match_drive_resource_to_zip(
        {"nombre": "Recurso   -   1.zip", "tamano": 999},
        ENTRADAS_ZIP,
        ".h5p",
    )

    assert resultado.entry == ENTRADAS_ZIP[0]
    assert resultado.verified_same_file is True


def test_match_without_zip_entry_returns_error():
    resultado = match_drive_resource_to_zip({"nombre": "nada.pdf"}, ENTRADAS_ZIP, ".pdf")

    assert resultado.entry is None
    assert resultado.error == "NO_ZIP_MATCH"
    assert resultado.verified_same_file is False


def test_match_with_two_zip_entries_of_same_name_is_ambiguous():
    entradas = ENTRADAS_ZIP + [{"nombre": "OTRO.pdf", "miembro": "y/OTRO.pdf"}]

    resultado = match_drive_resource_to_zip({"nombre": "otro.pdf"}, entradas, ".pdf")

    assert resultado.entry is None
    assert resultado.error == "AMBIGUOUS_SAME_NAME"


# ============================================================
# MISMO RECURSO EN VARIAS ACTIVIDADES
# ============================================================

def test_detect_duplicate_assignments_groups_by_name_and_size():
    avisos = detect_duplicate_assignments([
        {"archivo_drive": "a.pdf", "tamano_drive": 5, "hoja": "H", "fila": 3},
        {"archivo_drive": "A.pdf", "tamano_drive": 5, "hoja": "H", "fila": 2},
        {"archivo_drive": "b.pdf", "tamano_drive": 5, "hoja": "H", "fila": 4},
        {"archivo_drive": "c.pdf", "tamano_drive": None},
    ])

    assert [aviso.code for aviso in avisos] == ["CROSS_ACTIVITY_DUPLICATE"]
    assert "H fila 2, H fila 3" in avisos[0].message
    assert '"A.pdf" (5 bytes)' in avisos[0].message
