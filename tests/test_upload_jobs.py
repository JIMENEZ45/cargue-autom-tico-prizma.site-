"""Pruebas del servicio de trabajos de cargue (auto_prizma/services/upload_jobs.py)."""

import pytest

from auto_prizma.services import upload_jobs

CLAVE = "clave-secreta-de-prizma"


def _contiene(valor, buscado):
    """True si `buscado` aparece en cualquier valor anidado de dicts/listas."""
    if isinstance(valor, dict):
        return any(_contiene(v, buscado) for v in valor.values())
    if isinstance(valor, (list, tuple, set)):
        return any(_contiene(v, buscado) for v in valor)
    return isinstance(valor, str) and buscado in valor


@pytest.fixture
def trabajo_en_memoria(monkeypatch):
    """Registra un trabajo de prueba en TRABAJOS y lo limpia al terminar."""
    trabajo_id = "prueba-credenciales"
    upload_jobs.TRABAJOS[trabajo_id] = {
        "id": trabajo_id,
        "etapa": "analizado",
        "mensaje": "",
        "usuario_app": "adminlocal",
        "procesar_ovi": True,
        "procesar_ova": False,
        "procesar_retos": False,
        "ruta_excel": "matriz.xlsx",
        "ruta_zip": "recursos.zip",
        "carpeta_temp": "temp",
        "ruta_reporte": "reporte.csv",
    }
    yield trabajo_id
    upload_jobs.TRABAJOS.pop(trabajo_id, None)
    try:
        upload_jobs.COLA_CARGUES.remove(trabajo_id)
    except ValueError:
        pass


def test_enqueue_keeps_password_only_in_temporary_field(monkeypatch, trabajo_en_memoria):
    # Sin cupo: el trabajo queda en cola y no arranca ningun hilo.
    monkeypatch.setattr(upload_jobs, "CARGUES_ACTIVOS", upload_jobs.MAX_CARGUES_SIMULTANEOS)

    upload_jobs._encolar_trabajo(trabajo_en_memoria, "usuario", CLAVE)

    trabajo = upload_jobs.TRABAJOS[trabajo_en_memoria]
    assert trabajo["etapa"] == "en_cola"
    assert "credenciales_prizma" not in trabajo
    sin_temporales = {
        k: v for k, v in trabajo.items()
        if k not in ("usuario_prizma_temporal", "contrasena_prizma_temporal")
    }
    assert not _contiene(sin_temporales, CLAVE)


def test_password_is_gone_after_the_upload_thread_finishes(monkeypatch, trabajo_en_memoria):
    monkeypatch.setattr(upload_jobs, "CARGUES_ACTIVOS", upload_jobs.MAX_CARGUES_SIMULTANEOS)
    upload_jobs._encolar_trabajo(trabajo_en_memoria, "usuario", CLAVE)
    upload_jobs.COLA_CARGUES.remove(trabajo_en_memoria)

    recibidas = []
    monkeypatch.setattr(
        upload_jobs,
        "ejecutar_cargue_con_historial",
        lambda *args: recibidas.append(args[8]),
    )
    monkeypatch.setattr(upload_jobs, "_registrar_reporte_final", lambda trabajo: None)
    monkeypatch.setattr(upload_jobs, "CARGUES_ACTIVOS", 1)

    upload_jobs._ejecutar_cargue_en_hilo(trabajo_en_memoria)

    assert recibidas == [CLAVE]  # el motor si recibio la contrasena
    assert not _contiene(upload_jobs.TRABAJOS[trabajo_en_memoria], CLAVE)
