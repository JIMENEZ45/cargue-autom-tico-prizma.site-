"""Hora de la aplicacion: Colombia (America/Bogota) para historial, reportes y estados."""

from datetime import datetime

from auto_prizma.core.config import ZONA_HORARIA_COLOMBIA


def _ahora_colombia():
    return datetime.now(ZONA_HORARIA_COLOMBIA)


def _ahora_colombia_iso():
    return _ahora_colombia().isoformat(timespec="seconds")
