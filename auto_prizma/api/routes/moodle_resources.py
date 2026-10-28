"""Rutas web para analizar y publicar recursos de Moodle desde una instancia local."""

import ipaddress
import os

from fastapi import File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from auto_prizma.core.application import app
from auto_prizma.services.auth import _usuario_actual
from auto_prizma.services.moodle_resources import (
    cancel_moodle_publish,
    attach_manual_resource,
    create_moodle_preview,
    get_moodle_job,
    MAX_MANUAL_RESOURCE_BYTES,
    pause_moodle_publish,
    public_moodle_status,
    resume_moodle_publish,
    start_moodle_publish,
)
from auto_prizma.web.moodle_views import render_moodle_page


def _request_is_local(request):
    host = str(request.client.host if request.client else "").split("%", 1)[0]
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _owner():
    return str(_usuario_actual() or "")


@app.get("/moodle", response_class=HTMLResponse)
def moodle_home(request: Request):
    local = _request_is_local(request)
    return HTMLResponse(
        render_moodle_page(local=local),
        status_code=200 if local else 403,
    )


@app.post("/moodle/analizar", response_class=HTMLResponse)
async def moodle_analyze(
    request: Request,
    matriz_archivo: UploadFile = File(...),
    recursos_zip: UploadFile = File(...),
    course_url: str = Form(...),
):
    if not _request_is_local(request):
        return HTMLResponse(render_moodle_page(local=False), status_code=403)
    try:
        matrix_bytes = await matriz_archivo.read()
        zip_bytes = await recursos_zip.read()
        if not matrix_bytes or not zip_bytes:
            raise ValueError("Selecciona la matriz y el archivo ZIP de recursos.")
        job = create_moodle_preview(
            _owner(),
            matriz_archivo.filename,
            matrix_bytes,
            recursos_zip.filename,
            zip_bytes,
            course_url,
        )
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        return HTMLResponse(
            render_moodle_page(error=str(exc), local=True),
            status_code=400,
        )
    return RedirectResponse("/moodle/" + job["id"], status_code=303)


@app.get("/moodle/{job_id}", response_class=HTMLResponse)
def moodle_job_page(job_id: str, request: Request, vista: str = ""):
    if not _request_is_local(request):
        return HTMLResponse(render_moodle_page(local=False), status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job:
        return HTMLResponse(render_moodle_page(error="No se encontró la vista previa Moodle."), status_code=404)
    # ?vista=previa vuelve a mostrar la matriz después de una publicación terminada.
    return HTMLResponse(render_moodle_page(job, local=True, show_preview=vista == "previa"))


@app.post("/moodle/{job_id}/publicar", response_class=HTMLResponse)
def moodle_publish(
    job_id: str,
    request: Request,
    publish_mode: str = Form(...),
    entry_keys: list[str] = Form(default=[]),
    clean_labels: str = Form(default=""),
):
    if not _request_is_local(request):
        return HTMLResponse(render_moodle_page(local=False), status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job:
        return HTMLResponse(render_moodle_page(error="No se encontró la vista previa Moodle."), status_code=404)
    try:
        start_moodle_publish(job, publish_mode, entry_keys, clean_labels=clean_labels == "1")
    except ValueError as exc:
        return HTMLResponse(render_moodle_page(job, error=str(exc), local=True), status_code=400)
    return RedirectResponse("/moodle/" + job_id, status_code=303)


@app.get("/moodle/{job_id}/estado")
def moodle_job_status(job_id: str, request: Request):
    if not _request_is_local(request):
        return JSONResponse({"error": "Disponible solo desde la instancia local."}, status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job:
        return JSONResponse({"error": "Vista previa no encontrada."}, status_code=404)
    return public_moodle_status(job)


@app.post("/moodle/{job_id}/recurso-manual")
async def moodle_attach_manual_resource(
    job_id: str,
    request: Request,
    entry_key: str = Form(...),
    resource_file: UploadFile = File(...),
):
    if not _request_is_local(request):
        return JSONResponse({"error": "Disponible solo desde la instancia local."}, status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job:
        return JSONResponse({"error": "Vista previa no encontrada."}, status_code=404)
    try:
        if job.get("status") in {"queued", "logging_in", "publishing", "paused"}:
            raise ValueError("Espera a que termine la publicación antes de cambiar un archivo.")
        content = await resource_file.read(MAX_MANUAL_RESOURCE_BYTES + 1)
        if len(content) > MAX_MANUAL_RESOURCE_BYTES:
            raise ValueError("El archivo supera el límite de 200 MB para una carga manual.")
        attach_manual_resource(job, entry_key, resource_file.filename, content)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except OSError:
        return JSONResponse({"error": "No se pudo guardar el archivo seleccionado."}, status_code=500)
    return JSONResponse({"ok": True, "message": "Archivo asociado a la fila."})


_CONTROL_ACTIONS = {
    "pausar": pause_moodle_publish,
    "reanudar": resume_moodle_publish,
    "cancelar": cancel_moodle_publish,
}


@app.post("/moodle/{job_id}/{action}")
def moodle_control(job_id: str, action: str, request: Request):
    """Pausar, reanudar o cancelar la publicación en curso (lo usa la página con fetch)."""
    if action not in _CONTROL_ACTIONS:
        return JSONResponse({"error": "Acción no válida."}, status_code=404)
    if not _request_is_local(request):
        return JSONResponse({"error": "Disponible solo desde la instancia local."}, status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job:
        return JSONResponse({"error": "Vista previa no encontrada."}, status_code=404)
    try:
        _CONTROL_ACTIONS[action](job)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    return public_moodle_status(job)


@app.get("/moodle/{job_id}/reporte")
def moodle_download_report(job_id: str, request: Request, formato: str = "csv"):
    if not _request_is_local(request):
        return JSONResponse({"error": "Disponible solo desde la instancia local."}, status_code=403)
    job = get_moodle_job(job_id, _owner())
    if not job or not job.get("report"):
        return JSONResponse({"error": "Reporte Moodle no disponible."}, status_code=404)
    if formato not in {"json", "csv"}:
        return JSONResponse({"error": "Formato de reporte no válido."}, status_code=400)
    path = str((job.get("report_paths") or {}).get("jsonPath" if formato == "json" else "csvPath") or "")
    if not path or not os.path.isfile(path):
        return JSONResponse({"error": "El reporte Moodle ya no está disponible."}, status_code=404)
    media_type = "application/json" if formato == "json" else "text/csv"
    return FileResponse(path, media_type=media_type, filename=os.path.basename(path))
