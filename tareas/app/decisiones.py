"""Las decisiones del almacén en el board: carta, panel, aceptar."""

from gi.repository import Adw, Gtk

from .. import almacen, decision
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS, texto_a_markup
from .escala import px
from .piezas import chip, con_mano, etiquetar


class Decisiones:
    """Las decisiones del almacén en el board: carta, panel, aceptar."""

    def carta_decision(self, proyecto, alm, entrada):
        """La carta propia de una decisión `propuesta`, en *Para comprobar* (C5, v1.2 · E2).

        No es una tarea: no se arrastra, no cambia de columna y no tiene menú de acciones.
        Se abre con la misma vista de revisión que una entrega (`ver_revision_decision`), y
        ahí es donde está el único botón de Aceptar —nunca en la carta ni por un verbo—.
        `fila.tarea` queda en `None` a propósito: así el arrastre, `abrir` y mover con el
        teclado la dejan en paz sin tener que preguntar qué tipo de carta es.
        """
        fila = con_mano(Gtk.ListBoxRow(css_classes=["carta", "carta-decision"], activatable=True))
        fila.proyecto = proyecto
        fila.tarea = None
        fila.decision = (alm, entrada)
        # El id de la decisión, no el del proyecto: estable aunque se repinte la columna.
        fila.clave = f"decision:{entrada.id}"

        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        fila.set_child(caja)
        chips = Gtk.Box(spacing=px(ESPACIADO_XS))
        chips.append(chip("Decisión propuesta", "aviso",
                          tooltip="La propuso un agente; solo tú la aceptas, desde aquí"))
        caja.append(chips)
        caja.append(Gtk.Label(label=texto_a_markup(entrada.titulo), use_markup=True, xalign=0,
                              yalign=0, wrap=True, hexpand=True, max_width_chars=24,
                              css_classes=["carta-texto"]))
        reemplaza = entrada.datos.get("reemplaza")
        if reemplaza:
            caja.append(Gtk.Label(label=f"Reemplaza a «{reemplaza}»", xalign=0, wrap=True,
                                  css_classes=["revision-dato"]))

        etiquetar(fila, f"Decisión propuesta: {entrada.titulo}. Columna: Para comprobar")
        fila.set_tooltip_text("Clic o Enter: revisar la decisión propuesta y, si procede, "
                              "aceptarla")
        return fila

    # --- revisión de una decisión propuesta (C5, v1.2 · E2) -------------------------------

    def ver_revision_decision(self, proyecto, alm, entrada):
        """Su texto y, si reemplaza otra decisión, la vieja al lado; el único botón es Aceptar.

        Misma forma que `ver_revision`, para que abrir una no se aprenda distinto de abrir la
        otra, pero sin nada de lo que es solo de una entrega: sin pruebas, sin diff, sin
        «abrir en herramienta». Aceptar es lo único que se puede hacer aquí, y es lo único que
        hace: cierra el diálogo y vuelve a pintar; nunca mueve ni aprueba ninguna tarea.
        """
        datos = decision.para_revisar(alm, entrada)
        dialogo = Adw.Dialog(title="Revisar la decisión propuesta", content_width=px(760),
                             content_height=px(560))
        vista = Adw.ToolbarView()
        cabecera = Adw.HeaderBar()
        vista.add_top_bar(cabecera)

        aceptar_boton = Gtk.Button(child=self.con_icono("estado-hecha", "Aceptar"),
                                   css_classes=["suggested-action"])

        def al_aceptar(*_):
            dialogo.close()
            self.aceptar_decision(proyecto, alm, entrada)

        aceptar_boton.connect("clicked", al_aceptar)
        cabecera.pack_end(aceptar_boton)

        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_MD),
                         margin_top=px(ESPACIADO_MD), margin_bottom=px(ESPACIADO_LG),
                         margin_start=px(ESPACIADO_LG), margin_end=px(ESPACIADO_LG))
        cuerpo.append(self.panel_decision("PROPUESTA", datos))
        if datos["reemplaza"]:
            cuerpo.append(self.titulo_seccion(f"REEMPLAZA A «{datos['reemplaza']['id']}»"))
            cuerpo.append(self.panel_decision(None, datos["reemplaza"], secundario=True))

        vista.set_content(Gtk.ScrolledWindow(child=cuerpo, vexpand=True,
                                             hscrollbar_policy=Gtk.PolicyType.NEVER))
        dialogo.set_child(vista)
        dialogo.present(self)
        dialogo.set_focus(aceptar_boton)

    def panel_decision(self, titulo, datos, secundario=False):
        """El texto de una decisión (la propuesta, o la que reemplaza, al lado). Sin GTK por
        dentro: `decision.para_revisar` ya deja el texto tal cual, listo para pintar."""
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       css_classes=["anotacion"] if secundario else [])
        if titulo:
            caja.append(self.titulo_seccion(titulo))
        caja.append(Gtk.Label(label=datos["titulo"], xalign=0, wrap=True,
                              css_classes=["revision-texto"]))
        datos_linea = " · ".join(parte for parte in (
            datos.get("autor", ""), datos.get("fecha", ""),
            ", ".join(datos.get("temas") or ())) if parte)
        if datos_linea:
            caja.append(Gtk.Label(label=datos_linea, xalign=0, css_classes=["revision-dato"]))
        texto = (datos.get("texto") or "").strip()
        if texto:
            caja.append(Gtk.Label(label=texto, xalign=0, wrap=True, selectable=True,
                                  css_classes=["anotacion-texto"]))
        return caja

    def aceptar_decision(self, proyecto, alm, entrada):
        """La única escritura que acepta una decisión: solo la persona la pide, desde el
        botón de la vista de revisión. Nunca por un verbo de CLI ni por MCP."""
        try:
            aceptada, reemplazada = decision.aceptar(alm, entrada.id, entrada.version)
        except (almacen.EntradaNoExiste, almacen.IdRepetido, almacen.EntradaCambiada,
                almacen.NoSeEdita, decision.NoEsDecision) as error:
            self.aviso(str(error))
            return
        except decision.AceptacionParcial as error:
            # La propuesta sí quedó aceptada: lo que falló fue dejar la vieja reemplazada.
            self.aviso(str(error))
            self.pintar()
            return
        mensaje = f"«{aceptada.id}» aceptada"
        if reemplazada is not None:
            mensaje += f"; «{reemplazada.id}» quedó reemplazada"
        self.aviso(mensaje)
        self.pintar()
