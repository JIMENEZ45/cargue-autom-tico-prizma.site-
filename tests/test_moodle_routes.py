import io
import zipfile

from fastapi.testclient import TestClient

from main import app
from auto_prizma.services.auth import _firmar_sesion
from auto_prizma.services import moodle_resources


def _client():
    client = TestClient(app)
    client.cookies.set("ap_sesion", _firmar_sesion("adminlocal"))
    return client


def _resources_zip():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("U1-T1-Recurso de analitica.pdf", b"pdf")
    return output.getvalue()


def test_moodle_home_uses_common_frame_and_local_only_gate(monkeypatch):
    monkeypatch.setattr("auto_prizma.api.routes.moodle_resources._request_is_local", lambda _request: True)
    response = _client().get("/moodle")

    assert response.status_code == 200
    assert 'aria-current="page"' in response.text
    assert 'name="matriz_archivo"' in response.text
    assert 'name="recursos_zip"' in response.text
    assert 'href="/app.css?v=' in response.text

    monkeypatch.setattr("auto_prizma.api.routes.moodle_resources._request_is_local", lambda _request: False)
    denied = _client().get("/moodle")
    assert denied.status_code == 403
    assert "solo está disponible desde una instancia local" in denied.text


def test_moodle_analysis_uploads_matrix_and_zip_then_shows_preview(tmp_path, monkeypatch):
    monkeypatch.setattr("auto_prizma.api.routes.moodle_resources._request_is_local", lambda _request: True)
    monkeypatch.setattr(moodle_resources, "UPLOADS_DIR", str(tmp_path / "uploads"))
    matrix = (
        "Semana correspondiente,Unidad,Nombre del recurso,Categoría,Tipo de recurso,Enlace\n"
        "Semana 1,Unidad 1,Recurso de analítica,OVI,PDF,TEXTO - Recurso de analítica\n"
    ).encode("utf-8")
    response = _client().post(
        "/moodle/analizar",
        files={
            "matriz_archivo": ("matriz.csv", matrix, "text/csv"),
            "recursos_zip": ("recursos.zip", _resources_zip(), "application/zip"),
        },
        data={"course_url": "https://prizma.americana.edu.co/course/view.php?id=42"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    preview = _client().get(response.headers["location"])
    assert preview.status_code == 200
    assert "Recurso de analítica" in preview.text
    assert "Listo para publicar" in preview.text
    job_id = response.headers["location"].rsplit("/", 1)[-1]
    assert moodle_resources.get_moodle_job(job_id, "adminlocal") is not None
    assert moodle_resources.get_moodle_job(job_id, "otro-usuario") is None
