"""La conversación con el maestro, en un panel flotante encima del tablero (v1.3.1,
cotejo-w8vteb).

Los mensajes de la persona a la derecha, las respuestas a la izquierda, y mientras contesta lo
que va haciendo (cada `cotejo` que corre, en llano). Si el maestro propone repartir, su
respuesta lleva el botón «Repartir». No es una mezcla de `Board`: es un widget que recibe qué
pintar y a quién avisar, como la constelación; lo maneja la mezcla `maestro.py`.

Flota: vive en el overlay del board, con `halign`/`valign` y márgenes, así que enseñarlo no
empuja ni redimensiona las columnas. Se arrastra por su título y se puede minimizar (queda la
cabecera) o cerrar; ni minimizar ni cerrar paran al maestro: su turno sigue y la respuesta se
guarda para cuando se vuelva a abrir.
"""

from gi.repository import GLib, Gtk, Pango

from .comun import ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS, texto_a_markup
from .escala import px
from .piezas import con_mano, etiquetar

ALTO_MAXIMO = 340


def _etiqueta(texto, clases, xalign=0, markup=False):
    return Gtk.Label(label=texto_a_markup(texto) if markup else texto, use_markup=markup,
                     wrap=True, xalign=xalign, selectable=True,
                     wrap_mode=Pango.WrapMode.WORD_CHAR, max_width_chars=72,
                     css_classes=clases)


class PanelMaestro(Gtk.Box):
    """`al_repartir(indice, ids)`, `al_parar()`, `al_olvidar()` y `al_cerrar()` son de quien lo
    usa; el panel solo pinta (`pintar`), flota (`mover_a`) y avisa."""

    def __init__(self, al_repartir, al_parar, al_olvidar, al_cerrar):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                         halign=Gtk.Align.START, valign=Gtk.Align.START,
                         css_classes=["maestro-panel"])
        self.al_repartir, self.al_parar = al_repartir, al_parar
        self.minimizado = False
        # Si la persona lo movió, deja de anclarse abajo al redimensionar la ventana.
        self.movido = False
        self._desde_arrastre = None
        self.set_size_request(px(720), -1)
        cabeza = Gtk.Box(spacing=px(ESPACIADO_SM), css_classes=["maestro-cabeza"])
        self.titulo = Gtk.Label(xalign=0, hexpand=True, css_classes=["menu-titulo"],
                                ellipsize=Pango.EllipsizeMode.END)
        etiquetar(self.titulo, "Arrastra desde aquí para mover la conversación")
        self.titulo.set_cursor_from_name("grab")
        cabeza.append(self.titulo)
        self.pensando_icono = Gtk.Spinner(visible=False, css_classes=["maestro-chispa"])
        cabeza.append(self.pensando_icono)
        self.boton_minimizar = con_mano(Gtk.Button(
            icon_name="window-minimize-symbolic", css_classes=["flat", "maestro-accion"]))
        etiquetar(self.boton_minimizar, "Minimizar la conversación (el maestro sigue)")
        self.boton_minimizar.connect("clicked", lambda *_: self.alternar_minimizado())
        cabeza.append(self.boton_minimizar)
        self.boton_olvidar = con_mano(Gtk.Button(label="Empezar de nuevo",
                                                 css_classes=["flat", "maestro-accion"]))
        etiquetar(self.boton_olvidar, "Borrar esta conversación y empezar otra")
        self.boton_olvidar.connect("clicked", lambda *_: al_olvidar())
        cabeza.append(self.boton_olvidar)
        cerrar = con_mano(Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat"]))
        etiquetar(cerrar, "Ocultar la conversación (no se borra y no para al maestro)")
        cerrar.connect("clicked", lambda *_: al_cerrar())
        cabeza.append(cerrar)
        self.cabeza = cabeza
        self.append(cabeza)
        self.mensajes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        self.scroll = Gtk.ScrolledWindow(child=self.mensajes, propagate_natural_height=True,
                                         max_content_height=px(ALTO_MAXIMO),
                                         hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.append(self.scroll)
        self.botones_repartir = []
        self.boton_parar = None
        # El título arrastra el panel; los botones de la cabecera no, para que pulsarlos no lo
        # muevan. El gesto es de arrastre y no de clic: con el ratón quieto no pasa nada.
        arrastre = Gtk.GestureDrag()
        arrastre.connect("drag-begin", self._al_empezar_arrastre)
        arrastre.connect("drag-update", self._al_arrastrar)
        self.titulo.add_controller(arrastre)

    # --- flotar ---------------------------------------------------------------------------------

    def anclar_abajo(self, margen_inferior):
        """Abajo al centro, con su borde de abajo a `margen_inferior` del fondo del overlay
        (encima del pie). Lo ancla GTK con `valign=END`, no un `margin_top` calculado: así,
        entero o minimizado, la parte de abajo se queda junto al pie aunque cambie su alto,
        y nunca acaba en mitad de las columnas (cotejo-5ejs0y)."""
        self.movido = False
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.set_margin_start(0)
        self.set_margin_top(0)
        self.set_margin_bottom(max(0, round(margen_inferior)))

    @property
    def anclado(self):
        return self.get_valign() == Gtk.Align.END

    def mover_a(self, x, y, movido=True):
        """Lo deja en (x, y) dentro del overlay, sin salirse. `movido=False` es colocarlo, no
        que la persona lo haya movido (así se sigue recolocando al cambiar el tamaño)."""
        padre = self.get_parent()
        if padre is not None:
            ancho, alto = padre.get_width(), padre.get_height()
            if ancho > 0:
                x = min(x, max(0, ancho - self.get_width()))
            if alto > 0:
                y = min(y, max(0, alto - self.get_height()))
        x, y = max(0, round(x)), max(0, round(y))
        self.movido = self.movido or movido
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_margin_bottom(0)
        self.set_margin_start(x)
        self.set_margin_top(y)

    def posicion(self):
        """Dónde está ahora dentro del overlay, esté anclado abajo o puesto a mano."""
        padre = self.get_parent()
        if self.anclado and padre is not None:
            ok, caja = self.compute_bounds(padre)
            if ok:
                return caja.get_x(), caja.get_y()
        return self.get_margin_start(), self.get_margin_top()

    def reencajar(self):
        """Después de cambiar el tamaño de la ventana: que siga dentro del tablero."""
        if not self.anclado:
            self.mover_a(self.get_margin_start(), self.get_margin_top(), movido=False)

    def _al_empezar_arrastre(self, _gesto, _x, _y):
        self._desde_arrastre = self.posicion()

    def _al_arrastrar(self, _gesto, desplazado_x, desplazado_y):
        if self._desde_arrastre is None:
            self._desde_arrastre = self.posicion()
        self.mover_a(self._desde_arrastre[0] + desplazado_x,
                     self._desde_arrastre[1] + desplazado_y)

    # --- minimizar ------------------------------------------------------------------------------

    def alternar_minimizado(self):
        """Deja solo la cabecera: la conversación sigue ahí, y el maestro también."""
        self.minimizar(not self.minimizado)

    def minimizar(self, si=True):
        self.minimizado = bool(si)
        self.scroll.set_visible(not self.minimizado)
        if self.movido and not self.minimizado:
            # Puesto a mano: la cabecera se queda donde la dejó la persona; al crecer de
            # nuevo, que no se salga por abajo (el alto nuevo llega en la próxima vuelta).
            GLib.idle_add(lambda: self.reencajar() and False)
        self.boton_minimizar.set_icon_name(
            "window-restore-symbolic" if self.minimizado else "window-minimize-symbolic")
        etiquetar(self.boton_minimizar,
                  "Volver a ver la conversación" if self.minimizado else
                  "Minimizar la conversación (el maestro sigue)")

    # --- pintar ---------------------------------------------------------------------------------

    def pintar(self, proyecto, titulo, datos, en_vivo=()):
        """Repinta la conversación entera: es corta y así no hay estados a medias."""
        self.titulo.set_label(f"MAESTRO · {proyecto}" + (f" · {titulo}" if titulo else ""))
        self.pensando_icono.set_spinning(bool(datos.get("en_curso")))
        self.pensando_icono.set_visible(bool(datos.get("en_curso")))
        hijo = self.mensajes.get_first_child()
        while hijo is not None:
            siguiente = hijo.get_next_sibling()
            self.mensajes.remove(hijo)
            hijo = siguiente
        self.botones_repartir, self.boton_parar = [], None
        turnos = datos.get("turnos") or []
        if not turnos and not datos.get("en_curso"):
            self.mensajes.append(_etiqueta(
                "Pídele lo que quieras en llano: «apunta que falta el login», «¿qué falta para "
                "la 0.1.0?», «¿qué hace la pieza Fuente?» o «reparte lo asignado».",
                ["maestro-pista"]))
        for indice, turno in enumerate(turnos):
            self.mensajes.append(self.burbuja(indice, turno))
        if datos.get("en_curso"):
            self.mensajes.append(self.pensando(en_vivo))
        self.boton_olvidar.set_sensitive(bool(turnos) and not datos.get("en_curso"))
        ajuste = self.scroll.get_vadjustment()
        ajuste.set_value(ajuste.get_upper())

    def burbuja(self, indice, turno):
        persona = turno.get("quien") == "persona"
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       halign=Gtk.Align.END if persona else Gtk.Align.START,
                       css_classes=["maestro-burbuja",
                                    "maestro-persona" if persona else "maestro-respuesta"]
                       + ([] if persona or turno.get("ok", True) else ["maestro-fallo"]))
        caja.append(_etiqueta(turno.get("texto") or "", ["maestro-texto"], markup=not persona))
        ids = turno.get("repartir") or []
        if ids and not persona:
            hecho = bool(turno.get("repartido"))
            boton = con_mano(Gtk.Button(
                label=("Repartidas" if hecho else
                       f"Repartir {len(ids)} tarea{'s' if len(ids) != 1 else ''}"),
                halign=Gtk.Align.START, sensitive=not hecho,
                css_classes=["maestro-repartir"]))
            etiquetar(boton, "Lanzar sus agentes, como al pasarlas a Haciendo: "
                      + ", ".join(ids))
            boton.connect("clicked", lambda *_: self.al_repartir(indice, list(ids)))
            caja.append(boton)
            self.botones_repartir.append(boton)
        return caja

    def pensando(self, en_vivo):
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                       halign=Gtk.Align.START,
                       css_classes=["maestro-burbuja", "maestro-respuesta"])
        fila = Gtk.Box(spacing=px(ESPACIADO_MD))
        fila.append(Gtk.Spinner(spinning=True))
        fila.append(Gtk.Label(label="Pensando…", xalign=0, css_classes=["maestro-texto"]))
        self.boton_parar = con_mano(Gtk.Button(label="Parar", css_classes=["flat",
                                                                           "maestro-accion"]))
        etiquetar(self.boton_parar, "Parar al maestro")
        self.boton_parar.connect("clicked", lambda *_: self.al_parar())
        fila.append(self.boton_parar)
        caja.append(fila)
        for linea in en_vivo:
            caja.append(Gtk.Label(label=linea, xalign=0, css_classes=["maestro-vivo"],
                                  ellipsize=Pango.EllipsizeMode.END, max_width_chars=80))
        return caja
