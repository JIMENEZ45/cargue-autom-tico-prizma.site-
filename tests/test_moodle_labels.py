"""Moodle: borrar las etiquetas de bloque que la matriz no usa en cada semana."""

import uuid

import pytest

from auto_prizma.automation.moodle.client import MoodleClient
from auto_prizma.domain.moodle_resources import label_cleanup_plan
from auto_prizma.services import moodle_resources


def _row(week, category, resource_type, row=2):
    return {"week": week, "category": category, "resourceType": resource_type, "sourceRow": row, "title": "x"}


def test_plan_marks_only_the_blocks_a_week_does_not_use():
    plan = label_cleanup_plan([
        _row("Semana 1", "OVI", "PDF"),
        _row("Semana 1", "OVA", "Video interactivo Avatar"),
        _row("Semana 2", "OVI", "Recurso H5P"),
        _row("Semana 2", "CHALLENGE", "Reto evaluativo"),
        _row("Semana 3", "OVI", "Infografía"),
        _row("Semana 3", "OVI", "Video a cámara"),
    ])
    by_week = {item["week"]: item for item in plan}

    assert by_week["Semana 1"]["delete"] == ["challenge"]
    assert by_week["Semana 2"]["delete"] == ["audiovisual"]
    # Los videos a cámara se suben a mano: por precaución se conserva el bloque audiovisual.
    assert by_week["Semana 3"]["delete"] == ["challenge"]


def test_plan_does_not_touch_weeks_with_rows_it_cannot_classify():
    plan = label_cleanup_plan(
        [_row("Semana 1", "OVI", "PDF"), _row("Semana 2", "OVI", "PDF"), _row("Semana 2", "OVI", "Podcast")],
        [{"week": "Semana 1", "missing": ["Tipo de recurso"]}],
    )
    assert all(item["delete"] == [] and item["uncertain"] for item in plan)


def test_plan_is_ordered_from_week_one():
    plan = label_cleanup_plan([_row("Semana 10", "OVI", "PDF"), _row("Semana 2", "OVI", "PDF")])
    assert [item["week"] for item in plan] == ["Semana 2", "Semana 10"]


class _Locator:
    def __init__(self, page, name):
        self.page = page
        self.name = name

    @property
    def first(self):
        return self

    @property
    def last(self):
        return self

    def count(self):
        return 1

    def locator(self, selector):
        return _Locator(self.page, self.name + ">" + selector)

    def get_by_text(self, text, exact=False):
        return _Locator(self.page, self.name + ">text:" + text)

    def get_by_role(self, role, name=None):
        return _Locator(self.page, self.name + ">" + role + ":" + name.pattern)

    def filter(self, **options):
        return self

    def evaluate_all(self, script, arg):
        return self.page.cards

    def scroll_into_view_if_needed(self):
        pass

    def click(self):
        self.page.events.append("click " + self.name)

    def wait_for(self, **options):
        self.page.events.append("wait " + self.name + " " + options.get("state", ""))

    def inner_text(self):
        return self.page.dialog_text


class _Page:
    def __init__(self, cards, dialog_text="Esto eliminará Reto Evaluativo y cualquier dato."):
        self.cards = cards
        self.dialog_text = dialog_text
        self.events = []

    def locator(self, selector):
        return _Locator(self, selector)

    def get_by_role(self, role, name=None):
        return _Locator(self, role)


def _client(page):
    client = MoodleClient.__new__(MoodleClient)
    client.page = page
    client.current_week = "Semana 1"
    return client


def test_delete_label_uses_menu_then_borrar_then_confirms_borrar():
    page = _Page([
        {"id": "module-90", "isLabel": False, "text": "reto evaluativo final.pdf archivo"},
        {"id": "module-77", "isLabel": True, "text": "reto evaluativo"},
    ])
    assert _client(page).delete_unused_label("challenge") == "deleted"

    clicks = [event for event in page.events if event.startswith("click")]
    assert clicks[0].startswith('click [id="module-77"]>') and "dropdown" in clicks[0]
    assert "text:Borrar" in clicks[1]
    assert clicks[2].endswith("button:^Borrar$")
    assert page.events[-1] == 'wait [id="module-77"] detached'


def test_delete_label_returns_missing_when_the_week_has_no_such_label():
    page = _Page([{"id": "module-5", "isLabel": False, "text": "planteamiento del problema y reto evaluativo de la unidad con mucho texto"}])
    assert _client(page).delete_unused_label("challenge") == "missing"
    assert page.events == []


def test_delete_label_refuses_when_there_are_two_labels():
    page = _Page([
        {"id": "module-1", "isLabel": True, "text": "reto evaluativo"},
        {"id": "module-2", "isLabel": True, "text": "reto evaluativo"},
    ])
    with pytest.raises(RuntimeError):
        _client(page).delete_unused_label("challenge")
    assert not any(event.startswith("click") for event in page.events)


def test_delete_label_cancels_if_the_dialog_names_something_else():
    page = _Page([{"id": "module-77", "isLabel": True, "text": "reto evaluativo"}], dialog_text="Esto eliminará Otra cosa")
    with pytest.raises(RuntimeError):
        _client(page).delete_unused_label("challenge")
    assert page.events[-1].endswith("button:^Cancelar$")
    assert not any(event.endswith("button:^Borrar$") for event in page.events)


def test_insertion_falls_back_to_the_next_existing_label_or_week_end():
    client = MoodleClient.__new__(MoodleClient)
    present = {"challenge"}
    client._label_visible = lambda block, timeout_ms: block in present
    assert client._next_present_block("digital") == "challenge"
    present.clear()
    assert client._next_present_block("digital") is None
    assert client._next_present_block("audiovisual") is None


class _Client:
    def __init__(self):
        self.deleted = []

    def open_course(self, url):
        pass

    def open_week(self, week):
        self.week = week

    def wait_for_week_content(self):
        pass

    def find_existing_resource(self, *args):
        return "123"

    def delete_unused_label(self, block):
        self.deleted.append((self.week, block))
        return "deleted" if block == "challenge" else "missing"


class _Worker:
    def __init__(self, client):
        self.client = client

    def get_client(self, *args):
        return self.client


def _job(clean_labels):
    course = "https://prizma.americana.edu.co/course/view.php?id=" + uuid.uuid4().hex
    return {
        "id": uuid.uuid4().hex,
        "owner": "adminlocal",
        "course_url": course,
        "status": "queued",
        "progress": {"index": 0, "total": 1, "week": "", "title": "", "phase": ""},
        "live_results": [],
        "label_results": [],
        "cancel_requested": False,
        "pause_requested": False,
        "clean_labels": clean_labels,
        "label_weeks": ["Semana 1", "Semana 2"],
        "label_plan": [
            {"week": "Semana 1", "used": ["digital"], "delete": ["audiovisual", "challenge"], "uncertain": False},
            {"week": "Semana 2", "used": ["digital", "audiovisual", "challenge"], "delete": [], "uncertain": False},
        ],
    }


def _entry(job):
    return {
        "key": job["course_url"] + ":h:Semana 1:2:Uno:digital", "previewKey": "2:Uno:digital", "sourceRow": 2,
        "week": "Semana 1", "title": "Uno", "kind": "pdf", "destination": {"module": "file", "block": "digital"},
    }


def test_batch_publish_deletes_unused_labels_at_the_end_and_reports_them():
    job = _job(True)
    client = _Client()
    moodle_resources._run_moodle_publish(job, "batch", [_entry(job)], _Worker(client))

    assert client.deleted == [("Semana 1", "audiovisual"), ("Semana 1", "challenge")]
    assert [item["status"] for item in job["report"]["labels"]] == ["No estaba", "Borrada"]
    assert job["status"] == "completed"


def test_labels_are_never_deleted_without_the_option_or_in_test_mode():
    for mode, clean in (("batch", False), ("test", True)):
        job = _job(clean)
        client = _Client()
        moodle_resources._run_moodle_publish(job, mode, [_entry(job)], _Worker(client))
        assert client.deleted == []


def test_start_publish_only_enables_label_cleanup_in_batch_mode(monkeypatch):
    submitted = []
    monkeypatch.setattr(moodle_resources, "_worker_for", lambda owner: type("W", (), {"submit": lambda self, *args: submitted.append(args)})())
    job = {
        "id": "j", "owner": "u", "course_url": "https://prizma.americana.edu.co/course/view.php?id=1", "matrix_filename": "m.csv",
        "status": "preview", "progress": {},
        "entries": [{"key": "2:Uno:digital", "status": "matched", "sourceRow": 2, "week": "Semana 1", "title": "Uno"}],
    }
    moodle_resources.start_moodle_publish(job, "test", ["2:Uno:digital"], clean_labels=True)
    assert job["clean_labels"] is False
    job["status"] = "completed"
    moodle_resources.start_moodle_publish(job, "batch", ["2:Uno:digital"], clean_labels=True)
    assert job["clean_labels"] is True


def test_only_the_weeks_being_published_are_cleaned():
    job = _job(True)
    job["label_plan"].append({"week": "Semana 3", "used": [], "delete": ["challenge"], "uncertain": False})
    job["label_weeks"] = ["Semana 1"]
    client = _Client()
    moodle_resources._run_moodle_publish(job, "batch", [_entry(job)], _Worker(client))
    assert {week for week, _block in client.deleted} == {"Semana 1"}


def test_dialog_check_accepts_moodle_internal_name_of_the_same_label():
    names = MoodleClient._dialog_names_card
    assert names("¿Eliminar actividad? Esto eliminará Reto Evaluativo y cualquier dato.", "Reto Evaluativo", "reto evaluativo")
    # Mayúsculas, acentos o texto extra en el nombre interno de la etiqueta.
    assert names("Esto eliminará RETO EVALUATIVO y cualquier dato.", "Reto Evaluativo", "reto evaluativo")
    assert names("Esto eliminará Recurso educativo audiovisual Semana 3 y cualquier dato.", "Recurso educativo audiovisual", "recurso educativo audiovisual")
    assert names("Esto eliminará Reto Eval... y cualquier dato.", "Reto Evaluativo", "reto evaluativo")
    # Otra cosa distinta: no se confirma.
    assert not names("Esto eliminará Mapa conceptual de rigor y cualquier dato.", "Reto Evaluativo", "reto evaluativo")


def test_dialog_text_waits_until_moodle_fills_in_what_it_deletes():
    texts = iter(["¿Eliminar actividad?", "¿Eliminar actividad?", "¿Eliminar actividad? Esto eliminará Reto Evaluativo y cualquier dato."])
    waits = []

    class Dialog:
        def inner_text(self):
            return next(texts)

    client = MoodleClient.__new__(MoodleClient)
    client.page = type("P", (), {"wait_for_timeout": lambda self, ms: waits.append(ms)})()
    assert "Reto Evaluativo" in client._dialog_text_with_target(Dialog())
    assert waits == [500, 500]


def test_open_week_goes_to_the_week_link_even_if_it_is_hidden():
    events = []

    class Page:
        url = "https://prizma.americana.edu.co/course/view.php?id=716"

        def evaluate(self, script, name):
            assert name == "Semana 3"
            return "https://prizma.americana.edu.co/course/view.php?id=716&section=3"

        def goto(self, url, **options):
            events.append(("goto", url))

        def wait_for_load_state(self, state, **options):
            events.append(("load", state))

        def wait_for_timeout(self, ms):
            pass

        def get_by_text(self, *args, **kwargs):
            raise AssertionError("no debe hacer clic en enlaces que pueden estar ocultos")

    client = MoodleClient.__new__(MoodleClient)
    client.page = Page()
    client.open_week("Semana 3")

    assert events[0] == ("goto", "https://prizma.americana.edu.co/course/view.php?id=716&section=3")
    assert client.current_section_id == "3"
    assert client.current_week == "Semana 3"
