"""HTML del modulo de tests: layout, revision del documento y tarjeta de estado.

_patch_main_nav agrega el boton Test al menu de /cargue-actual
(auto_prizma/rutas/cargues.py) en memoria.
"""

from __future__ import annotations

import html
import json
import re
import sys

from fastapi.responses import HTMLResponse

from .models import Severity, document_to_dict
from .validation import validate_document
from .estado import (
    _cargar_credenciales_prizma,
    _issue_counts,
)


def _patch_main_nav():
    """Garantiza en memoria que el botón Test aparezca en /cargue-actual sin tocar auto_prizma/rutas/cargues.py."""
    main_mod = sys.modules.get("auto_prizma.rutas.cargues")
    if not main_mod:
        return

    orig_vacio = getattr(main_mod, "_pagina_sin_cargue_actual", None)
    if orig_vacio and not getattr(orig_vacio, "_ap_patched", False):
        def nuevo_vacio(*args, **kwargs):
            resp = orig_vacio(*args, **kwargs)
            if hasattr(resp, "body"):
                body_str = resp.body.decode("utf-8")
                if 'href="/tests"' not in body_str and '<a class="nav-item activo" href="/cargue-actual">' in body_str:
                    body_str = body_str.replace(
                        '<a class="nav-item activo" href="/cargue-actual">',
                        '<a class="nav-item" href="/tests">▣ <span>Test</span></a><a class="nav-item activo" href="/cargue-actual">'
                    )
                    return HTMLResponse(body_str, status_code=resp.status_code)
            return resp
        nuevo_vacio._ap_patched = True
        setattr(main_mod, "_pagina_sin_cargue_actual", nuevo_vacio)

    orig_cargue = getattr(main_mod, "cargue_actual", None)
    if orig_cargue and not getattr(orig_cargue, "_ap_patched", False):
        def nuevo_cargue(*args, **kwargs):
            resp = orig_cargue(*args, **kwargs)
            if hasattr(resp, "body"):
                body_str = resp.body.decode("utf-8")
                if 'href="/tests"' not in body_str and '<a class="nav-item activo" href="/cargue-actual">' in body_str:
                    body_str = body_str.replace(
                        '<a class="nav-item activo" href="/cargue-actual">',
                        '<a class="nav-item" href="/tests">▣ <span>Test</span></a><a class="nav-item activo" href="/cargue-actual">'
                    )
                    return HTMLResponse(body_str, status_code=resp.status_code)
            return resp
        nuevo_cargue._ap_patched = True
        app = getattr(main_mod, "app", None)
        if app:
            for route in app.routes:
                if getattr(route, "path", None) == "/cargue-actual":
                    route.endpoint = nuevo_cargue
        setattr(main_mod, "cargue_actual", nuevo_cargue)


_patch_main_nav()


def _layout(title: str, body: str, active: str = "Test") -> str:
    _patch_main_nav()
    nav = "".join(
        f'<a class="nav-item {"activo" if label == active else ""}" href="{href}">{icon}<span>{label}</span></a>'
        for label, href, icon in [
            ("Inicio", "/", "⌂"),
            ("Test", "/tests", "▣"),
            ("Cargue actual", "/cargue-actual", "⇧"),
            ("Historial", "/historial", "◷"),
            ("Reportes", "/reportes", "▥"),
            ("Mi contraseña", "/cambiar-clave", "✎"),
            ("Salir", "/salir", "⏻"),
        ]
    )
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} - Auto Prizma Pro</title><style>
:root{{--fondo:#f7f8fc;--texto:#101828;--muted:#667085;--borde:#e5e7ef;--morado:#5548e8;--verde:#087f5b;--rojo:#b42318;--amarillo:#9a6700;--sombra:0 10px 30px rgba(29,41,57,.05)}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--fondo);color:var(--texto);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
.app{{min-height:100vh;display:grid;grid-template-columns:235px 1fr}}
.sidebar{{position:sticky;top:0;height:100vh;background:#fff;border-right:1px solid var(--borde);padding:28px 20px;display:flex;flex-direction:column}}
.marca{{display:flex;align-items:center;gap:12px;margin-bottom:34px}}
.marca strong{{display:block;font-size:18px}}
.marca span{{display:block;color:var(--muted);font-size:12px;margin-top:3px}}
.logo{{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,#6d5dfc,#4338ca);color:#fff;font-weight:900;font-size:22px;box-shadow:0 8px 20px rgba(79,70,229,.25)}}
.nav{{display:grid;gap:8px}}
.nav-item{{padding:12px 14px;border-radius:11px;color:#475467;font-size:14px;display:flex;gap:11px;align-items:center;text-decoration:none}}
.nav-item.activo,.nav-item:hover{{background:#f1efff;color:#4f46e5;font-weight:700}}
.contenido{{padding:34px 38px;min-width:0}}
.layout-tests{{display:grid;grid-template-columns:1fr 340px;gap:24px;align-items:start}}
.panel{{background:#fff;border:1px solid var(--borde);border-radius:18px;box-shadow:var(--sombra);padding:26px;margin-bottom:18px}}
.panel-ayuda{{padding:24px;background:#fff;border:1px solid var(--borde);border-radius:18px}}
.panel-ayuda h3{{margin:0 0 18px;font-size:17px;color:#101828}}
.paso-ayuda{{display:grid;grid-template-columns:30px 1fr;gap:12px;align-items:start;margin-bottom:16px;color:#475467;font-size:13px;line-height:1.5}}
.paso-ayuda b{{width:28px;height:28px;border-radius:50%;background:#f1efff;color:#4f46e5;display:grid;place-items:center;font-size:13px;font-weight:800}}
.ayuda-separador{{height:1px;background:var(--borde);margin:22px 0}}
.titulo-consejos{{color:#4f46e5;font-size:16px;margin:0 0 12px}}
.consejo{{color:#475467;font-size:13px;line-height:1.55;margin:0 0 10px}}
h1{{margin:0 0 8px;font-size:29px}}
h2{{margin:0 0 12px;font-size:20px}}
p{{color:var(--muted);line-height:1.5;margin:0 0 14px}}
.pasos{{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 24px}}
.paso{{padding:8px 14px;border-radius:999px;background:#f1efff;color:#5548e8;font-size:12px;font-weight:800}}
.dropzone{{display:grid;place-items:center;border:2px dashed #b8b3f8;border-radius:14px;padding:32px 20px;text-align:center;background:#fbfaff;cursor:pointer;transition:all .2s}}
.dropzone:hover,.dropzone.dragover{{border-color:#5548e8;background:#f4f2ff}}
input,textarea,select{{width:100%;border:1px solid #d0d5dd;border-radius:10px;padding:11px 13px;font:inherit;color:inherit;background:#fff}}
textarea{{min-height:78px;resize:vertical}}
label{{display:block;font-size:12px;font-weight:800;margin:13px 0 6px;color:#344054}}
button,.boton{{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;border-radius:10px;padding:12px 18px;background:var(--morado);color:#fff;font-weight:800;font-size:14px;text-decoration:none;cursor:pointer}}
button:hover,.boton:hover{{opacity:.93}}
button.secundario,.boton.secundario{{background:#fff;color:#5548e8;border:1px solid #c7c2ff}}
.acciones{{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px}}
.test-card{{border:1px solid var(--borde);border-radius:16px;padding:22px;margin-top:18px;background:#fcfcff;box-shadow:0 4px 12px rgba(0,0,0,.02)}}
.section{{border-left:4px solid #7c6dfc;padding-left:16px;margin:20px 0}}
.question{{background:#fff;border:1px solid var(--borde);border-radius:12px;padding:16px;margin:14px 0;transition:all .2s;scroll-margin-top:24px}}
.question.question-error{{border:2px solid #f04438 !important;background:#fffbfa !important;box-shadow:0 0 0 4px rgba(240,68,56,0.12);}}
.badge{{display:inline-block;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:800;margin:3px 6px 3px 0}}
.badge.ok{{background:#ecfdf3;color:var(--verde)}}
.badge.warn{{background:#fff8e1;color:var(--amarillo)}}
.badge.error{{background:#fef3f2;color:var(--rojo)}}
.issue{{padding:12px 14px;border-radius:10px;margin:8px 0;font-size:13px;line-height:1.5}}
.issue.error{{background:#fef3f2;color:var(--rojo);border:1px solid #fecdca}}
.issue.warning{{background:#fff8e1;color:var(--amarillo);border:1px solid #fedf89}}
.issue.ok{{background:#ecfdf3;color:var(--verde);border:1px solid #a6f4c5}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.option-row,.pair-row{{display:grid;grid-template-columns:42px 1fr auto;gap:10px;align-items:center;margin-top:8px}}
.pair-row{{grid-template-columns:1fr 1fr}}
.muted{{color:var(--muted);font-size:12px}}
@media(max-width:1100px){{.layout-tests{{grid-template-columns:1fr}}.panel-ayuda{{order:2}}}}
@media(max-width:900px){{.app{{grid-template-columns:1fr}}.sidebar{{display:none}}.contenido{{padding:20px}}.grid2{{grid-template-columns:1fr}}}}
.estado-servicio{{margin-top:auto;border:1px solid var(--borde);border-radius:14px;padding:15px}}
.servicio-linea{{font-size:12px;font-weight:800;color:#07894f;margin-bottom:14px}}
.punto{{width:8px;height:8px;background:#12b76a;border-radius:50%;display:inline-block;margin-right:7px}}
.servicio-mini{{display:flex;justify-content:space-between;align-items:center;font-size:11px;color:var(--muted);margin-top:10px}}
.chip{{background:#eef2ff;color:#4f46e5;border-radius:999px;padding:4px 8px}}
html[data-theme="dark"] .test-card,
html[data-theme="dark"] .panel-ayuda,
html[data-theme="dark"] .question,
html[data-theme="dark"] .dropzone {{
  background: #111827 !important;
  color: #e5e7eb !important;
  border-color: #263244 !important;
}}
html[data-theme="dark"] .question.question-error {{
  background: #2a1a1a !important;
  border-color: #f04438 !important;
}}
html[data-theme="dark"] .section {{ border-left-color: #6d5dfc !important; }}
html[data-theme="dark"] .titulo-consejos,
html[data-theme="dark"] .paso-ayuda,
html[data-theme="dark"] .consejo,
html[data-theme="dark"] .muted {{ color: #aeb9ca !important; }}
html[data-theme="dark"] .ayuda-separador {{ background: #263244 !important; }}
html[data-theme="dark"] .issue.error {{ background: #2a1a1a !important; border-color: #633 !important; }}
html[data-theme="dark"] .issue.warning {{ background: #2a2210 !important; border-color: #7a5c00 !important; }}
html[data-theme="dark"] .issue.ok {{ background: #103322 !important; border-color: #0a5c3a !important; }}
html[data-theme="dark"] .badge.ok {{ background: #103322 !important; }}
html[data-theme="dark"] .badge.warn {{ background: #2a2210 !important; }}
html[data-theme="dark"] .badge.error {{ background: #2a1a1a !important; }}

/* ---- Estados dinamicos reutilizables (banners, kpis, badges, tarjeta en vivo) ---- */
.status-banner{{display:flex;gap:14px;align-items:flex-start;margin-bottom:20px;border-radius:14px;padding:20px;border:2px solid transparent;box-shadow:0 4px 12px rgba(0,0,0,.06)}}
.status-banner .status-icon{{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-size:22px;font-weight:900;flex-shrink:0}}
.status-banner h3{{margin:0 0 6px;font-size:17px;font-weight:800}}
.status-banner p{{margin:0 0 12px;font-size:14px;line-height:1.5}}
.status-banner .acciones{{margin-top:0}}
.status-banner--ok{{background:#f6fef9;border-color:#a6f4c5}}
.status-banner--ok .status-icon{{background:#d1fadf;color:#027a48}}
.status-banner--ok h3,.status-banner--ok p{{color:#027a48}}
.status-banner--error{{background:#fffbfa;border-color:#fecdca}}
.status-banner--error .status-icon{{background:#fee4e2;color:#d92d20}}
.status-banner--error h3{{color:#b42318}}
.status-banner--error p{{color:#7a271a}}
.status-banner--warn{{background:#fffcf5;border-color:#fedf89}}
.status-banner--warn .status-icon{{background:#fef0c7;color:#b54708}}
.status-banner--warn h3{{color:#92400e}}
.status-banner--warn p{{color:#78350f}}

.kpi-card{{background:#fff;border:1px solid var(--borde);border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(16,24,40,.05)}}
.kpi-card .kpi-label{{font-size:12px;font-weight:700;text-transform:uppercase;color:var(--muted)}}
.kpi-card .kpi-valor{{font-size:28px;font-weight:900;margin-top:4px;color:var(--texto)}}
.kpi-card--ok{{background:#f6fef9;border-color:#a6f4c5}}
.kpi-card--ok .kpi-label,.kpi-card--ok .kpi-valor{{color:#027a48}}
.kpi-card--warn{{background:#fffcf5;border-color:#fedf89}}
.kpi-card--warn .kpi-label,.kpi-card--warn .kpi-valor{{color:#b54708}}
.kpi-card--error{{background:#fffbfa;border-color:#fecdca}}
.kpi-card--error .kpi-label,.kpi-card--error .kpi-valor{{color:#b42318}}

.badge-dinamico{{display:inline-block;border-radius:999px;padding:5px 10px;font-size:12px;font-weight:800}}
.badge-dinamico--pendiente{{background:#f2f4f7;color:#344054}}
.badge-dinamico--proceso{{background:#fef0c7;color:#b54708}}
.badge-dinamico--ok{{background:#ecfdf3;color:#087f5b}}
.badge-dinamico--error{{background:#fef3f2;color:#b42318}}
.badge-dinamico--detenido{{background:#e5e7eb;color:#374151}}

.live-card{{border-radius:16px;padding:20px 24px;box-shadow:0 4px 14px rgba(0,0,0,.04);border:2px solid transparent;margin-bottom:24px;transition:all .3s ease}}
.live-card--running{{background:#fbfaff;border-color:#6366f1}}
.live-card--waiting{{background:#fef2f2;border-color:#ef4444}}
.live-card h3{{margin:0;font-size:16px;font-weight:800;color:var(--texto)}}
.live-card p{{margin:3px 0 0;font-size:13px;color:var(--muted)}}

.progress-track{{background:#e2e8f0;border-radius:999px;height:9px;overflow:hidden}}
.progress-fill{{background:linear-gradient(90deg,#5548e8,#818cf8);height:100%;transition:width .4s ease}}

.mode-option{{flex:1;min-width:180px;border:1px solid var(--borde);border-radius:12px;padding:14px;cursor:pointer;background:#fff;transition:all .2s}}
.mode-option strong{{margin-left:7px;font-size:14px}}
.mode-option span{{display:block;margin:5px 0 0 25px;color:var(--muted);font-size:12px}}
.mode-option--activo{{border-color:#5548e8;background:#f8f7ff}}

.alert-soft{{margin-top:14px;border-radius:12px;padding:14px;display:flex;gap:12px;align-items:center}}
.alert-soft--ok{{background:#ecfdf3;border:1px solid #a6f4c5;color:#027a48}}
.alert-soft--warn{{background:#fff8df;border:1px solid #f5c451;color:#7a4b00;align-items:flex-start}}
.alert-soft a{{color:#4f46e5;font-weight:700}}

.test-card-header{{background:#f8f9fc;border-bottom:1px solid #edeafc}}
.chip-morado{{display:inline-block;font-size:12px;background:#edeafc;padding:3px 8px;border-radius:6px;color:#4338ca;font-weight:600}}

#btn-guardar-correcciones.is-dirty{{background:#e11d48 !important;color:#fff !important;font-weight:800;box-shadow:0 0 0 4px rgba(225,29,72,.35)}}

html[data-theme="dark"] .status-banner--ok{{background:#0b2318 !important;border-color:#0a5c3a !important}}
html[data-theme="dark"] .status-banner--ok h3,html[data-theme="dark"] .status-banner--ok p{{color:#86efac !important}}
html[data-theme="dark"] .status-banner--error{{background:#2a1a1a !important;border-color:#633 !important}}
html[data-theme="dark"] .status-banner--error h3{{color:#fca5a5 !important}}
html[data-theme="dark"] .status-banner--error p{{color:#fecaca !important}}
html[data-theme="dark"] .status-banner--warn{{background:#2a2210 !important;border-color:#7a5c00 !important}}
html[data-theme="dark"] .status-banner--warn h3{{color:#fbbf24 !important}}
html[data-theme="dark"] .status-banner--warn p{{color:#fde68a !important}}

html[data-theme="dark"] .kpi-card{{background:#111827 !important;border-color:#263244 !important}}
html[data-theme="dark"] .kpi-card .kpi-label{{color:#aeb9ca !important}}
html[data-theme="dark"] .kpi-card .kpi-valor{{color:#f3f4f6 !important}}
html[data-theme="dark"] .kpi-card--ok{{background:#0b2318 !important;border-color:#0a5c3a !important}}
html[data-theme="dark"] .kpi-card--ok .kpi-label,html[data-theme="dark"] .kpi-card--ok .kpi-valor{{color:#4ade80 !important}}
html[data-theme="dark"] .kpi-card--warn{{background:#2a2210 !important;border-color:#7a5c00 !important}}
html[data-theme="dark"] .kpi-card--warn .kpi-label,html[data-theme="dark"] .kpi-card--warn .kpi-valor{{color:#fbbf24 !important}}
html[data-theme="dark"] .kpi-card--error{{background:#2a1a1a !important;border-color:#633 !important}}
html[data-theme="dark"] .kpi-card--error .kpi-label,html[data-theme="dark"] .kpi-card--error .kpi-valor{{color:#fca5a5 !important}}

html[data-theme="dark"] .badge-dinamico--pendiente{{background:#1f2937 !important;color:#cbd5e1 !important}}
html[data-theme="dark"] .badge-dinamico--proceso{{background:#2a2210 !important;color:#fbbf24 !important}}
html[data-theme="dark"] .badge-dinamico--ok{{background:#0b2318 !important;color:#4ade80 !important}}
html[data-theme="dark"] .badge-dinamico--error{{background:#2a1a1a !important;color:#fca5a5 !important}}
html[data-theme="dark"] .badge-dinamico--detenido{{background:#263244 !important;color:#cbd5e1 !important}}

html[data-theme="dark"] .live-card--running{{background:#111827 !important;border-color:#6d5dfc !important}}
html[data-theme="dark"] .live-card--waiting{{background:#2a1a1a !important;border-color:#ef4444 !important}}

html[data-theme="dark"] .mode-option{{background:#111827 !important;border-color:#263244 !important;color:#e5e7eb !important}}
html[data-theme="dark"] .mode-option span{{color:#aeb9ca !important}}
html[data-theme="dark"] .mode-option--activo{{background:#1d2540 !important;border-color:#818cf8 !important}}

html[data-theme="dark"] .alert-soft--ok{{background:#0b2318 !important;border-color:#0a5c3a !important;color:#86efac !important}}
html[data-theme="dark"] .alert-soft--warn{{background:#2a2210 !important;border-color:#7a5c00 !important;color:#fde68a !important}}
html[data-theme="dark"] .alert-soft a{{color:#a5b4fc !important}}

html[data-theme="dark"] .progress-track{{background:#1f2937 !important}}

html[data-theme="dark"] .test-card-header{{background:#0f172a !important;border-bottom-color:#263244 !important}}
html[data-theme="dark"] .chip-morado{{background:#1d2540 !important;color:#a5b4fc !important}}
html[data-theme="dark"] button.secundario,
html[data-theme="dark"] .boton.secundario{{background:#111827 !important;color:#a5b4fc !important;border-color:#334155 !important}}
.boton.secundario.peligro{{border-color:#fda29b;color:#b42318}}
html[data-theme="dark"] .boton.secundario.peligro{{background:#2a1a1a !important;color:#fca5a5 !important;border-color:#7a3b3b !important}}
</style><link rel="stylesheet" href="/estilos-responsive.css"><script src="/tema.js" defer></script></head><body><div class="app"><aside class="sidebar"><div class="marca"><div class="logo">A</div><div><strong>Auto Prizma Pro</strong><span>Automatización PRIZMA</span></div></div><nav class="nav">{nav}</nav><div class="estado-servicio"><div class="servicio-linea"><span class="punto"></span> Servicio activo</div><div class="servicio-mini"><span>Navegador</span><span class="chip">Chromium</span></div><div class="servicio-mini"><span>Conexión</span><span class="chip">Estable</span></div></div></aside><main class="contenido">{body}</main></div></body></html>'''


def _render_issues(issues) -> str:
    if not issues:
        return '<span class="badge ok" id="badge-todas-validadas">✓ Todas las preguntas y claves validadas</span>'
    items = []
    for issue in issues:
        m = re.match(r"tests\[(\d+)\]\.sections\[(\d+)\]\.questions\[(\d+)\]", issue.path)
        if m:
            t_idx, s_idx, q_idx = m.groups()
            anchor = f"#pregunta-{t_idx}-{s_idx}-{q_idx}"
            target_id = f"pregunta-{t_idx}-{s_idx}-{q_idx}"
            items.append(
                f'<div class="issue {issue.severity.value}" data-issue-target="{target_id}" data-original-msg="{html.escape(issue.message, quote=True)}" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">'
                f'<div class="issue-text"><strong>{issue.severity.value.title()}</strong>: {html.escape(issue.message)}</div>'
                f'<a class="issue-link" href="{anchor}" onclick="irAPregunta(\'{target_id}\', {t_idx}); return false;" style="color:#5548e8;font-weight:700;text-decoration:underline;font-size:12px;cursor:pointer;">Ir a la pregunta ➔</a>'
                f'</div>'
            )
        else:
            items.append(f'<div class="issue {issue.severity.value}"><div class="issue-text"><strong>{issue.severity.value.title()}</strong>: {html.escape(issue.message)}</div></div>')
    return "".join(items)


def _render_review(job_id: str, job: dict, message: str = "") -> str:
    document: TestDocument = job["document"]
    issues = validate_document(document)
    counts = _issue_counts(issues)
    state = json.dumps(document_to_dict(document), ensure_ascii=False).replace("<", "\\u003c")
    issues_by_path: dict[str, list] = {}
    for issue in issues:
        issues_by_path.setdefault(issue.path, []).append(issue)

    owner = job.get("owner", "")
    creds = _cargar_credenciales_prizma(owner)

    job_creds = job.get("credenciales_prizma") or {}
    usuario_prizma_val = job_creds.get("usuario") or creds.get("usuario", "")
    clave_prizma_val = job_creds.get("clave", "")

    cascada_datos = job.get("cascada_datos") or {}
    cascada_facultad_val = cascada_datos.get("facultad", "")
    cascada_programa_val = cascada_datos.get("programa") or document.program or ""
    cascada_pensum_val = cascada_datos.get("pensum", "")
    cascada_nivel_val = cascada_datos.get("nivel", "")
    cascada_asignatura_val = cascada_datos.get("asignatura", "")


    programa_sugerido = cascada_programa_val or document.program or ""
    primera_semana = document.tests[0].week if document.tests else ""
    primer_corte = document.tests[0].cut if document.tests else ""

    cards = []
    for test_index, test in enumerate(document.tests):
        sections = []
        for section_index, section in enumerate(test.sections):
            questions = []
            for question_index, question in enumerate(section.questions):
                q_path = f"tests[{test_index}].sections[{section_index}].questions[{question_index}]"
                q_issues = issues_by_path.get(q_path, [])
                has_q_error = any(i.severity == Severity.ERROR for i in q_issues)
                error_class = " question-error" if has_q_error else ""
                
                error_alert = ""
                if q_issues:
                    error_items = "".join(f'<li style="margin:3px 0;">{html.escape(i.message)}</li>' for i in q_issues)
                    error_alert = f'<div class="issue error" style="margin:0 0 12px 0;"><strong>⚠️ Corrección requerida en Pregunta {question_index + 1}:</strong><ul style="margin:4px 0 0 18px;padding:0;">{error_items}</ul></div>'
                
                badge_estado = '<span class="badge error">❌ Requiere atención</span>' if has_q_error else '<span class="badge ok">✓ Válida</span>'

                option_html = ""
                if section.code == "trueOrFalse":
                    value = "true" if question.answer is True else "false" if question.answer is False else ""
                    option_html = f'<div style="margin-top:10px;"><label>Respuesta Correcta</label><select style="max-width:200px;" data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-field="answer"><option value="">Selecciona una opción</option><option value="true" {"selected" if value == "true" else ""}>Verdadero</option><option value="false" {"selected" if value == "false" else ""}>Falso</option></select></div>'
                elif section.code == "multipleChoice":
                    option_html = "<div style='margin-top:10px;'><label>Opciones y Clave (marca la casilla de la respuesta correcta)</label>" + "".join(
                        f'<div class="option-row"><strong>{html.escape(option.letter.upper())}</strong><input data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-option="{option_index}" data-field="option_text" value="{html.escape(option.text, quote=True)}"><label style="margin:0;display:flex;align-items:center;gap:5px;cursor:pointer;"><input type="checkbox" style="width:auto;" data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-option="{option_index}" data-field="option_correct" {"checked" if option.letter in question.correct_option_letters else ""}> Correcta</label></div>'
                        for option_index, option in enumerate(question.options)
                    ) + "</div>"
                elif section.code == "matching":
                    option_html = "<div style='margin-top:10px;'><label>Parejas Concepto - Definición</label>" + "".join(
                        f'<div class="pair-row"><input placeholder="Concepto (Col A)" data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-pair="{pair_index}" data-field="pair_left" value="{html.escape(pair.left, quote=True)}"><input placeholder="Descripción (Col B)" data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-pair="{pair_index}" data-field="pair_right" value="{html.escape(pair.right, quote=True)}"></div>'
                        for pair_index, pair in enumerate(question.pairs)
                    ) + "</div>"
                questions.append(
                    f'<div class="question{error_class}" id="pregunta-{test_index}-{section_index}-{question_index}">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                    f'<label style="margin:0;font-weight:800;font-size:13px;">Pregunta {question_index + 1}</label>'
                    f'{badge_estado}'
                    f'</div>'
                    f'{error_alert}'
                    f'<textarea data-test="{test_index}" data-section="{section_index}" data-question="{question_index}" data-field="prompt">{html.escape(question.prompt)}</textarea>'
                    f'{option_html}'
                    f'</div>'
                )
            sections.append(f'<div class="section"><h3>{html.escape(section.name)} ({len(section.questions)} pregunta{"s" if len(section.questions)!=1 else ""})</h3>{"".join(questions)}</div>')
        num_preguntas_test = sum(len(sec.questions) for sec in test.sections)
        cards.append(f'''<article class="test-card" id="test-card-{test_index}" style="margin-bottom:16px;padding:0;overflow:hidden;">
            <div class="test-card-header" onclick="toggleTestCard({test_index})" style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;cursor:pointer;user-select:none;">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
                    <span class="badge ok" style="font-weight:700;">Test {test_index + 1} de {len(document.tests)}</span>
                    <strong style="font-size:15px;">{html.escape(test.title or f"Evaluación {test_index + 1}")}</strong>
                    <span class="chip-morado">{num_preguntas_test} pregunta{'s' if num_preguntas_test != 1 else ''}</span>
                    <span class="muted" style="font-size:12px;">Semana {html.escape(test.week or "N/A")} | Corte {html.escape(test.cut or "N/A")}</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span id="test-toggle-text-{test_index}" style="font-size:12px;font-weight:700;color:#6366f1;">{"Contraer ▲" if test_index == 0 else "Desplegar ▼"}</span>
                </div>
            </div>
            <div class="test-card-body" id="test-card-body-{test_index}" style="padding:18px;{'display:block;' if test_index == 0 else 'display:none;'}">
                <div class="grid2">
                    <div><label>Título del test</label><input data-test="{test_index}" data-field="title" value="{html.escape(test.title, quote=True)}"></div>
                    <div class="grid2">
                        <div><label>Semana</label><input data-test="{test_index}" data-field="week" value="{html.escape(test.week, quote=True)}"></div>
                        <div><label>Corte</label><input data-test="{test_index}" data-field="cut" value="{html.escape(test.cut, quote=True)}"></div>
                    </div>
                </div>
                <label>Indicaciones / Descripción</label>
                <textarea data-test="{test_index}" data-field="description">{html.escape(test.description)}</textarea>
                {"".join(sections)}
            </div>
        </article>''')
    message_html = f'<div class="issue ok">{html.escape(message)}</div>' if message else ''
    error_badge_style = "" if counts["error"] else "display:none;"
    ok_badge_style = "" if not counts["error"] else "display:none;"

    body = f'''<h1>Revisión de Tests</h1><p>Analiza, audita y corrige preguntas antes de conectar la plataforma PRIZMA.</p>
    <div class="pasos"><span class="paso">1 Entrada ✓</span><span class="paso">2 Revisión activa</span><span class="paso">3 Configuración PRIZMA</span><span class="paso">4 Carga en cola</span></div>
    {message_html}
    <section class="panel">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:12px;">
            <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                <span class="badge ok">{len(document.tests)} test(s) detectado(s)</span>
                <span class="badge error" id="badge-contador-errores" style="{error_badge_style}"><span id="num-errores">{counts['error']}</span> error(es) pendiente(s)</span>
                <span class="badge ok" id="badge-sin-errores" style="{ok_badge_style}">✓ Todas las preguntas y claves validadas</span>
                <span class="badge {'warn' if counts['warning'] else 'ok'}">{counts['warning']} advertencia(s)</span>
            </div>
            <a href="#bloque-acceso-prizma" class="boton" style="text-decoration:none;padding:8px 16px;font-size:13px;">
                ⚡ Ir a Carga en PRIZMA ↓
            </a>
        </div>
        <div id="contenedor-issues" style="margin-top:14px">{_render_issues(issues)}</div>
    </section>
    <form id="review-form" class="panel" method="post" action="/tests/{job_id}/guardar">
        <input type="hidden" name="payload" id="payload">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px;">
            <div style="display:flex;gap:8px;">
                <button type="button" class="boton secundario" onclick="expandirTodosTests()" style="font-size:12px;padding:6px 12px;cursor:pointer;">＋ Expandir todos</button>
                <button type="button" class="boton secundario" onclick="contraerTodosTests()" style="font-size:12px;padding:6px 12px;cursor:pointer;">－ Contraer todos</button>
            </div>
        </div>
        {"".join(cards)}
        <div class="acciones">
            <button type="submit" id="btn-guardar-correcciones" style="transition:all .3s ease;padding:12px 22px;border-radius:10px;font-weight:700;">💾 Guardar correcciones</button>
            <a class="boton secundario" href="/tests/{job_id}/descargar">⬇ Descargar respaldo (JSON)</a>
            <a class="boton secundario" href="/tests">＋ Nuevo análisis</a>
        </div>
    </form>

    <section id="bloque-acceso-prizma" class="panel" style="margin-top:28px;border:2px solid var(--morado);background:#faf9ff;scroll-margin-top:24px;">
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px;">
            <div style="width:42px;height:42px;border-radius:12px;background:var(--morado);color:#fff;display:grid;place-items:center;font-size:22px;flex-shrink:0;">🛡</div>
            <div>
                <h2 style="margin:0;font-size:20px;">Fase 3: Publicación y Carga en PRIZMA</h2>
                <p style="margin:3px 0 0;font-size:13px;">Automatización con Playwright en tiempo real contra <strong>admin.prizma.site</strong></p>
            </div>
        </div>

        <form id="form-prizma" method="post" action="/tests/{job_id}/ejecutar-prizma">
            <div class="grid2">
                <div>
                    <label>Usuario PRIZMA</label>
                    <input name="prizma_usuario" placeholder="Ej. 1020304050" value="{html.escape(usuario_prizma_val)}" required>
                </div>
                <div>
                    <label>Contraseña PRIZMA</label>
                    <input type="password" name="prizma_clave" placeholder="••••••••" value="{html.escape(clave_prizma_val)}" required>
                </div>
            </div>

            <div style="display:flex;gap:18px;margin:14px 0 18px;flex-wrap:wrap;align-items:center;">
                <label style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-weight:600;font-size:13px;">
                    <input type="checkbox" name="recordar_credenciales" value="1" style="width:auto;" {"checked" if creds.get("recordar", True) else ""}>
                    Recordar usuario en este equipo
                </label>
            </div>

            <div style="border-top:1px dashed var(--borde);padding-top:16px;margin-top:10px;">
                <h3 style="margin:0 0 12px;font-size:15px;">Parámetros del Curso en PRIZMA (Selectores en Cascada)</h3>
                <div class="grid2">
                    <div>
                        <label>Facultad <small style="font-weight:normal;">(Opcional)</small></label>
                        <input name="cascada_facultad" placeholder="Opcional - Facultad institucional (ej. Virtual - Derecho)" value="{html.escape(cascada_facultad_val)}">
                    </div>
                    <div>
                        <label>Programa</label>
                        <input name="cascada_programa" placeholder="Código o Nombre (ej. COD111)" value="{html.escape(cascada_programa_val)}">
                    </div>
                </div>
                <div class="grid2">
                    <div>
                        <label>Pensum</label>
                        <input name="cascada_pensum" placeholder="Código del pensum (ej. COD111 o Pensum 2024)" value="{html.escape(cascada_pensum_val)}">
                    </div>
                    <div>
                        <label>Nivel de pensum</label>
                        <input name="cascada_nivel" placeholder="Nivel (ej. 3, Tres, Semestre 3...)" value="{html.escape(cascada_nivel_val)}">
                    </div>
                </div>
                <div class="grid2">
                    <div>
                        <label>Asignatura por pensum</label>
                        <input name="cascada_asignatura" placeholder="Código o Nombre de la asignatura" value="{html.escape(cascada_asignatura_val)}">
                    </div>
                    <div class="grid2">
                        <div>
                            <label>Semana</label>
                            <input name="cascada_semana" placeholder="Semana" value="{html.escape(primera_semana)}">
                        </div>
                        <div>
                            <label>Corte</label>
                            <input name="cascada_corte" placeholder="Corte" value="{html.escape(primer_corte)}">
                        </div>
                    </div>
                </div>
            </div>

            <div class="acciones" style="margin-top:22px;">
                <button type="submit" id="btn-lanzar-prizma" style="background:#087f5b;color:#fff;padding:14px 28px;font-size:15px;font-weight:800;border:none;border-radius:10px;cursor:pointer;display:inline-flex;align-items:center;gap:8px;box-shadow:0 4px 12px rgba(8,127,91,0.25);transition:all .2s;">
                    ⚡ Crear y Publicar Evaluación en PRIZMA
                </button>
            </div>
        </form>
    </section>

    <script>
    const initial={state};
    function val(q){{return q.type==='checkbox'?q.checked:q.value}}

    function verificarPreguntaValida(qBox) {{
        const selAnswer = qBox.querySelector('[data-field="answer"]');
        if (selAnswer) {{
            return selAnswer.value === 'true' || selAnswer.value === 'false';
        }}
        const checkboxes = qBox.querySelectorAll('[data-field="option_correct"]');
        if (checkboxes.length > 0) {{
            return Array.from(checkboxes).some(cb => cb.checked);
        }}
        const promptArea = qBox.querySelector('[data-field="prompt"]');
        if (promptArea) {{
            return promptArea.value.trim().length > 0;
        }}
        return true;
    }}

    function actualizarEstadoPreguntaEnVivo(qBox) {{
        if (!qBox) return;
        const targetId = qBox.id;
        const issueTop = document.querySelector(`[data-issue-target="${{targetId}}"]`);
        const esValida = verificarPreguntaValida(qBox);

        if (esValida) {{
            qBox.classList.remove('question-error');
            const errAlert = qBox.querySelector('.issue.error');
            if (errAlert) errAlert.style.display = 'none';
            const badge = qBox.querySelector('.badge');
            if (badge) {{
                badge.className = 'badge warn';
                badge.textContent = '✎ Modificado (por guardar)';
            }}
            if (issueTop) {{
                issueTop.className = 'issue ok';
                issueTop.dataset.resolved = 'true';
                const textDiv = issueTop.querySelector('.issue-text');
                if (textDiv) textDiv.innerHTML = '<strong>✓ Resuelto:</strong> Corrección aplicada (recuerda guardar cambios)';
                const link = issueTop.querySelector('.issue-link');
                if (link) link.style.display = 'none';
            }}
        }} else {{
            qBox.classList.add('question-error');
            const errAlert = qBox.querySelector('.issue.error');
            if (errAlert) errAlert.style.display = 'block';
            const badge = qBox.querySelector('.badge');
            if (badge) {{
                badge.className = 'badge error';
                badge.textContent = '❌ Requiere atención';
            }}
            if (issueTop) {{
                issueTop.className = 'issue error';
                delete issueTop.dataset.resolved;
                const textDiv = issueTop.querySelector('.issue-text');
                if (textDiv) textDiv.innerHTML = '<strong>Error</strong>: ' + (issueTop.dataset.originalMsg || '');
                const link = issueTop.querySelector('.issue-link');
                if (link) link.style.display = 'inline';
            }}
        }}

        // Recalcular errores pendientes
        const pendientes = document.querySelectorAll('#contenedor-issues .issue.error').length;
        const badgeContador = document.getElementById('badge-contador-errores');
        const badgeSinErrores = document.getElementById('badge-sin-errores');
        const numSpan = document.getElementById('num-errores');
        if (numSpan) numSpan.textContent = pendientes;
        if (pendientes === 0) {{
            if (badgeContador) badgeContador.style.display = 'none';
            if (badgeSinErrores) {{
                badgeSinErrores.style.display = 'inline-block';
                badgeSinErrores.textContent = '✓ Todas las preguntas corregidas (listo para guardar o cargar)';
            }}
        }} else {{
            if (badgeContador) badgeContador.style.display = 'inline-block';
            if (badgeSinErrores) badgeSinErrores.style.display = 'none';
        }}
    }}

    document.querySelectorAll('[data-field="answer"], [data-field="option_correct"], [data-field="prompt"]').forEach(el => {{
        el.addEventListener('change', () => actualizarEstadoPreguntaEnVivo(el.closest('.question')));
        el.addEventListener('input', () => actualizarEstadoPreguntaEnVivo(el.closest('.question')));
    }});

    document.getElementById('review-form').addEventListener('submit',()=>{{
        const data=structuredClone(initial);
        document.querySelectorAll('[data-field]').forEach(el=>{{
            const t=+el.dataset.test,s=el.dataset.section,q=el.dataset.question,f=el.dataset.field;
            if(f==='title'||f==='description'||f==='week'||f==='cut')data.tests[t][f]=val(el);
            if(f==='prompt')data.tests[t].sections[s].questions[q].prompt=val(el);
            if(f==='answer')data.tests[t].sections[s].questions[q].answer=val(el)==='true'?true:val(el)==='false'?false:null;
            if(f==='option_text')data.tests[t].sections[s].questions[q].options[+el.dataset.option].text=val(el);
            if(f==='option_correct'){{const o=data.tests[t].sections[s].questions[q].options[+el.dataset.option];o.correct=val(el);}}
            if(f==='pair_left')data.tests[t].sections[s].questions[q].pairs[+el.dataset.pair].left=val(el);
            if(f==='pair_right')data.tests[t].sections[s].questions[q].pairs[+el.dataset.pair].right=val(el);
        }});
        data.tests.forEach(t=>t.sections.forEach(sec=>sec.questions.forEach(q=>{{
            if(sec.code==='multipleChoice')q.correct_option_letters=q.options.filter(o=>o.correct).map(o=>o.letter);
        }})));
        document.getElementById('payload').value=JSON.stringify(data);
    }});

    function toggleTestCard(idx) {{
        const body = document.getElementById(`test-card-body-${{idx}}`);
        const txt = document.getElementById(`test-toggle-text-${{idx}}`);
        if (!body) return;
        if (body.style.display === 'none') {{
            body.style.display = 'block';
            if (txt) txt.textContent = 'Contraer ▲';
        }} else {{
            body.style.display = 'none';
            if (txt) txt.textContent = 'Desplegar ▼';
        }}
    }}

    function expandirTodosTests() {{
        document.querySelectorAll('.test-card-body').forEach(b => b.style.display = 'block');
        document.querySelectorAll('[id^="test-toggle-text-"]').forEach(t => t.textContent = 'Contraer ▲');
    }}

    function contraerTodosTests() {{
        document.querySelectorAll('.test-card-body').forEach(b => b.style.display = 'none');
        document.querySelectorAll('[id^="test-toggle-text-"]').forEach(t => t.textContent = 'Desplegar ▼');
    }}

    function irAPregunta(targetId, testIndex) {{
        const body = document.getElementById(`test-card-body-${{testIndex}}`);
        const txt = document.getElementById(`test-toggle-text-${{testIndex}}`);
        if (body) {{
            body.style.display = 'block';
            if (txt) txt.textContent = 'Contraer ▲';
        }}
        const qEl = document.getElementById(targetId);
        if (qEl) {{
            qEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            qEl.style.transition = 'all 0.3s ease';
            qEl.style.boxShadow = '0 0 0 4px #6366f1';
            setTimeout(() => {{ qEl.style.boxShadow = ''; }}, 2200);
            const firstInput = qEl.querySelector('input, select, textarea');
            if (firstInput) firstInput.focus();
        }}
    }}

    function marcarCambiosPendientes() {{
        const btn = document.getElementById('btn-guardar-correcciones');
        if (btn && !btn.dataset.dirty) {{
            btn.dataset.dirty = 'true';
            btn.classList.add('is-dirty');
            btn.innerHTML = '💾 Guardar correcciones * (Cambios pendientes)';
        }}
    }}

    document.querySelectorAll('#review-form input, #review-form textarea, #review-form select').forEach(el => {{
        el.addEventListener('input', marcarCambiosPendientes);
        el.addEventListener('change', marcarCambiosPendientes);
    }});
    </script>'''
    return _layout("Revisión de Tests", body)


def _render_tarjeta_estado_test(info: dict | None) -> str:
    """Tarjeta de monitoreo en vivo en /tests. Solo se llama mientras el
    test esta realmente en curso (ver _obtener_estado_test_activo) - en
    cuanto termina, deja de mostrarse solo, sin intervencion del usuario."""
    if not info:
        return ""
    jid = html.escape(str(info.get("job_id") or ""))
    st = info.get("estado", "")
    titulo = html.escape(str(info.get("titulo_doc") or info.get("asignatura") or "Test Evaluativo"))
    asignatura = html.escape(str(info.get("asignatura") or ""))
    mensaje = html.escape(str(info.get("mensaje") or ""))
    pct = int(info.get("progreso_porcentaje") or 0)
    total = int(info.get("total") or 0)
    exit = int(info.get("exitosos") or 0)
    fall = int(info.get("fallidos") or 0)

    if st == "esperando_asignatura":
        clase_card = "live-card--waiting"
        badge = '<span class="badge-dinamico badge-dinamico--error">⚠️ Selección requerida</span>'
        icono = "⚠️"
    else:
        clase_card = "live-card--running"
        badge = f'<span class="badge-dinamico badge-dinamico--proceso">⏳ En proceso ({pct}%)</span>'
        icono = "🔄"

    asig_html = f' · Asignatura: <strong>{asignatura}</strong>' if asignatura else ''

    return f'''
    <section id="card-estado-test-activo" class="panel live-card {clase_card}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px;margin-bottom:12px;">
            <div style="display:flex;gap:12px;align-items:center;">
                <span style="font-size:26px;">{icono}</span>
                <div>
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                        <h3>Cargue de Test en PRIZMA</h3>
                        <span id="card-badge-estado">{badge}</span>
                    </div>
                    <p>Documento: <strong>{titulo}</strong>{asig_html}</p>
                </div>
            </div>
            <a href="/tests/{jid}/estado-prizma" class="boton" style="text-decoration:none;padding:10px 18px;font-size:13px;">
                ⚡ Ver monitor en vivo ➔
            </a>
        </div>

        <div style="margin:12px 0 8px;">
            <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px;font-weight:600;">
                <span id="card-txt-avance" class="muted">{exit} de {total} tests guardados exitosamente</span>
                <span id="card-txt-pct" style="color:#5548e8;font-weight:800;">{pct}%</span>
            </div>
            <div class="progress-track">
                <div id="card-barra-progreso" class="progress-fill" style="width:{pct}%;"></div>
            </div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-top:10px;flex-wrap:wrap;gap:8px;">
            <span id="card-mensaje" class="muted" style="font-style:italic;">💬 {mensaje}</span>
            <span id="card-stats" class="muted" style="font-weight:600;">Exitosos: {exit} · Fallidos: {fall} · Total: {total}</span>
        </div>
    </section>
    '''
