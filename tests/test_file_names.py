"""Pruebas de los nombres de archivo de recursos (auto_prizma/domain/file_names.py)."""

import unicodedata

import pytest

from auto_prizma.domain.file_names import exact_name_key, file_base_name


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("carpeta/sub/Recurso 1.h5p", "Recurso 1.h5p"),
        (r"carpeta\sub\Recurso 1.h5p", "Recurso 1.h5p"),
        ("  Lectura.pdf  ", "Lectura.pdf"),
        ("Lectura.pdf", "Lectura.pdf"),
        (None, ""),
    ],
)
def test_file_base_name(valor, esperado):
    assert file_base_name(valor) == esperado


def test_exact_name_key_unifies_accent_forms_only():
    nfd = unicodedata.normalize("NFD", "Guía.pdf")
    nfc = unicodedata.normalize("NFC", "Guía.pdf")

    assert nfd != nfc
    assert exact_name_key("zip/" + nfd) == exact_name_key(nfc) == nfc
    # Sigue siendo exacta: distingue mayusculas y guiones.
    assert exact_name_key("guía.pdf") != exact_name_key("Guía.pdf")
    assert exact_name_key("Recurso-1.pdf") != exact_name_key("Recurso–1.pdf")
