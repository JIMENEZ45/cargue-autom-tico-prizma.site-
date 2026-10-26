"""Drive: los enlaces se consultan en cada análisis, con reintentos, y los errores dicen el motivo."""

import collections

from auto_prizma.integrations.google import drive as drive_module

FOLDER = "application/vnd.google-apps.folder"


class _HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class _FakeDrive:
    """Simula files().get en lote: cada id falla las veces indicadas y luego responde una carpeta."""

    def __init__(self, failures=None, status=403):
        self.failures = collections.Counter(failures or {})
        self.status = status
        self.calls = collections.Counter()

    def files(self):
        return self

    def get(self, fileId, fields, supportsAllDrives):
        return fileId

    def new_batch_http_request(self, callback):
        drive = self

        class Batch:
            def __init__(self):
                self.ids = []

            def add(self, request, request_id):
                self.ids.append(request_id)

            def execute(self):
                for drive_id in self.ids:
                    drive.calls[drive_id] += 1
                    if drive.failures[drive_id] > 0:
                        drive.failures[drive_id] -= 1
                        callback(drive_id, None, _HttpError(drive.status))
                    else:
                        callback(drive_id, {"id": drive_id, "name": "carpeta", "mimeType": FOLDER}, None)

        return Batch()


def _no_wait(monkeypatch):
    monkeypatch.setattr(drive_module, "DRIVE_ESPERAS_REINTENTO", (0, 0))
    monkeypatch.setattr(drive_module.time, "sleep", lambda seconds: None)


def test_transient_errors_are_retried(monkeypatch):
    _no_wait(monkeypatch)
    fake = _FakeDrive({"a": 1, "b": 2})
    metadatos, errores = drive_module._obtener_metadatos_drive_en_lote(fake, ["a", "b", "c"], "id")

    assert all(metadatos[drive_id]["mimeType"] == FOLDER for drive_id in "abc")
    assert errores == {}
    assert fake.calls == {"a": 2, "b": 3, "c": 1}


def test_permanent_error_keeps_a_readable_reason(monkeypatch):
    _no_wait(monkeypatch)
    fake = _FakeDrive({"a": 99}, status=404)
    metadatos, errores = drive_module._obtener_metadatos_drive_en_lote(fake, ["a"], "id")

    assert metadatos["a"] is None
    assert "404" in errores["a"] and "no tiene acceso" in errores["a"]
    assert fake.calls["a"] == 3


def _preload(monkeypatch, fake, drive_id):
    monkeypatch.setattr(drive_module, "build", lambda *args, **kwargs: fake)
    monkeypatch.setattr(drive_module, "_cargar_credenciales_google", lambda *args: object())
    monkeypatch.setattr(drive_module, "_listar_carpetas_drive_en_lote", lambda drive, ids: {})
    actividad = {"_url_drive_sheet": "https://drive.google.com/open?id=" + drive_id + "&usp=drive_copy"}
    drive_module._precargar_referencias_drive_batch([actividad])
    with drive_module._CACHE_REFERENCIAS_DRIVE_LOCK:
        return dict(drive_module._CACHE_REFERENCIAS_DRIVE[drive_module._clave_cache_drive(drive_id)])


def test_a_failed_link_is_queried_again_in_the_next_analysis(monkeypatch):
    _no_wait(monkeypatch)
    drive_id = "1KZlpqkFl0KZsLj-prueba-refresco"

    first = _preload(monkeypatch, _FakeDrive({drive_id: 99}, status=429), drive_id)
    assert first["tipo"] == "error"
    assert "429" in first["error"]

    # Antes el error quedaba guardado y la fila seguía "sin archivo" hasta reiniciar el servidor.
    second = _preload(monkeypatch, _FakeDrive(), drive_id)
    assert second["tipo"] == "folder"
