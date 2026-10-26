import io
import zipfile

import pytest

from auto_prizma.domain.moodle_resources import destination_for, normalize_key, resolve_resource
from auto_prizma.services import moodle_resources


def _zip_bytes():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("semana/U1-T1-Origen y transformacion de la analitica.pdf", b"pdf")
        archive.writestr("otros/solo-notas.txt", b"no se indexa")
    return output.getvalue()


def test_matching_preserves_original_moodle_prefix_and_extension_rules():
    row = {
        "category": "OVI",
        "resourceType": "PDF",
        "title": "Origen y transformación de la analítica",
        "linkLabel": "TEXTO - Origen y transformación de la analítica",
    }
    path = "resources/U1-T1-Origen y transformacion de la analitica.pdf"
    assert normalize_key("U1-T1-Origen y transformación de la analítica") == normalize_key(row["title"])
    assert destination_for(row)["block"] == "digital"
    assert resolve_resource(row, [{"path": path, "extension": ".pdf", "key": normalize_key(path.rsplit("/", 1)[-1][:-4])}]) == {
        "status": "matched",
        "path": path,
        "candidates": [path],
    }


def test_matches_matrix_infographic_to_h5p_file_with_h5p_name_prefix():
    row = {
        "category": "OVI",
        "resourceType": "Infografía",
        "title": "Ejemplos comparativos de textos académicos",
        "linkLabel": "Infografía - Ejemplos comparativos de textos académicos",
    }
    path = "resources/H5P - Ejemplos comparativos de textos académicos.h5p"
    indexed_file = {
        "path": path,
        "extension": ".h5p",
        "key": normalize_key("H5P - Ejemplos comparativos de textos académicos"),
    }

    result = resolve_resource(row, [indexed_file])

    assert result == {"status": "matched", "path": path, "candidates": [path]}


def test_prefixed_duplicate_h5p_files_remain_ambiguous():
    row = {
        "category": "OVI",
        "resourceType": "Infografía",
        "title": "Ejemplos comparativos de textos académicos",
        "linkLabel": "Infografía - Ejemplos comparativos de textos académicos",
    }
    paths = (
        "resources/H5P - Ejemplos comparativos de textos académicos.h5p",
        "resources/copia/H5P - Ejemplos comparativos de textos académicos.h5p",
    )
    indexed_files = [
        {"path": path, "extension": ".h5p", "key": normalize_key(path.rsplit("/", 1)[-1][:-5])}
        for path in paths
    ]

    result = resolve_resource(row, indexed_files)

    assert result == {"status": "ambiguous", "candidates": list(paths)}


def test_preview_extracts_only_supported_resources_and_keeps_course_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(moodle_resources, "UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(moodle_resources, "DATA_DIR", str(tmp_path / "data"))
    matrix = (
        "Programa,Curso,Semana correspondiente,Unidad,Nombre del recurso,Categoría,Tipo de recurso,Enlace\n"
        "P,C,Semana 1,Unidad 1,Origen y transformación de la analítica,OVI,PDF,TEXTO - Origen y transformación de la analítica\n"
    ).encode("utf-8")

    job = moodle_resources.create_moodle_preview(
        "adminlocal",
        "matriz.csv",
        matrix,
        "recursos.zip",
        _zip_bytes(),
        "https://prizma.americana.edu.co/course/view.php?id=42",
    )

    assert job["owner"] == "adminlocal"
    assert job["summary"]["matched"] == 1
    assert job["entries"][0]["status"] == "matched"
    assert job["entries"][0]["week"] == "Semana 1"
    assert len(moodle_resources.index_resource_files(job["resources_root"])) == 1


def test_preview_rejects_course_from_another_host(tmp_path, monkeypatch):
    monkeypatch.setattr(moodle_resources, "UPLOADS_DIR", str(tmp_path / "uploads"))
    with pytest.raises(ValueError, match="enlace HTTPS válido"):
        moodle_resources.validate_course_url("https://example.com/course/view.php?id=42")


def test_invalid_matrix_does_not_leave_an_uploaded_job_directory(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    monkeypatch.setattr(moodle_resources, "UPLOADS_DIR", str(uploads))
    with pytest.raises(ValueError, match="encabezados requeridos"):
        moodle_resources.create_moodle_preview(
            "adminlocal",
            "matriz.csv",
            b"esta no es la matriz requerida\n",
            "recursos.zip",
            _zip_bytes(),
            "https://prizma.americana.edu.co/course/view.php?id=42",
        )
    assert not (uploads / "moodle").exists()


def test_publishable_entries_rejects_unmatched_keys():
    job = {"entries": [{"key": "matched", "status": "matched", "sourceRow": 2}]}
    assert moodle_resources.publishable_entries(job, ["matched"])[0]["key"] == "matched"
    with pytest.raises(ValueError, match="no están disponibles"):
        moodle_resources.publishable_entries(job, ["missing"])


def test_publishable_entries_start_from_week_one():
    job = {"entries": [
        {"key": "s10", "status": "matched", "sourceRow": 2, "week": "Semana 10"},
        {"key": "s2", "status": "matched", "sourceRow": 3, "week": "Semana 2"},
        {"key": "s1b", "status": "matched", "sourceRow": 9, "week": "Semana 1"},
        {"key": "s1a", "status": "matched", "sourceRow": 4, "week": "Semana 1"},
    ]}
    keys = [entry["key"] for entry in moodle_resources.publishable_entries(job, ["s10", "s2", "s1b", "s1a"])]
    assert keys == ["s1a", "s1b", "s2", "s10"]
