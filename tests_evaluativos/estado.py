"""Estado en memoria de los tests evaluativos y utilidades de sesion y credenciales de PRIZMA.
"""

from __future__ import annotations

import json
import os
import threading
import sys

from fastapi import Request

from .models import Severity


_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.RLock()
_AUTOMATION_JOBS: dict[str, dict] = {}
_AUTOMATION_LOCK = threading.RLock()
_AUTOMATION_SYNC: dict[str, dict] = {}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"




def _ruta_token_prizma(usuario: str) -> str:
    tokens_dir = os.path.join(os.path.dirname(__file__), "..", "data", "tokens")
    os.makedirs(tokens_dir, exist_ok=True)
    return os.path.join(tokens_dir, f"prizma_{usuario}.json")


def _cargar_credenciales_prizma(usuario: str) -> dict:
    ruta = _ruta_token_prizma(usuario)
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"usuario": "", "recordar": True}


def _guardar_credenciales_prizma(usuario: str, creds: dict):
    ruta = _ruta_token_prizma(usuario)
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _user(request: Request) -> str:
    return str(getattr(request.state, "usuario", "") or "").strip().lower()


def _job_for(request: Request, job_id: str) -> dict | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job or job.get("owner") != _user(request):
            return None
        return job


def _issue_counts(issues):
    return {
        "error": sum(issue.severity is Severity.ERROR for issue in issues),
        "warning": sum(issue.severity is Severity.WARNING for issue in issues),
    }

def _es_google_conectado(usuario: str) -> bool:
    main_mod = sys.modules.get("auto_prizma.google_oauth")
    if main_mod and hasattr(main_mod, "_google_conectado"):
        try:
            return bool(main_mod._google_conectado(usuario))
        except Exception:
            pass
    token_path = os.path.join(os.path.dirname(__file__), "..", "data", f"tokens_{usuario}.json")
    return os.path.exists(token_path)
