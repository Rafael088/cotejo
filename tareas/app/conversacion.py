"""La conversación con el maestro, encima del pie del board (v1.3.0, cotejo-9ybn1a).

Un `Gtk.Revealer` que sube sobre el tablero cuando se le escribe al maestro: los mensajes de la
persona a la derecha, las respuestas a la izquierda, y mientras contesta lo que va haciendo
(cada `cotejo` que corre, en llano). Si el maestro propone repartir, su respuesta lleva el botón
«Repartir». No es una mezcla de `Board`: es un widget que recibe qué pintar y a quién avisar,
como la constelación; lo maneja la mezcla `maestro.py`.
"""

from gi.repository import Gtk, Pango

from .comun import ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XS
from .escala import px
from .piezas import con_mano, etiquetar

ALTO_MAXIMO = 340


def _etiqueta(texto, clases, xalign=0):
    return Gtk.Label(label=texto, wrap=True, xalign=xalign, selectable=True,
                     wrap_mode=Pango.WrapMode.WORD_CHAR, max_width_chars=72,
                     css_classes=clases)


class PanelMaestro(Gtk.Revealer):
    """`al_repartir(indice, ids)`, `al_parar()`, `al_olvidar()` y `al_cerrar()` son de quien lo
    usa; el panel solo pinta (`pintar`) y avisa."""

    def __init__(self, al_repartir, al_parar, al_olvidar, al_cerrar):
        super().__init__(transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                         reveal_child=False, css_classes=["maestro-panel-revelador"])
        self.al_repartir, self.al_parar = al_repartir, al_parar
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM),
                       css_classes=["maestro-panel"], halign=Gtk.Align.CENTER,
                       margin_bottom=px(ESPACIADO_XS))
        caja.set_size_request(px(720), -1)
        cabeza = Gtk.Box(spacing=px(ESPACIADO_SM))
        self.titulo = Gtk.Label(xalign=0, hexpand=True, css_classes=["menu-titulo"],
                                ellipsize=Pango.EllipsizeMode.END)
        cabeza.append(self.titulo)
        self.boton_olvidar = con_mano(Gtk.Button(label="Empezar de nuevo",
                                                 css_classes=["flat", "maestro-accion"]))
        etiquetar(self.boton_olvidar, "Borrar esta conversación y empezar otra")
        self.boton_olvidar.connect("clicked", lambda *_: al_olvidar())
        cabeza.append(self.boton_olvidar)
        cerrar = con_mano(Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat"]))
        etiquetar(cerrar, "Ocultar la conversación (no se borra)")
        cerrar.connect("clicked", lambda *_: al_cerrar())
        cabeza.append(cerrar)
        caja.append(cabeza)
        self.mensajes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        self.scroll = Gtk.ScrolledWindow(child=self.mensajes, propagate_natural_height=True,
                                         max_content_height=px(ALTO_MAXIMO),
                                         hscrollbar_policy=Gtk.PolicyType.NEVER)
        caja.append(self.scroll)
        self.set_child(caja)
        self.botones_repartir = []
        self.boton_parar = None

    def pintar(self, proyecto, titulo, datos, en_vivo=()):
        """Repinta la conversación entera: es corta y así no hay estados a medias."""
        self.titulo.set_label(f"MAESTRO · {proyecto}" + (f" · {titulo}" if titulo else ""))
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
        caja.append(_etiqueta(turno.get("texto") or "", ["maestro-texto"]))
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
