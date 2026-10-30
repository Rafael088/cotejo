"""El pie del board: deshacer, el medidor de ahorro y donar."""

import time

from gi.repository import Gio, Gtk, Pango

from .. import ahorro
from .comun import (
    ANCHO_BARRA_MAESTRO, DONAR_URL, ESPACIADO_SM, ESPACIADO_XS, MARGEN_TABLERO_LADOS,
    frase_ahorro, miles,
)
from .escala import px
from .piezas import chip, etiquetar


class Pie:
    """El pie del board: deshacer, el medidor de ahorro y donar."""

    def crear_pie(self):
        """Tres zonas a todo el ancho: medidor y café, barra del Maestro, Deshacer.

        Un CenterBox y no un Box con hexpand: el centro queda en el centro de la VENTANA,
        no en el hueco que dejan los lados, que miden distinto.
        """
        pie = Gtk.CenterBox(css_classes=["pie"], hexpand=True)

        izquierda = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=px(ESPACIADO_XS),
                            valign=Gtk.Align.CENTER, css_classes=["pie-izquierda"],
                            margin_start=px(MARGEN_TABLERO_LADOS))
        izquierda.append(self.pie_ahorro())
        if DONAR_URL:
            izquierda.append(self.pie_donar())
        pie.set_start_widget(izquierda)

        centro = Gtk.Box(valign=Gtk.Align.CENTER, css_classes=["pie-centro"])
        barra = self.barra_maestro()
        barra.set_size_request(px(ANCHO_BARRA_MAESTRO), -1)
        self.barra_del_maestro = barra  # el ancla del dot en el pie, su casa
        centro.append(barra)
        pie.set_center_widget(centro)

        derecha = Gtk.Box(valign=Gtk.Align.CENTER, halign=Gtk.Align.END,
                          css_classes=["pie-derecha"], margin_end=px(MARGEN_TABLERO_LADOS))
        contenido = Gtk.Box(spacing=px(ESPACIADO_SM))
        contenido.append(Gtk.Image.new_from_icon_name("edit-undo-symbolic"))
        contenido.append(Gtk.Label(label="Deshacer"))
        self.boton_deshacer = Gtk.Button(child=contenido, css_classes=["pie-deshacer"])
        etiquetar(self.boton_deshacer, "Deshacer la última tarea finalizada")
        self.boton_deshacer.set_tooltip_text("Deshacer la última tarea finalizada (Ctrl Z)")
        self.boton_deshacer.connect("clicked", self.al_deshacer)
        derecha.append(self.boton_deshacer)
        pie.set_end_widget(derecha)
        self.pie_izquierda, self.pie_centro, self.pie_derecha = izquierda, centro, derecha
        self.actualizar_deshacer()
        return pie

    def actualizar_deshacer(self):
        """El pie dice si se puede echar atrás: con la pila vacía, el botón se queda apagado
        pero visible (nunca un fantasma casi invisible)."""
        pila = getattr(getattr(self, "finalizadas", None), "pila", ())
        self.boton_deshacer.set_sensitive(bool(pila))

    def al_deshacer(self, _boton=None):
        """La misma acción que el «Deshacer» del aviso y Ctrl+Z."""
        self.finalizadas.deshacer()

    def pie_ahorro(self):
        """Lo que costó enterarse por la CLI contra leer las notas, bajo el tablero.

        Va aquí y no en la barra por la misma razón por la que el botón no lleva el total de
        pendientes: un número permanente y a la vista es FOMO. Bajo el tablero está donde
        se mira cuando se quiere mirar, y no estorba el uso de todos los días — por eso en
        plata, sin acento, y sin parada propia de `Tab`: no es algo que haya que atender.

        El supuesto que une lo medido con «ahorrado» —que sin Cotejo se habrían leído las notas
        enteras— no se mide, y por eso va en el tooltip, siempre, junto a la cifra.
        """
        self.ahorro_cifra = Gtk.Label(xalign=0, css_classes=["ahorro-cifra"],
                                      ellipsize=Pango.EllipsizeMode.END)
        # Sin aire propio: el borde izquierdo lo pone el contenedor, el mismo para el café.
        self.ahorro_caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ahorro"])
        self.ahorro_caja.append(self.ahorro_cifra)
        self.pintar_ahorro()
        return self.ahorro_caja

    def pintar_ahorro(self):
        """Repinta el medidor con lo de hoy; el total desde el principio va en la ayuda. Sin
        ninguna lectura hoy, el pie no existe: enseñar «0 tokens ahorrados hoy» sería peor
        que no enseñar nada."""
        datos = ahorro.resumen()
        dia = datos and datos["hoy"]
        self.ahorro_caja.set_visible(bool(dia))
        if not dia:
            return
        self.ahorro_cifra.set_label(frase_ahorro(dia))
        desde = time.strftime("%d/%m/%Y", time.localtime(datos["desde"]))
        self.ahorro_caja.set_tooltip_text(
            f"Hoy, {miles(abs(dia.get('tokens_ahorrados', 0)))} tokens "
            f"{'de más' if dia.get('tokens_ahorrados', 0) < 0 else 'ahorrados'}.\n\n"
            f"Hoy, {dia['lecturas']} lecturas de la CLI devolvieron {miles(dia['devuelto'])} "
            f"caracteres (~{miles(dia['tokens_devueltos'])} tokens); las notas que hubo que "
            f"leer para contestarlas pesaban {miles(dia['leido'])}. El ahorro es frente a "
            f"leer las notas enteras.\n\n"
            f"Desde el {desde}: {miles(datos['tokens_ahorrados'])} tokens ahorrados en "
            f"{datos['lecturas']} lecturas.\n\n{datos['supuesto']}")

    def pie_donar(self):
        """«Invita al autor a un café», debajo del medidor. Sale siempre, haya lecturas o no:
        no depende del número de arriba, y agradecer no debería esperar a que haya ahorro."""
        boton = Gtk.Button(label="☕ Invita al autor a un café", css_classes=["pie-cafe"],
                           halign=Gtk.Align.START, tooltip_text=DONAR_URL)
        boton.connect("clicked", lambda _b: Gio.AppInfo.launch_default_for_uri(DONAR_URL, None))
        return boton
