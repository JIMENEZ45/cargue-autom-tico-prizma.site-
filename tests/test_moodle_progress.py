"""Moodle: no duplicar recursos ya publicados y pantalla de cargue en progreso."""

import re
import uuid

from auto_prizma.automation.moodle.client import MoodleClient
from auto_prizma.services import moodle_resources
from auto_prizma.web.moodle_views import render_moodle_page


class _Client:
    """Cliente simulado que nunca ve el recurso en la página (como cuando la semana aún no cargó)."""

    def __init__(self):
        self.published = []

    def open_course(self, url):
        pass

    def open_week(self, week):
        pass

    def find_existing_resource(self, *args):
        return None

    def publish(self, entry, on_before_save=None):
        on_before_save and on_before_save()
        self.published.append(entry["title"])
        return "4321"


class _Worker:
    def __init__(self, client):
        self.client = client

    def get_client(self, *args):
        return self.client


def _job(course_url):
    return {
        "id": uuid.uuid4().hex,
        "owner": "adminlocal",
        "course_url": course_url,
        "status": "queued",
        "progress": {"index": 0, "total": 1, "week": "", "title": "", "phase": ""},
        "live_results": [],
        "cancel_requested": False,
        "pause_requested": False,
    }


def _entry(course_url, matrix_hash, source_row=5):
    preview_key = str(source_row) + ":Claves para formular el planteamiento del problema:digital"
    return {
        "key": course_url + ":" + matrix_hash + ":Semana 5:" + preview_key,
        "previewKey": preview_key,
        "sourceRow": source_row,
        "week": "Semana 5",
        "title": "Claves para formular el planteamiento del problema",
        "kind": "h5p",
        "destination": {"module": "h5p", "block": "digital"},
        "path": "Claves.h5p",
    }


def test_resource_published_before_is_not_published_again_even_if_the_page_misses_it():
    course = "https://prizma.americana.edu.co/course/view.php?id=" + uuid.uuid4().hex
    client = _Client()

    first = _job(course)
    moodle_resources._run_moodle_publish(first, "test", [_entry(course, "hash-a")], _Worker(client))
    assert first["live_results"][0]["status"] == "Cargado"

    # Mismo recurso con un id numérico en el historial: antes se volvía a subir si la página no lo mostraba.
    second = _job(course)
    moodle_resources._run_moodle_publish(second, "batch", [_entry(course, "hash-a")], _Worker(client))
    assert second["live_results"][0]["status"] == "Ya estaba cargado"

    # Matriz exportada de nuevo (otro hash y otra fila): sigue reconociéndose por curso, semana, título y bloque.
    third = _job(course)
    moodle_resources._run_moodle_publish(third, "batch", [_entry(course, "hash-b", source_row=9)], _Worker(client))
    assert third["live_results"][0]["status"] == "Ya estaba cargado"

    assert client.published == ["Claves para formular el planteamiento del problema"]


def test_same_title_in_another_course_is_still_published():
    client = _Client()
    for _ in range(2):
        course = "https://prizma.americana.edu.co/course/view.php?id=" + uuid.uuid4().hex
        moodle_resources._run_moodle_publish(_job(course), "batch", [_entry(course, "hash-a")], _Worker(client))
    assert len(client.published) == 2


def test_open_week_waits_for_the_week_page_before_checking_existing_resources():
    events = []

    class Tab:
        def count(self):
            return 1

        def nth(self, _index):
            return self

        def is_visible(self):
            return True

        @property
        def first(self):
            return self

        def evaluate(self, script):
            return "/course/view.php?id=7&section=5"

        def click(self):
            events.append("click")

    class Page:
        url = "https://prizma.americana.edu.co/course/view.php?id=7"

        def get_by_text(self, text, exact=False):
            return Tab()

        def wait_for_url(self, pattern, **options):
            assert re.search(pattern, "https://x/course/view.php?id=7&section=5")
            assert not re.search(pattern, "https://x/course/view.php?id=7&section=51")
            events.append("wait-url")
            self.url = "https://prizma.americana.edu.co/course/view.php?id=7&section=5"

        def wait_for_load_state(self, state, **options):
            events.append("load-" + state)

        def wait_for_timeout(self, milliseconds):
            pass

    client = MoodleClient.__new__(MoodleClient)
    client.page = Page()
    client.open_week("Semana 5")

    assert events == ["click", "wait-url", "load-networkidle"]
    assert client.current_section_id == "5"


def _base_job(status):
    return {
        "id": "job-progress",
        "status": status,
        "message": "Revisando Semana 1: Uno",
        "course_url": "https://prizma.americana.edu.co/course/view.php?id=1",
        "matrix_filename": "m.csv",
        "zip_filename": "r.zip",
        "summary": {"matched": 2},
        "entries": [
            {"key": "2:Uno:digital", "status": "matched", "sourceRow": 2, "week": "Semana 1", "title": "Uno", "kind": "pdf", "category": "OVI", "resourceType": "PDF"},
            {"key": "3:Dos:digital", "status": "matched", "sourceRow": 3, "week": "Semana 1", "title": "Dos", "kind": "pdf", "category": "OVI", "resourceType": "PDF"},
        ],
        "queue": [
            {"previewKey": "2:Uno:digital", "sourceRow": 2, "week": "Semana 1", "title": "Uno", "kind": "pdf"},
            {"previewKey": "3:Dos:digital", "sourceRow": 3, "week": "Semana 1", "title": "Dos", "kind": "pdf"},
        ],
        "live_results": [
            {"previewKey": "2:Uno:digital", "sourceRow": 2, "week": "Semana 1", "title": "Uno", "kind": "pdf", "status": "Cargado", "detail": ""},
        ],
        "progress": {"index": 2, "total": 2, "week": "Semana 1", "title": "Dos", "phase": "Subiendo el archivo"},
        "started_at": "2026-10-21T15:00:00+00:00",
    }


def test_running_publish_shows_only_the_upload_progress_not_the_matrix():
    page = render_moodle_page(_base_job("publishing"))

    assert "Cargue Moodle en progreso" in page
    assert "Recursos del cargue" in page
    assert "Recursos por semana" not in page
    assert "¿Qué quieres publicar?" not in page
    assert page.count('class="moodle-queue-item ok"') == 1
    assert page.count('class="moodle-queue-item procesando"') == 1
    assert "50%" in page
    assert 'data-moodle-control="pausar"' in page


def test_finished_publish_shows_the_result_and_the_matrix_only_on_request():
    job = _base_job("completed")
    job["report"] = moodle_resources.report_from_results([
        {"entry": {"sourceRow": 2, "week": "Semana 1", "title": "Uno", "previewKey": "2:Uno:digital"}, "status": "Cargado", "detail": ""},
    ])
    job["report_paths"] = {}

    result = render_moodle_page(job)
    assert "Resultado de la publicación" in result
    assert "Recursos por semana" not in result
    assert "?vista=previa" in result

    preview = render_moodle_page(job, show_preview=True)
    assert "Recursos por semana" in preview
    assert "Volver al resultado de la publicación" in preview
