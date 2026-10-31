"""La entrevista de «Nuevo proyecto» en el board (v1.3.0, cotejo-kf94so).

Seis preguntas en lenguaje llano con valores de ejemplo, la carpeta, el agente que Cotejo detectó
y «Ver lo que se le enviará a tu agente». «Preparar proyecto» valida con `inicio.validar` y
lanza con `enrutador.preparar.lanzar`; la lógica del formulario (Respuestas, carpeta sugerida) es
de `tareas/entrevista.py`, el prompt de `tareas/inicio.py`. Aquí solo se pinta.

Al lanzar, `preparar_proyecto` llama a `mostrar_preparando(estado)` y, cuando el agente vuelve,
`GLib.idle_add` llama a `preparacion_terminada(estado)`: los dos son de la pantalla Preparando
(`tareas/app/preparando.py`, cotejo-hiifrz).
"""

import os

from gi.repository import GLib, Gtk, Pango

from .. import entrevista, inicio
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .piezas import con_mano, etiquetar

ENTREVISTA = "entrevista"


class PestanaEntrevista:
    """El formulario, como una pantalla más de la pila (sin botón en el selector)."""

    # --- armar la pantalla ----------------------------------------------------------------------

    def crear_entrevista(self):
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)
        cuerpo.append(Gtk.Label(label="Inicio  ›  Nuevo proyecto", xalign=0, css_classes=["dato"]))
        cuerpo.append(Gtk.Label(label="Cuéntale a tu agente qué quieres construir", xalign=0,
                                wrap=True, css_classes=["inicio-titular"]))
        self.entrevista_avance = Gtk.ProgressBar(css_classes=["inicio-avance"])
        cuerpo.append(self.entrevista_avance)

        ej = entrevista.EJEMPLOS
        self.ent_que_es = self._pregunta(cuerpo, "1. ¿Qué quieres construir?",
                                         "En una frase, como se lo contarías a un amigo.",
                                         Gtk.Entry(placeholder_text=ej["que_es"], hexpand=True))
        self.ent_para_quien = self._pregunta(cuerpo, "2. ¿Quién la va a usar?", "",
                                             Gtk.Entry(placeholder_text=ej["para_quien"], hexpand=True))
        self.ent_que_hace = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=px(ESPACIADO_SM),
                                         bottom_margin=px(ESPACIADO_SM), left_margin=px(ESPACIADO_MD),
                                         right_margin=px(ESPACIADO_MD), css_classes=["entrevista-texto"])
        marco = Gtk.ScrolledWindow(child=self.ent_que_hace, min_content_height=px(84),
                                   hscrollbar_policy=Gtk.PolicyType.NEVER,
                                   css_classes=["entrevista-marco"])
        # Los ejemplos van en gris y no como respuesta: si no, «Preparar proyecto» sin tocar
        # nada prepararía el proyecto de ejemplo. Un TextView no tiene placeholder: va encima.
        self.ent_que_hace_ejemplo = Gtk.Label(label=ej["que_hace"], xalign=0, yalign=0,
                                              halign=Gtk.Align.START, valign=Gtk.Align.START,
                                              margin_top=px(ESPACIADO_SM), margin_start=px(ESPACIADO_MD),
                                              can_target=False, css_classes=["dim-label"])
        marco = Gtk.Overlay(child=marco)
        marco.add_overlay(self.ent_que_hace_ejemplo)
        self._pregunta(cuerpo, "3. ¿Qué tiene que hacer la primera versión?",
                       "Tres cosas como mucho, una por línea. Lo demás vendrá después.", marco)
        self.ent_donde = self._opciones(cuerpo, "4. ¿Dónde la van a usar?", "", entrevista.DONDE)
        self.ent_necesita = self._opciones(
            cuerpo, "5. ¿Qué más necesita?",
            "Marca lo que aplique. Con esto el agente elige la tecnología, sin preguntarte por ella.",
            entrevista.NECESITA)
        self.ent_fuera = self._pregunta(cuerpo, "6. ¿Qué dejamos para después? (opcional)", "",
                                        Gtk.Entry(placeholder_text=ej["fuera"], hexpand=True))

        # Carpeta y agente.
        self.ent_carpeta = Gtk.Entry(hexpand=True,
                                     placeholder_text=entrevista.carpeta_sugerida(ej["que_es"]))
        self.ent_carpeta_a_mano = False   # si la persona la escribe, deja de seguir a la pregunta 1
        self._pregunta(cuerpo, "Dónde se guarda",
                       "La carpeta del proyecto; si no existe, se crea.", self.ent_carpeta)
        self.ent_agentes = []            # nombres de cliente, en el orden del desplegable
        self.ent_agente = Gtk.DropDown(model=Gtk.StringList())
        self.ent_agente_pista = Gtk.Label(xalign=0, wrap=True, css_classes=["dato"])
        fila_agente = Gtk.Box(spacing=px(ESPACIADO_SM))
        fila_agente.append(Gtk.Label(label="Lo prepara", css_classes=["carta-descripcion"]))
        fila_agente.append(self.ent_agente)
        fila_agente.append(self.ent_agente_pista)
        cuerpo.append(fila_agente)
        # El modelo exacto del catálogo (`cotejo modelos`) para ese agente: sin elegir, el
        # que el agente tendría por defecto (cotejo-v5ywpr).
        self.ent_modelos = []            # `Nivel` del catálogo, en el orden del desplegable
        self.ent_modelo = Gtk.DropDown(model=Gtk.StringList())
        fila_modelo = Gtk.Box(spacing=px(ESPACIADO_SM))
        fila_modelo.append(Gtk.Label(label="Con qué modelo", css_classes=["carta-descripcion"]))
        fila_modelo.append(self.ent_modelo)
        fila_modelo.append(Gtk.Label(label="del catálogo de Cotejo", css_classes=["dato"]))
        cuerpo.append(fila_modelo)

        # Lo que se enviará, a la vista.
        self.ent_prompt = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                       wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                       css_classes=["entrevista-texto"])
        marco_prompt = Gtk.ScrolledWindow(child=self.ent_prompt, min_content_height=px(220),
                                          max_content_height=px(360),
                                          hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          css_classes=["entrevista-marco"])
        self.ent_ver = Gtk.Expander(label="Ver lo que se le enviará a tu agente", child=marco_prompt)
        cuerpo.append(self.ent_ver)

        self.ent_error = Gtk.Label(xalign=0, wrap=True, css_classes=["dato"], visible=False)
        cuerpo.append(self.ent_error)
        pie = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.END)
        cancelar = con_mano(Gtk.Button(label="Cancelar"))
        cancelar.connect("clicked", lambda *_: self.cancelar_entrevista())
        self.ent_preparar = con_mano(Gtk.Button(label="Preparar proyecto",
                                                css_classes=["suggested-action"]))
        etiquetar(self.ent_preparar, "Preparar proyecto")
        self.ent_preparar.connect("clicked", lambda *_: self.preparar_proyecto())
        pie.append(cancelar)
        pie.append(self.ent_preparar)
        cuerpo.append(pie)

        for entrada in (self.ent_que_es, self.ent_para_quien, self.ent_fuera, self.ent_carpeta):
            entrada.connect("changed", self._al_cambiar_entrevista)
        self.ent_que_es.connect("changed", self._seguir_nombre)
        self.ent_carpeta.connect("changed", self._carpeta_a_mano)
        self.ent_que_hace.get_buffer().connect("changed", self._al_cambiar_entrevista)
        self.ent_agente.connect("notify::selected", self._al_cambiar_agente)
        self.ent_modelo.connect("notify::selected", self._al_cambiar_entrevista)

        ancho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER)
        ancho.set_size_request(px(640), -1)
        ancho.append(cuerpo)
        return Gtk.ScrolledWindow(child=ancho, hexpand=True, vexpand=True,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER, css_classes=["inicio"])

    def _pregunta(self, cuerpo, titulo, ayuda, campo):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS))
        caja.append(Gtk.Label(label=titulo, xalign=0, css_classes=["carta-nombre"]))
        if ayuda:
            caja.append(Gtk.Label(label=ayuda, xalign=0, wrap=True, css_classes=["carta-descripcion"]))
        caja.append(campo)
        cuerpo.append(caja)
        return campo

    def _opciones(self, cuerpo, titulo, ayuda, opciones):
        """Casillas (texto → Gtk.ToggleButton) en una fila que se parte; devuelve {texto: botón}."""
        flujo = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                            max_children_per_line=4, row_spacing=px(ESPACIADO_SM),
                            column_spacing=px(ESPACIADO_SM))
        botones = {}
        for texto, marcada in opciones:
            boton = con_mano(Gtk.ToggleButton(label=texto, active=marcada, css_classes=["pestana"]))
            boton.connect("toggled", self._al_cambiar_entrevista)
            botones[texto] = boton
            flujo.append(boton)
        self._pregunta(cuerpo, titulo, ayuda, flujo)
        return botones

    # --- leer y reaccionar ----------------------------------------------------------------------

    def _texto_de(self, vista):
        b = vista.get_buffer()
        return b.get_text(b.get_start_iter(), b.get_end_iter(), False)

    def agente_elegido(self):
        """El nombre del cliente elegido en el desplegable, o None si no hay ninguno instalado."""
        if not self.ent_agentes:
            return None
        return self.ent_agentes[min(self.ent_agente.get_selected(), len(self.ent_agentes) - 1)]

    def definiciones_entrevista(self):
        """El catálogo registrado (`cotejo modelos agregar`) que conoce el board."""
        definiciones = getattr(self, "definiciones", None)
        if definiciones is not None:
            return definiciones
        from enrutador import config as enrutador_config
        try:
            return enrutador_config.cargar().get("modelos") or []
        except enrutador_config.ConfigInvalida:
            return []

    def llenar_modelos(self):
        """Los modelos del agente elegido, con el suyo por defecto seleccionado."""
        from enrutador import niveles
        from .modelos import texto_de_modelo
        cliente = self.agente_elegido()
        definiciones = self.definiciones_entrevista()
        self.ent_modelos = list(niveles.modelos_de(cliente, definiciones)) if cliente else []
        self.ent_modelo.set_model(
            Gtk.StringList.new([texto_de_modelo(n) for n in self.ent_modelos]))
        self.ent_modelo.set_sensitive(bool(self.ent_modelos))
        if not self.ent_modelos:
            return
        defecto = niveles.modelo_por_defecto(cliente, definiciones)
        claves = [n.modelo for n in self.ent_modelos]
        self.ent_modelo.set_selected(claves.index(defecto) if defecto in claves else 0)

    def modelo_elegido(self):
        """La clave del modelo elegido (`astra`, `sol`, `opus`…), o None sin agentes."""
        if not self.ent_modelos:
            return None
        indice = min(self.ent_modelo.get_selected(), len(self.ent_modelos) - 1)
        return self.ent_modelos[indice].modelo

    def _al_cambiar_agente(self, *_):
        self.llenar_modelos()
        self._al_cambiar_entrevista()

    def respuestas_entrevista(self):
        """Lo que hay en el formulario ahora, como `inicio.Respuestas` (sin validar)."""
        marcadas = lambda grupo: [t for t, b in grupo.items() if b.get_active()]  # noqa: E731
        return entrevista.respuestas(
            self.ent_que_es.get_text(), self.ent_para_quien.get_text(),
            self._texto_de(self.ent_que_hace), marcadas(self.ent_donde),
            marcadas(self.ent_necesita), self.ent_fuera.get_text(), self.ent_carpeta.get_text())

    def _seguir_nombre(self, *_):
        if not self.ent_carpeta_a_mano:
            self.ent_carpeta.handler_block_by_func(self._carpeta_a_mano)
            self.ent_carpeta.set_text(entrevista.carpeta_sugerida(self.ent_que_es.get_text()))
            self.ent_carpeta.handler_unblock_by_func(self._carpeta_a_mano)

    def _carpeta_a_mano(self, *_):
        self.ent_carpeta_a_mano = True

    def _al_cambiar_entrevista(self, *_):
        self.actualizar_entrevista()

    def actualizar_entrevista(self):
        """Repinta el avance, el prompt que se enviaría y si se puede preparar."""
        r = self.respuestas_entrevista()
        self.ent_que_hace_ejemplo.set_visible(not self._texto_de(self.ent_que_hace))
        self.entrevista_avance.set_fraction(entrevista.rellenadas(r) / 6)
        prompt, motivo = entrevista.prompt_o_error(r)
        self.ent_prompt.get_buffer().set_text(prompt or f"(todavía no se puede armar: {motivo})")
        self.ent_error.set_label(motivo)
        self.ent_error.set_visible(bool(motivo))
        self.ent_preparar.set_sensitive(not motivo and self.agente_elegido() is not None)
        return prompt, motivo

    def detectar_agentes(self):
        """Mira qué agentes hay en el PATH y llena el desplegable. Sin ninguno, lo dice."""
        from enrutador import clientes
        nombres = clientes.instalados()
        self.ent_agentes = list(nombres)
        self.ent_agente.set_model(Gtk.StringList.new(
            [clientes.CLIENTES[n].titulo or n for n in nombres]))
        self.ent_agente.set_sensitive(bool(nombres))
        self.ent_agente_pista.set_label(
            "detectado" if nombres else
            "No encontré ningún agente de terminal. Instala uno (Claude Code, Codex, OpenCode "
            "o Gemini CLI) y vuelve a abrir esto.")
        self.llenar_modelos()

    # --- las acciones ---------------------------------------------------------------------------

    def nuevo_proyecto(self):
        """«Nuevo proyecto»: abre la entrevista (cotejo-kf94so)."""
        self.detectar_agentes()
        self.actualizar_entrevista()
        self.ver_pestana(ENTREVISTA)

    def cancelar_entrevista(self):
        self.ver_pestana("inicio")

    def preparar_proyecto(self):
        """Valida y lanza al agente en segundo plano. Devuelve el estado o None si no se pudo."""
        from enrutador import preparar
        r = self.respuestas_entrevista()
        try:
            r = inicio.validar(r)
        except ValueError as error:
            self.aviso(str(error))
            return None
        try:
            estado = preparar.lanzar(r, cliente=self.agente_elegido(),
                                     modelo=self.modelo_elegido(),
                                     al_terminar=lambda e: GLib.idle_add(
                                         self.preparacion_terminada, e))
        except preparar.NoSePuede as error:
            self.aviso(str(error))
            return None
        self.mostrar_preparando(estado)
        return estado
