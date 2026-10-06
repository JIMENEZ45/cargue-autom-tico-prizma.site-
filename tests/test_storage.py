"""Pruebas de la lectura/escritura de archivos de datos (auto_prizma/core/storage.py)."""

import json

import pytest

from auto_prizma.core.storage import read_json, write_json_atomic, write_text_atomic


def test_read_json_returns_default_when_missing(tmp_path):
    assert read_json(str(tmp_path / "no_existe.json"), {}, dict) == {}


def test_read_json_returns_default_on_invalid_json_or_wrong_type(tmp_path):
    corrupto = tmp_path / "corrupto.json"
    corrupto.write_text("{no es json", encoding="utf-8")
    lista = tmp_path / "lista.json"
    lista.write_text("[1, 2]", encoding="utf-8")

    assert read_json(str(corrupto), {}, dict) == {}
    assert read_json(str(lista), {}, dict) == {}
    assert read_json(str(lista), [], list) == [1, 2]


def test_read_json_propagates_unexpected_errors_by_default(tmp_path):
    # usuarios.json con bytes no UTF-8: no debe tratarse como "sin usuarios",
    # porque al crear un usuario se sobrescribiria el archivo danado.
    danado = tmp_path / "usuarios.json"
    danado.write_bytes(b"\xff\xfe\x00 basura")

    with pytest.raises(UnicodeDecodeError):
        read_json(str(danado), {}, dict)

    assert read_json(str(danado), [], list, errors=(Exception,)) == []


def test_write_json_atomic_keeps_accents_and_leaves_no_temp_file(tmp_path):
    destino = tmp_path / "historial.json"

    write_json_atomic(str(destino), [{"curso": "Gestión Financiera"}])

    contenido = destino.read_text(encoding="utf-8")
    assert "Gestión Financiera" in contenido
    assert json.loads(contenido) == [{"curso": "Gestión Financiera"}]
    assert not (tmp_path / "historial.json.tmp").exists()


def test_write_json_atomic_matches_previous_format(tmp_path):
    destino = tmp_path / "usuarios.json"
    datos = {"ana": {"nombre": "Ána", "activo": True}}

    write_json_atomic(str(destino), datos)

    assert destino.read_text(encoding="utf-8") == json.dumps(datos, ensure_ascii=False, indent=2)


def test_write_text_atomic_replaces_existing_content(tmp_path):
    destino = tmp_path / "token.json"
    destino.write_text("viejo", encoding="utf-8")

    write_text_atomic(str(destino), '{"token": "nuevo"}')

    assert destino.read_text(encoding="utf-8") == '{"token": "nuevo"}'
    assert not (tmp_path / "token.json.tmp").exists()
