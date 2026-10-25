"""La pantalla «Revisar el equipo» del board (v1.3.0, cotejo-36mzm0): reemplaza el primer arranque.

Se ve la primera vez (la fuente de repos sin ningún repo, `equipo.es_primer_arranque`) en vez del
tablero, y dice qué agentes de terminal y qué git hay en esta máquina. De cada uno que falta
lleva a su página oficial (`Board.abrir_pagina`, el lanzador de enlaces del sistema); Cotejo no
instala nada. «Ya lo instalé, revisar otra vez» vuelve a detectar y «Seguir al Inicio» pasa a la
pestaña Inicio. Es una página más de la pila (`"equipo"`, sin botón en el selector).
Qué se detecta lo decide `tareas/equipo.py`, sin GTK; aquí solo se pinta.
"""

from gi.repository import Gio, Gtk

from .. import equipo
from .comun import ESPACIADO_LG, ESPACIADO_MD, ESPACIADO_SM, ESPACIADO_XL, ESPACIADO_XS
from .escala import px
from .piezas import chip, con_mano, etiquetar, vaciar

EQUIPO = "equipo"


class PestanaEquipo:
    def crear_equipo(self):
        cuerpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_LG),
                         margin_top=px(ESPACIADO_XL) * 2, margin_bottom=px(ESPACIADO_XL) * 2,
                         margin_start=px(ESPACIADO_XL) * 2, margin_end=px(ESPACIADO_XL) * 2)
        cuerpo.append(Gtk.Label(label="Primer arranque", xalign=0, css_classes=["dato"]))
        cuerpo.append(Gtk.Label(label="Antes de empezar, Cotejo revisa tu equipo", xalign=0,
                                wrap=True, css_classes=["inicio-titular"]))
        cuerpo.append(Gtk.Label(
            label="Para preparar proyectos hace falta un agente de IA. Esto es lo que encontré:",
            xalign=0, wrap=True, css_classes=["vacio-pista"]))
        self.equipo_filas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_SM))
        cuerpo.append(self.equipo_filas)
        self.equipo_titular = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-titulo"])
        self.equipo_mensaje = Gtk.Label(xalign=0, wrap=True, css_classes=["vacio-pista"])
        cuerpo.append(self.equipo_titular)
        cuerpo.append(self.equipo_mensaje)
        botones = Gtk.Box(spacing=px(ESPACIADO_MD))
        self.equipo_revisar = con_mano(Gtk.Button(label="Ya lo instalé, revisar otra vez",
                                                  css_classes=["suggested-action"]))
        self.equipo_revisar.connect("clicked", lambda *_: self.revisar_equipo())
        self.equipo_seguir = con_mano(Gtk.Button(label="Seguir al Inicio"))
        self.equipo_seguir.connect("clicked", lambda *_: self.seguir_al_inicio())
        botones.append(self.equipo_revisar)
        botones.append(self.equipo_seguir)
        cuerpo.append(botones)
        return Gtk.ScrolledWindow(child=cuerpo, hexpand=True, vexpand=True,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER, css_classes=["inicio"])

    def revisar_equipo(self):
        """Vuelve a detectar y repinta. Devuelve el `Equipo` que vio."""
        visto = equipo.revisar()
        self.equipo_visto = visto
        vaciar(self.equipo_filas)
        self.equipo_enlaces = {}
        for pieza in visto.piezas:
            fila = Gtk.Box(spacing=px(ESPACIADO_MD), css_classes=["carta"])
            fila.append(Gtk.Label(label=pieza.titulo, xalign=0, hexpand=True))
            fila.append(chip(pieza.estado, "", *(["verde"] if pieza.listo else [])))
            if not pieza.listo:
                enlace = con_mano(Gtk.Button(label=pieza.texto_enlace, valign=Gtk.Align.CENTER,
                                             css_classes=["flat"]))
                etiquetar(enlace, f"{pieza.texto_enlace} (abre su página oficial)")
                enlace.connect("clicked", lambda _b, p=pieza: self.abrir_pagina(p.pagina))
                self.equipo_enlaces[pieza.clave] = enlace
                fila.append(enlace)
            self.equipo_filas.append(fila)
        self.equipo_titular.set_label(visto.titular)
        self.equipo_mensaje.set_label(visto.mensaje)
        return visto

    def abrir_pagina(self, url):
        """Abre una página oficial con el lanzador del sistema (las pruebas lo sustituyen)."""
        Gio.AppInfo.launch_default_for_uri(url, None)

    def seguir_al_inicio(self):
        self.ver_pestana("inicio")
