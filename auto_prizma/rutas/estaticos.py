"""Logo, hoja de estilos responsive y script del tema claro/oscuro.
"""

from fastapi.responses import (
    Response,
    FileResponse,
)

from auto_prizma.aplicacion import app
from auto_prizma.config import LOGO_PATH


# Se carga DESPUES del <style> de cada pagina, por eso puede corregir
# lo que traigan los estilos propios sin tener que tocarlos uno por uno.
CSS_RESPONSIVE = r"""
/* ---------- base ---------- */
html { -webkit-text-size-adjust: 100%; }
img, svg, video { max-width: 100%; height: auto; }
* { min-width: 0; }

/* ---------- pantallas medianas y telefonos ---------- */
@media (max-width: 1050px) {

  .app { grid-template-columns: 1fr !important; }

  /* El menu lateral pasa a ser una barra superior.
     Antes simplemente se ocultaba y en el telefono no habia
     forma de ir a Historial, Reportes ni Salir. */
  .sidebar {
    display: flex !important;
    position: sticky !important;
    top: 0;
    z-index: 40;
    height: auto !important;
    min-height: 0 !important;
    flex-direction: column !important;
    gap: 10px;
    padding: 12px 14px !important;
    border-right: 0 !important;
    border-bottom: 1px solid #e5e7ef;
    background: #fff;
  }

  .sidebar .marca { margin-bottom: 0 !important; }
  .sidebar .marca span { display: none !important; }
  .sidebar .marca strong { font-size: 16px !important; }
  .sidebar .logo {
    width: 36px !important;
    height: 36px !important;
    border-radius: 10px !important;
    flex: 0 0 36px;
  }
  .sidebar .logo svg { width: 23px !important; height: 23px !important; }

  .sidebar .nav {
    display: flex !important;
    flex-direction: row !important;
    gap: 6px !important;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-bottom: 2px;
  }
  .sidebar .nav::-webkit-scrollbar { display: none; }

  .sidebar .nav-item {
    padding: 10px 13px !important;
    font-size: 13px !important;
    white-space: nowrap;
    flex: 0 0 auto;
  }

  /* Version compacta: se ve el punto + "Servicio activo", sin los
     chips de Navegador/Conexion, para que quepa en la barra superior
     en vez de desaparecer del todo. */
  .sidebar .estado-servicio {
    margin-top: 0 !important;
    margin-left: auto !important;
    border: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    flex: 0 0 auto;
  }
  .sidebar .estado-servicio .servicio-linea { margin-bottom: 0 !important; white-space: nowrap; }
  .sidebar .estado-servicio .servicio-mini { display: none !important; }

  .contenido { padding: 18px 16px 32px !important; }

  /* Cualquier rejilla de dos o mas columnas pasa a una sola. */
  .layout-inicio,
  .revision-grid,
  .carga-card,
  .zona,
  .herramientas,
  .grid-archivos,
  .grid-tipos { grid-template-columns: 1fr !important; }

  .accion-bloque { border-left: 0 !important; padding-left: 0 !important; }
}

/* ---------- telefonos ---------- */
@media (max-width: 700px) {

  .contenido { padding: 14px 12px 28px !important; }

  .panel-principal,
  .tabla-panel,
  .credenciales-panel,
  .panel,
  .vacio,
  .carga-card { padding: 16px !important; border-radius: 14px !important; }

  .vacio { padding: 30px 18px !important; }

  h1 { font-size: 21px !important; line-height: 1.25; }
  h2 { font-size: 17px !important; }

  .cabecera,
  .cabecera-top,
  .cabecera-linea {
    flex-direction: column !important;
    align-items: flex-start !important;
    gap: 12px;
  }

  .resumen-grid,
  .numeros,
  .metricas { grid-template-columns: repeat(2, 1fr) !important; }

  /* Tarjeta de conexion con Google: el boton baja y ocupa el ancho. */
  .google-conexion {
    flex-direction: column !important;
    align-items: flex-start !important;
    gap: 12px;
  }
  .google-conexion .google-boton,
  .google-boton {
    width: 100% !important;
    text-align: center !important;
    justify-content: center !important;
  }

  /* Botones y enlaces de accion a lo ancho, mas facil de tocar. */
  .boton,
  .boton-secundario,
  button[type="submit"],
  .accion-bloque a {
    width: 100% !important;
    justify-content: center !important;
    text-align: center !important;
    padding: 14px 16px !important;
  }

  /* 16px evita que iOS haga zoom al enfocar un campo. */
  input, select, textarea { font-size: 16px !important; }
  .campo-moderno input { padding: 12px 0 !important; }

  /* Las tablas anchas se deslizan en vez de romper la pantalla. */
  table {
    display: block !important;
    width: 100% !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
    white-space: nowrap;
  }

  /* Nombres largos de curso o de archivo no desbordan. */
  .curso-texto h2,
  .curso-texto p { white-space: normal !important; }

  td, th { word-break: break-word; }
}

/* ---------- pantallas muy angostas ---------- */
@media (max-width: 420px) {
  .resumen-grid,
  .numeros,
  .metricas { grid-template-columns: 1fr !important; }

  .contenido { padding: 12px 10px 24px !important; }
  .sidebar .nav-item { padding: 9px 11px !important; font-size: 12px !important; }
}

.logo-imagen { width:100% !important; height:100% !important; object-fit:contain !important; display:block !important; }

/* ---------- tema oscuro ---------- */
html[data-theme="dark"] {
  color-scheme: dark;
  background: #0b1020;
}
html[data-theme="dark"] body { background: #0b1020 !important; color: #e5e7eb !important; }
html[data-theme="dark"] .sidebar,
html[data-theme="dark"] .panel,
html[data-theme="dark"] .panel-principal,
html[data-theme="dark"] .tabla-panel,
html[data-theme="dark"] .credenciales-panel,
html[data-theme="dark"] .carga-card,
html[data-theme="dark"] .vacio,
html[data-theme="dark"] .caja,
html[data-theme="dark"] .estado-servicio,
html[data-theme="dark"] .google-conexion,
html[data-theme="dark"] .nota,
html[data-theme="dark"] .resumen-card,
html[data-theme="dark"] .seleccion-tipo-card {
  background: #111827 !important;
  color: #e5e7eb !important;
  border-color: #263244 !important;
  box-shadow: none !important;
}
html[data-theme="dark"] h1,
html[data-theme="dark"] h2,
html[data-theme="dark"] h3,
html[data-theme="dark"] strong,
html[data-theme="dark"] label,
html[data-theme="dark"] th,
html[data-theme="dark"] td { color: #f3f4f6 !important; }
html[data-theme="dark"] p,
html[data-theme="dark"] span,
html[data-theme="dark"] small,
html[data-theme="dark"] .sub,
html[data-theme="dark"] .marca span,
html[data-theme="dark"] .curso-texto p { color: #aeb9ca !important; }
html[data-theme="dark"] .nav-item { color: #cbd5e1 !important; }
html[data-theme="dark"] .nav-item:hover,
html[data-theme="dark"] .nav-item.activo { background: #1d2540 !important; color: #c7d2fe !important; }
html[data-theme="dark"] input,
html[data-theme="dark"] select,
html[data-theme="dark"] textarea,
html[data-theme="dark"] .campo-moderno {
  background: #0f172a !important;
  color: #f3f4f6 !important;
  border-color: #334155 !important;
}
html[data-theme="dark"] input::placeholder,
html[data-theme="dark"] textarea::placeholder { color: #64748b !important; }
html[data-theme="dark"] table,
html[data-theme="dark"] thead,
html[data-theme="dark"] tbody,
html[data-theme="dark"] tr { background: transparent !important; }
html[data-theme="dark"] th { background: #172033 !important; border-color: #263244 !important; }
html[data-theme="dark"] td { border-color: #263244 !important; }
html[data-theme="dark"] .caja-seguridad,
html[data-theme="dark"] .alerta,
html[data-theme="dark"] .error { background: #2a1a1a !important; border-color: #633 !important; }
html[data-theme="dark"] .boton-secundario { background: #172033 !important; color: #dbe4f0 !important; border-color: #334155 !important; }
html[data-theme="dark"] .contador,
html[data-theme="dark"] .chip,
html[data-theme="dark"] .estado-chip { background: #1e293b !important; color: #cbd5e1 !important; }
html[data-theme="dark"] .sidebar { border-color: #263244 !important; }
html[data-theme="dark"] .filtro-recurso-item {
  background: #111827 !important;
  border-color: #334155 !important;
}
html[data-theme="dark"] .filtro-recurso-item:hover {
  background: #172033 !important;
  border-color: #6d5dfc !important;
}
html[data-theme="dark"] .filtro-recurso-item:has(input:checked) {
  background: #1d2540 !important;
  border-color: #7c6ff0 !important;
}
html[data-theme="dark"] .filtro-recurso-texto strong {
  color: #f8fafc !important;
}
html[data-theme="dark"] .filtro-recurso-texto small {
  color: #aeb9ca !important;
}

/* Inicio: evitar fondos claros con texto claro en modo oscuro. */
html[data-theme="dark"] .encabezado-pagina,
html[data-theme="dark"] .selector-modo-matriz label,
html[data-theme="dark"] .tarjeta-archivo,
html[data-theme="dark"] .tarjeta-tipo,
html[data-theme="dark"] .caja-datos-academicos,
html[data-theme="dark"] .selector-archivo {
  background: #111827 !important;
  color: #e5e7eb !important;
  border-color: #334155 !important;
  box-shadow: none !important;
}
html[data-theme="dark"] .selector-modo-matriz label:hover,
html[data-theme="dark"] .tarjeta-archivo:hover,
html[data-theme="dark"] .tarjeta-archivo.arrastrando,
html[data-theme="dark"] .tarjeta-tipo:hover {
  background: #172033 !important;
  border-color: #6d5dfc !important;
}
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-verde,
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-azul,
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-morado,
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-naranja {
  background: #172033 !important;
}
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-verde { border-color: #2fbf7f !important; }
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-azul { border-color: #4b9ee8 !important; }
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-morado { border-color: #8b7cf6 !important; }
html[data-theme="dark"] .tarjeta-tipo:has(input:checked).tipo-naranja { border-color: #f0a83c !important; }
html[data-theme="dark"] .selector-modo-matriz label:has(input:checked) {
  background: #172033 !important;
  border-color: #6d5dfc !important;
}
html[data-theme="dark"] #bloque-test .selector-modo-matriz label:has(input:checked) {
  border-color: #f0a83c !important;
}
html[data-theme="dark"] .archivo-cabecera strong,
html[data-theme="dark"] .tarjeta-tipo strong {
  color: #f8fafc !important;
}
html[data-theme="dark"] .archivo-cabecera span,
html[data-theme="dark"] .tarjeta-tipo small,
html[data-theme="dark"] .nombre-archivo {
  color: #aeb9ca !important;
}
html[data-theme="dark"] .boton-selector {
  background: #5b48e8 !important;
  color: #ffffff !important;
}
html[data-theme="dark"] .numero-seccion {
  background: #26204d !important;
  color: #c4b5fd !important;
}


/* Cargue en progreso: evitar fondos claros con texto claro en modo oscuro. */
html[data-theme="dark"] .lista-actividades,
html[data-theme="dark"] .actividad-progreso,
html[data-theme="dark"] .estado-panel .estado-caja {
  background: #111827 !important;
  color: #e5e7eb !important;
  border-color: #263244 !important;
}
html[data-theme="dark"] .actividad-progreso {
  border-bottom-color: #263244 !important;
}
html[data-theme="dark"] .actividad-progreso.actividad-procesando {
  background: #1d1b36 !important;
  box-shadow: inset 3px 0 0 #7c6ff0 !important;
}
html[data-theme="dark"] .actividad-progreso.actividad-ok {
  background: #10251d !important;
}
html[data-theme="dark"] .actividad-progreso.actividad-error-fila {
  background: #2a1719 !important;
}
html[data-theme="dark"] .actividad-nombre,
html[data-theme="dark"] .estado-caja strong,
html[data-theme="dark"] .leyenda div {
  color: #e5e7eb !important;
}
html[data-theme="dark"] .estado-caja span {
  color: #aeb9ca !important;
}

.tema-toggle {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  width: 42px;
  height: 42px;
  border: 1px solid #d0d5dd;
  border-radius: 12px;
  background: #ffffff;
  color: #344054;
  display: grid;
  place-items: center;
  font-size: 18px;
  cursor: pointer;
  box-shadow: 0 8px 22px rgba(16,24,40,.10);
  transition: transform .15s ease, background .2s ease, color .2s ease;
}
.tema-toggle:hover { transform: translateY(-1px); }
html[data-theme="dark"] .tema-toggle {
  background: #172033;
  color: #f8fafc;
  border-color: #334155;
  box-shadow: 0 8px 24px rgba(0,0,0,.28);
}
@media (max-width: 700px) {
  .tema-toggle { top: 10px; right: 10px; width: 38px; height: 38px; border-radius: 10px; }
}

/* ---------- impresion ---------- */
@media print {
  .sidebar, .nav, .boton, .boton-secundario, .tema-toggle { display: none !important; }
  .app { grid-template-columns: 1fr !important; }
}
"""


@app.get("/favicon.ico")
@app.get("/auto-prizma-logo.png")
def auto_prizma_logo():
    return FileResponse(
        LOGO_PATH,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/estilos-responsive.css")
def estilos_responsive():
    return Response(
        content=CSS_RESPONSIVE,
        media_type="text/css",
        headers={"Cache-Control": "public, max-age=300"},
    )


JS_TEMA = r"""
(function () {
  var CLAVE = "autoPrizmaTema";

  function leerTema() {
    try {
      return localStorage.getItem(CLAVE) === "dark" ? "dark" : "light";
    } catch (_) {
      return "light";
    }
  }

  function guardarTema(tema) {
    try { localStorage.setItem(CLAVE, tema); } catch (_) {}
  }

  function aplicarTema(tema) {
    document.documentElement.setAttribute("data-theme", tema);
    var boton = document.querySelector(".tema-toggle");
    if (boton) {
      var oscuro = tema === "dark";
      boton.textContent = oscuro ? "☀️" : "🌙";
      boton.title = oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro";
      boton.setAttribute("aria-label", boton.title);
    }
  }

  aplicarTema(leerTema());

  function instalarBoton() {
    if (!document.body || document.querySelector(".tema-toggle")) return;
    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "tema-toggle";
    boton.addEventListener("click", function () {
      var actual = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      var siguiente = actual === "dark" ? "light" : "dark";
      guardarTema(siguiente);
      aplicarTema(siguiente);
    });
    document.body.appendChild(boton);
    aplicarTema(leerTema());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", instalarBoton, { once: true });
  } else {
    instalarBoton();
  }
})();
"""


@app.get("/tema.js")
def tema_javascript():
    return Response(
        content=JS_TEMA,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )
