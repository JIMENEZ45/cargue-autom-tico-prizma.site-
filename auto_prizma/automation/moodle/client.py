"""Cliente visible de Playwright para publicar recursos en Moodle."""

import os
import re
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from auto_prizma.domain.moodle_resources import BLOCK_LABELS, normalize_key


DESTINATION_NAMES = BLOCK_LABELS
NEXT_BLOCK = {"digital": "audiovisual", "audiovisual": "challenge", "challenge": None}
INSERTION_BOUNDARY = {
    "digital": "button[data-action=\"open-chooser\"][aria-label*=\"{label}\"]",
    "audiovisual": "button[data-action=\"open-chooser\"][aria-label*=\"{label}\"]",
}


class MoodleClient:
    def __init__(self, context, page):
        self.context = context
        self.page = page
        self.current_week = ""
        self.current_section_id = ""
        self.unavailable_destination_blocks = {}

    @classmethod
    def launch(cls, course_url, profile_path):
        os.makedirs(profile_path, exist_ok=True)
        playwright = sync_playwright().start()
        context = None
        try:
            context = playwright.chromium.launch_persistent_context(
                profile_path,
                headless=False,
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(course_url, wait_until="domcontentloaded")
            client = cls(context, page)
            client._playwright = playwright
            client._wait_for_manual_login()
            client.ensure_edit_mode()
            return client
        except Exception:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            playwright.stop()
            raise

    def _wait_for_manual_login(self):
        self.page.get_by_text("Curso", exact=True).wait_for(timeout=120_000)

    def _edit_mode_toggle(self):
        toggle = self.page.locator('.editmode-switch-form input[name="setmode"], input[name="setmode"]').first
        if toggle.count():
            return toggle
        return self.page.get_by_role("checkbox", name=re.compile(r"Modo de edici[oó]n|Edit mode", re.I)).first

    def ensure_edit_mode(self):
        """Activa el interruptor «Modo de edición»: sin él Moodle no muestra «Añade actividad o recursos»."""
        toggle = self._edit_mode_toggle()
        try:
            toggle.wait_for(state="attached", timeout=15_000)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("No se encontró el interruptor «Modo de edición» en el curso de Moodle.") from exc
        if toggle.is_checked():
            return
        toggle.click()
        # Moodle envía el formulario y recarga la página con la edición activa.
        for _ in range(40):
            self.page.wait_for_timeout(500)
            try:
                self.page.wait_for_load_state("domcontentloaded")
                if self._edit_mode_toggle().is_checked():
                    self._wait_for_manual_login()
                    return
            except Exception:
                continue
        raise RuntimeError("Se pulsó «Modo de edición», pero Moodle no lo dejó activado.")

    def open_course(self, course_url):
        self.page.goto(course_url, wait_until="domcontentloaded")
        self._wait_for_manual_login()
        self.ensure_edit_mode()

    def _week_url(self, week):
        """Enlace de la semana (?section=N) tomado de cualquier enlace con ese nombre, aunque esté oculto.

        El índice lateral del curso tiene enlaces «Semana N» ocultos: hacer clic en ellos fallaba
        («element is not visible»); ir directo a su dirección no depende de que se vean.
        """
        try:
            return self.page.evaluate(
                """(name) => {
                  const norm = value => String(value || '').replace(/\\s+/g, ' ').trim();
                  for (const link of document.querySelectorAll('a[href*="section="]')) {
                    if (norm(link.textContent) === name) return link.href;
                  }
                  return '';
                }""",
                str(week).strip(),
            ) or ""
        except Exception:
            return ""

    def open_week(self, week):
        url = self._week_url(week)
        section = parse_qs(urlparse(url).query).get("section", [""])[0] if url else ""
        if section:
            self.page.goto(url, wait_until="domcontentloaded")
            try:
                self.page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                pass
            self.page.wait_for_timeout(250)
            self.current_week = str(week).strip()
            self.current_section_id = section
            return
        tab = self._visible_first(self.page.get_by_text(str(week).strip(), exact=True))
        href = ""
        try:
            href = tab.evaluate("element => (element.closest('a') || element).getAttribute('href')") or ""
        except Exception:
            pass
        section_from_tab = parse_qs(urlparse(href).query).get("section", [""])[0] if href else ""
        tab.click()
        # La pestaña es un enlace que recarga la página (?section=N). Hay que esperar a que cargue
        # la semana nueva: si se revisa antes, se lee la página anterior y el recurso se duplica.
        if section_from_tab:
            try:
                self.page.wait_for_url(
                    re.compile(r"[?&]section=" + re.escape(section_from_tab) + r"(?:[&#]|$)"),
                    timeout=30_000,
                    wait_until="domcontentloaded",
                )
            except PlaywrightTimeoutError:
                pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeoutError:
            pass
        self.page.wait_for_timeout(250)
        self.current_week = str(week).strip()
        self.current_section_id = parse_qs(urlparse(self.page.url).query).get("section", [""])[0] or section_from_tab

    def _wait_for_week_content(self):
        """Espera a que la semana muestre sus bloques antes de buscar recursos ya cargados."""
        labels = "|".join(re.escape(label) for label in DESTINATION_NAMES.values())
        try:
            self.page.get_by_text(re.compile(r"^(?:" + labels + r")$")).first.wait_for(state="visible", timeout=15_000)
        except Exception:
            pass
        self.page.wait_for_timeout(500)

    def _find_final_section_add_control(self):
        challenge = self.page.get_by_text("Reto Evaluativo", exact=True).last
        if challenge.count() > 0:
            challenge.scroll_into_view_if_needed()
            self.page.wait_for_timeout(1000)
        add = self.page.get_by_text(re.compile("Añade actividad o recursos", re.I)).last
        try:
            add.wait_for(state="visible", timeout=15_000)
            return add
        except Exception:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(1000)
            add = self.page.get_by_text(re.compile("Añade actividad o recursos", re.I)).last
            add.wait_for(state="visible", timeout=15_000)
            return add

    @staticmethod
    def _visible_first(locator):
        for index in range(locator.count()):
            candidate = locator.nth(index)
            try:
                if candidate.is_visible():
                    return candidate
            except Exception:
                continue
        candidate = locator.first
        candidate.wait_for(state="visible", timeout=15_000)
        return candidate

    def _label_visible(self, block, timeout_ms):
        locator = self.page.get_by_text(DESTINATION_NAMES[block], exact=True)
        for attempt in range(max(1, timeout_ms // 250)):
            for index in range(locator.count()):
                try:
                    if locator.nth(index).is_visible():
                        return True
                except Exception:
                    continue
            if attempt < timeout_ms // 250 - 1:
                self.page.wait_for_timeout(250)
        return False

    def _next_present_block(self, block):
        """Primera etiqueta siguiente que existe en la semana; None = usar el botón final de la semana.

        Si la etiqueta siguiente se borró por no usarse (p. ej. «Recurso educativo audiovisual»),
        el recurso se inserta antes de la que sigue, o al final de la semana.
        """
        candidate = NEXT_BLOCK[block]
        timeout_ms = 5_000
        while candidate:
            if self._label_visible(candidate, timeout_ms):
                return candidate
            timeout_ms = 250
            candidate = NEXT_BLOCK[candidate]
        return None

    def wait_for_week_content(self):
        self._wait_for_week_content()

    def delete_unused_label(self, block):
        """Borra la etiqueta del bloque en la semana abierta: ⋮ → «Borrar» → confirmar «Borrar».

        Devuelve "deleted" o "missing" (no estaba). Solo borra módulos de tipo etiqueta
        (`modtype_label`) cuyo texto es el nombre del bloque, y confirma únicamente si el
        diálogo nombra esa etiqueta.
        """
        label = DESTINATION_NAMES[block]
        cards = self.page.locator('[id^="module-"]:visible').evaluate_all(
            """(elements, label) => {
              const norm = value => String(value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/\\s+/g, ' ').trim();
              const wanted = norm(label);
              return elements.map(element => ({
                id: element.id,
                isLabel: element.classList.contains('modtype_label'),
                text: norm(element.innerText || element.textContent || ''),
              })).filter(card => card.text.includes(wanted));
            }""",
            label,
        )
        wanted = normalize_key(label)
        labels = [card for card in cards if card["isLabel"]]
        if not labels:
            # Sin clase modtype_label: solo vale una tarjeta corta cuyo texto es casi solo el nombre del bloque.
            labels = [card for card in cards if len(card["text"]) <= len(wanted) + 25]
        if not labels:
            return "missing"
        if len(labels) > 1:
            raise RuntimeError(f"Hay {len(labels)} etiquetas «{label}» en {self.current_week}; no se borró ninguna.")
        card = self.page.locator(f'[id="{labels[0]["id"]}"]')
        card.scroll_into_view_if_needed()
        toggle = card.locator(
            '.action-menu [data-toggle="dropdown"], .action-menu [data-bs-toggle="dropdown"], '
            '.action-menu .dropdown-toggle, [data-bs-toggle="dropdown"], [data-toggle="dropdown"], .dropdown-toggle'
        ).first
        toggle.click()
        delete = card.locator('.dropdown-menu.show').get_by_text("Borrar", exact=True).first
        if not delete.count():
            delete = self.page.locator('.dropdown-menu.show').get_by_text("Borrar", exact=True).first
        delete.wait_for(state="visible", timeout=10_000)
        delete.click()
        dialog = self.page.get_by_role("dialog").filter(has_text=re.compile(r"Eliminar", re.I)).last
        dialog.wait_for(state="visible", timeout=15_000)
        dialog_text = self._dialog_text_with_target(dialog)
        if not self._dialog_names_card(dialog_text, label, labels[0]["text"]):
            dialog.get_by_role("button", name=re.compile(r"^Cancelar$", re.I)).first.click()
            shown = re.sub(r"\s+", " ", dialog_text).strip()[:200]
            raise RuntimeError(
                f"El diálogo de borrado no nombraba «{label}»; se canceló sin borrar. Texto del diálogo: {shown}"
            )
        dialog.get_by_role("button", name=re.compile(r"^Borrar$", re.I)).first.click()
        card.wait_for(state="detached", timeout=30_000)
        return "deleted"

    def _dialog_text_with_target(self, dialog):
        """Texto del diálogo de borrado cuando ya cargó a quién elimina (Moodle lo rellena un instante después)."""
        text = ""
        for _ in range(20):
            text = dialog.inner_text()
            if re.search(r"(?:eliminar[aá]|delete)\s+\S", text, re.I):
                return text
            self.page.wait_for_timeout(500)
        return text

    @staticmethod
    def _dialog_names_card(dialog_text, label, card_text):
        """True si el diálogo nombra la etiqueta o el mismo texto de la tarjeta cuyo menú se abrió.

        Moodle muestra el nombre interno de la etiqueta, que puede diferir del texto visible
        (mayúsculas, espacios o texto extra); se compara normalizado en ambos sentidos.
        """
        dialog_key = normalize_key(dialog_text)
        if normalize_key(label) in dialog_key:
            return True
        match = re.search(r"(?:eliminar[aá]|delete)\s+(.+?)(?:\s+y\s+cualquier|\s+and\s+any|[.?]|$)", dialog_text, re.I | re.S)
        target = normalize_key(match.group(1)) if match else ""
        card_key = normalize_key(card_text)
        return len(target) >= 4 and (target in card_key or card_key in target)

    def begin_add_resource(self, block):
        block_key = (self.current_week, block)
        if block_key in self.unavailable_destination_blocks:
            error = RuntimeError(self.unavailable_destination_blocks[block_key])
            error.code = "DESTINATION_BLOCK_UNAVAILABLE"
            raise error
        next_block = self._next_present_block(block)
        if next_block:
            label = DESTINATION_NAMES[next_block]
            selector = INSERTION_BOUNDARY[block].format(label=label)
            if self.current_section_id:
                selector = selector.replace("[aria-label", f'[data-sectionid="{self.current_section_id}"][aria-label')
            button = self.page.locator(selector).first
        else:
            if self.current_section_id:
                button = self.page.locator(
                    f'button[data-action="open-chooser"][data-sectionid="{self.current_section_id}"]'
                    f'[data-sectionreturnid="{self.current_section_id}"]'
                ).last
            else:
                button = self.page.locator('[data-action="open-chooser"], .addresourcemod a, .addresourcemod button, button.activity-add, a.activity-add, .section-modchooser, .section-modchooser-link').last
            if button.count() == 0:
                if self.current_section_id:
                    button = self.page.locator(
                        f'button[data-action="open-chooser"][data-sectionid="{self.current_section_id}"]'
                    ).last
            if button.count() == 0:
                button = self.page.locator("button, a").filter(has_text=re.compile("Añade actividad o recursos", re.I)).last
            if button.count() == 0:
                button = self._find_final_section_add_control()
        if button.count() == 0:
            controls = self.page.locator('button, a, [role="button"], input[type="button"], input[type="submit"]').evaluate_all(
                """elements => elements.map(element => ({
                  tag: element.tagName.toLowerCase(),
                  text: (element.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 100),
                  aria: element.getAttribute('aria-label'),
                  className: String(element.className || '').slice(0, 160)
                })).filter(control => /a.ad|actividad|recurso|chooser|section/i.test(`${control.text} ${control.aria} ${control.className}`)).slice(-25)"""
            )
            error = RuntimeError(
                f"El bloque {DESTINATION_NAMES[block]} de {self.current_week or 'la semana actual'} "
                + "no tiene el control para añadir recursos. Controles encontrados: "
                + str(controls)
            )
            error.code = "DESTINATION_BLOCK_UNAVAILABLE"
            self.unavailable_destination_blocks[block_key] = str(error)
            raise error
        button.scroll_into_view_if_needed()
        button.evaluate("element => element.click()")

    def find_existing_resource(self, title, known_resource_id="", file_path=""):
        self._wait_for_week_content()
        if str(known_resource_id).isdigit():
            known = self.page.locator(f'#module-{known_resource_id}:visible, [data-cmid="{known_resource_id}"]:visible').first
            if known.count():
                return str(known_resource_id)
        keys = [normalize_key(title), normalize_key(os.path.splitext(os.path.basename(file_path))[0])]
        keys = [key for key in keys if len(key) >= 8]
        cards = self.page.locator('[id^="module-"]:visible, [data-cmid]:visible')
        for index in range(cards.count()):
            card = cards.nth(index)
            text = card.evaluate("element => [element.innerText || element.textContent || '', ...Array.from(element.querySelectorAll('[title], [aria-label], a[href]')).flatMap(item => [item.getAttribute('title') || '', item.getAttribute('aria-label') || '', item.getAttribute('href') || ''])].join(' ')")
            normalized = normalize_key(text)
            if any(key in normalized or (min(len(normalized), len(key)) >= 18 and (normalized.startswith(key) or key.startswith(normalized))) for key in keys):
                module_id = card.get_attribute("data-cmid") or ""
                if not module_id:
                    match = re.match(r"^module-(.+)$", card.get_attribute("id") or "")
                    module_id = match.group(1) if match else ""
                return module_id or "verified-existing-" + str(title)
        try:
            visible_text = normalize_key(self.page.locator("body").inner_text())
            if any(key in visible_text for key in keys):
                return "verified-existing-" + str(title)
        except Exception:
            pass
        return None

    def _open_resource_type(self, module):
        dialog = self.page.get_by_role("dialog")
        name = "Archivo" if module == "file" else "Contenido interactivo"
        dialog.get_by_text(name, exact=True).first.wait_for(state="visible", timeout=15_000)
        dialog.get_by_text(name, exact=True).first.click()

    def _fill_name(self, title):
        field = self.page.locator("#id_name").first
        field.wait_for(state="visible", timeout=30_000)
        field.fill(title)

    def _upload_file(self, path):
        field = self.page.locator("#fitem_id_files input[type=file], #id_files input[type=file]").first
        if field.count():
            field.set_input_files(path)
            return
        drop = self.page.locator("#fitem_id_files .dndupload-target, #id_files .dndupload-target").first
        if not drop.count():
            raise RuntimeError("No se encontró el selector para subir el archivo PDF en Moodle.")
        with open(path, "rb") as source:
            file_bytes = source.read()
        drop.evaluate(
            """(element, payload) => {
              const transfer = new DataTransfer();
              transfer.items.add(new File([new Uint8Array(payload.bytes)], payload.name));
              element.dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true, cancelable: true }));
            }""",
            {"bytes": list(file_bytes), "name": os.path.basename(path)},
        )

    def _configure_embedded_display(self):
        display = self.page.get_by_label("Mostrar", exact=True)
        if not display.count():
            raise RuntimeError("No se encontró la opción Mostrar del recurso.")
        if not display.is_visible():
            self.page.locator('a[aria-controls="id_optionssectioncontainer"]').first.click()
        display.select_option(label="Incrustar")
        for label in ("Mostrar tipo", "Mostrar descripción del recurso"):
            checkbox = self.page.get_by_label(label, exact=True)
            if checkbox.count() and checkbox.is_checked():
                checkbox.uncheck()

    def _h5p_editor_frame(self):
        for _ in range(40):
            for frame in [self.page, *self.page.frames]:
                try:
                    create = frame.get_by_text("Create Content", exact=True).first
                    upload = frame.get_by_text("Upload", exact=True).first
                    if create.is_visible() and upload.is_visible():
                        return frame
                    prompt = frame.get_by_text(re.compile("Upload an H5P file", re.I)).first
                    if prompt.is_visible() and upload.is_visible():
                        return frame
                except Exception:
                    continue
            self.page.wait_for_timeout(500)
        diagnostics = []
        for index, frame in enumerate([self.page, *self.page.frames]):
            try:
                summary = re.sub(r"\s+", " ", frame.locator("body").inner_text())[:180]
                diagnostics.append(f"frame{index}: {summary}")
            except Exception:
                continue
        error = RuntimeError(
            "No se detectó el editor H5P activo con las opciones Create Content y Upload. "
            + " | ".join(diagnostics)
        )
        error.code = "H5P_EDITOR_NOT_READY"
        raise error

    def _select_h5p_upload_mode(self, editor):
        # Igual que MOODLE (selectH5pUploadMode): clic en la pestaña visible "Upload" del editor.
        # Marcar el radio oculto value="upload" no cambia la pestaña y el selector de archivo no aparece.
        editor.locator("text=Create Content").first.wait_for(state="visible", timeout=15_000)
        editor.evaluate(
            """() => {
              for (const element of document.querySelectorAll('button,div,span,a,label')) {
                if (element.textContent.trim() === 'Upload') {
                  const rect = element.getBoundingClientRect();
                  if (rect.width < 250 && rect.width > 20) {
                    element.click();
                    return;
                  }
                }
              }
              document.querySelector('input[value="upload"]')?.closest('label')?.click();
            }"""
        )

        prompt = editor.get_by_text(re.compile("Upload an H5P file", re.I)).first
        try:
            prompt.wait_for(state="visible", timeout=15_000)
        except Exception as exc:
            diagnostics = []
            for frame_index, frame in enumerate([self.page, *self.page.frames]):
                try:
                    summary = re.sub(r"\s+", " ", frame.locator("body").inner_text())[:180]
                    diagnostics.append(f"frame{frame_index}: {summary}")
                except Exception:
                    continue
            raise RuntimeError(
                "No se activó Upload en el editor H5P; no apareció el selector de archivo. "
                + " | ".join(diagnostics)
            ) from exc

    def _assert_h5p_accepted(self, editor, path):
        for attempt in range(6):
            error = self._h5p_validation_error(path)
            if error:
                failure = ValueError(error)
                failure.code = "H5P_PACKAGE_VALIDATION_FAILED"
                raise failure
            if attempt < 5:
                editor.wait_for_timeout(500)

    def _upload_h5p_file(self, editor, path):
        # Igual que MOODLE (uploadH5pFile): el .h5p va directo al input del editor, sin diálogo de archivos.
        file_input = editor.locator('input[type="file"]').first
        file_input.wait_for(state="attached", timeout=15_000)
        file_input.set_input_files(path)
        self._assert_h5p_accepted(editor, path)
        use_button = editor.get_by_role("button", name=re.compile(r"^Use$")).first
        try:
            use_button.wait_for(state="visible", timeout=20_000)
            use_button.click()
        except Exception:
            try:
                editor.locator("text=Use").first.click()
            except Exception:
                pass
        self._assert_h5p_accepted(editor, path)
        try:
            editor.get_by_text(re.compile("successfully uploaded|cargado correctamente", re.I)).first.wait_for(
                state="visible",
                timeout=10_000,
            )
        except Exception:
            pass
        editor.wait_for_timeout(3000)

    def _upload_h5p(self, title, path):
        try:
            editor = self._h5p_editor_frame()
            self._select_h5p_upload_mode(editor)
        except Exception as exc:
            if re.search(r"Create Content|editor H5P activo", str(exc), re.I):
                error = RuntimeError(f"Editor H5P no disponible para {title}: {exc}")
                error.code = "H5P_EDITOR_NOT_READY"
                raise error from exc
            raise
        try:
            self._upload_h5p_file(editor, path)
        except Exception as exc:
            if getattr(exc, "code", "") == "H5P_PACKAGE_VALIDATION_FAILED":
                validation = exc
            else:
                message = self._h5p_validation_error(path)
                validation = ValueError(message) if message else None
                if validation:
                    validation.code = "H5P_PACKAGE_VALIDATION_FAILED"
            if validation:
                self._cancel_h5p_form()
                raise validation from exc
            raise

    def _h5p_validation_error(self, path):
        text_parts = []
        for frame in [self.page, *self.page.frames]:
            try:
                text_parts.append(frame.locator("body").inner_text())
            except Exception:
                continue
        text = " ".join(text_parts)
        rejected = re.findall(r'(?:El archivo|The file)\s+"([^"]+)"\s+(?:no está permitido|is not allowed)', text, re.I)
        if re.search(r"H5P package validation failed|validación del paquete H5P falló", text, re.I) or rejected:
            names = ", ".join(rejected[:3]) or "el contenido del paquete"
            return f"Paquete H5P rechazado ({os.path.basename(path)}): Moodle no permitió {names}."
        return ""

    def _cancel_h5p_form(self):
        candidates = (
            self.page.get_by_role("button", name=re.compile(r"^Cancelar$", re.I)).last,
            self.page.get_by_role("link", name=re.compile(r"^Cancelar$", re.I)).last,
            self.page.locator('input[type="submit"][value="Cancelar"], button[name="cancel"], input[name="cancel"]').last,
            self.page.get_by_text("Cancelar", exact=True).last,
        )
        cancel = None
        for candidate in candidates:
            try:
                if candidate.count() and candidate.is_visible():
                    cancel = candidate
                    break
            except Exception:
                continue
        if not cancel:
            raise RuntimeError("Moodle rechazó el paquete H5P, pero no se encontró el botón Cancelar para descartar el formulario.")
        cancel.click()
        try:
            self.page.wait_for_url(
                re.compile(r"/course/view\.php"),
                timeout=30_000,
                wait_until="domcontentloaded",
            )
        except Exception:
            try:
                self.page.go_back(timeout=10_000, wait_until="domcontentloaded")
            except Exception:
                pass
            if not re.search(r"/course/view\.php", self.page.url):
                raise RuntimeError("Se pulsó Cancelar, pero Moodle no regresó al curso; el formulario H5P quedó pendiente de cerrar.")

    def _verify_published(self, title, module, previous_count):
        cards = self.page.locator('[id^="module-"]')
        cards.first.wait_for(state="visible", timeout=60_000)
        card = cards.filter(has_text=title).last
        try:
            card.wait_for(state="visible", timeout=5_000)
            module_id = card.get_attribute("data-cmid") or ""
            if not module_id:
                match = re.match(r"^module-(.+)$", card.get_attribute("id") or "")
                module_id = match.group(1) if match else ""
            if module_id:
                return module_id
        except Exception:
            # Moodle puede mostrar el título interno del H5P, distinto al de la matriz.
            pass
        return f"verified-{module}-{previous_count + 1}"

    def _save_and_verify(self, title, module, previous_count, on_before_save=None):
        notification = self.page.locator('input[name="sendcontentchangenotification"], input[name="coursecontentnotification"]').first
        if notification.count() and notification.is_checked():
            notification.uncheck()
        else:
            notification = self.page.get_by_role("checkbox", name=re.compile("Enviar notificación", re.I))
            if notification.count() and notification.first.is_checked():
                notification.first.uncheck()
        save = self.page.get_by_role("button", name="Guardar cambios y regresar al curso")
        on_before_save and on_before_save()
        try:
            save.wait_for(state="visible", timeout=15_000)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(1000)
            save.click(timeout=15_000)
        except Exception as exc:
            footer = ""
            try:
                footer = self.page.locator("footer, .form-buttons, .form-actions").last.inner_text()
            except Exception:
                pass
            raise RuntimeError(
                "No se pudo pulsar Guardar cambios y regresar al curso. "
                + "Pie del formulario: " + (footer or "no encontrado")
            ) from exc
        self.page.wait_for_url(
            re.compile(r"/course/view\.php"),
            timeout=60_000,
            wait_until="domcontentloaded",
        )
        self.page.wait_for_timeout(5000)
        return self._verify_published(title, module, previous_count)

    def publish(self, entry, on_before_save=None):
        previous_count = self.page.get_by_text(entry["title"], exact=True).count()
        destination = entry["destination"]
        self.begin_add_resource(destination["block"])
        self._open_resource_type(destination["module"])
        if destination["module"] == "file":
            self._fill_name(entry["title"])
            self._upload_file(entry["path"])
            self._configure_embedded_display()
        else:
            # Como en MOODLE: el H5P no lleva nombre manual (Moodle toma el título del paquete
            # y el campo #id_name no es visible, así que esperarlo agotaba los 30 s).
            self._upload_h5p(entry["title"], entry["path"])
        return self._save_and_verify(entry["title"], destination["module"], previous_count, on_before_save)

    def close(self):
        try:
            self.context.close()
        finally:
            playwright = getattr(self, "_playwright", None)
            if playwright:
                playwright.stop()
