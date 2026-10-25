"""La banda de proyectos: chips, flechas, arrastre y centrado."""

from gi.repository import Adw, GLib, Gtk

from . import comun
from .comun import (
    ALTO_CHIP_BANDA, CENTRADO_MS, ESPACIADO_SM, ESPACIADO_XS, FRANJA_BANDA, TODOS,
    UMBRAL_ARRASTRE, animaciones_activas, posicion_centrado,
)
from .escala import px
from .piezas import chip, con_mano, etiquetar, icono, vaciar


class Banda:
    """La banda de proyectos: chips, flechas, arrastre y centrado."""

    def crear_banda_proyectos(self):
        """La franja de proyectos: una fila de chips, centrada, uno por proyecto.

        Con pocos proyectos es solo eso, una fila quieta en el centro: nada que arrastrar ni
        que dé vueltas. Cuando ya no caben, la fila se desplaza —rueda del mouse, arrastre o las
        flechas ‹ › de los lados, que solo salen entonces y se apagan al llegar a un extremo—.
        Se elige con clic o con teclado (flechas entre chips, Intro o espacio); los chips son
        botones de verdad, así que el foco y el lector de pantalla los ven como lo que son.

        Antes la banda era infinita (la lista repetida, dando la vuelta): con dos o tres
        proyectos se veía el mismo nombre tres veces seguidas y no se sabía cuál era cuál.
        """
        self.chips = Gtk.Box(spacing=px(ESPACIADO_SM), halign=Gtk.Align.CENTER)
        self.animacion_banda = None
        self.botones_chip = {}
        self.banda_scroll = Gtk.ScrolledWindow(hexpand=True, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                               hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                               child=self.chips)
        arrastre = Gtk.GestureDrag()
        arrastre.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        arrastre.connect("drag-begin", self.al_empezar_banda)
        arrastre.connect("drag-update", self.al_arrastrar_banda)
        arrastre.connect("drag-end", self.al_soltar_banda)
        self.banda_scroll.add_controller(arrastre)
        # La rueda va de lado: en una fila horizontal, girarla hacia abajo es ir a la derecha.
        rueda = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        rueda.connect("scroll", self.al_girar_rueda_banda)
        self.banda_scroll.add_controller(rueda)
        ajuste = self.banda_scroll.get_hadjustment()
        for senal in ("notify::page-size", "notify::upper"):
            ajuste.connect(senal, self.al_medir_banda)
        ajuste.connect("value-changed", lambda *_: self.poner_flechas_banda())
        self.banda_origen = 0.0
        self.vigilar_teclas(self.chips, self.al_tecla_banda)

        self.flecha_banda_atras = self.flecha_de_banda("flecha-izquierda", -1,
                                                       "Ver los proyectos de antes")
        self.flecha_banda_adelante = self.flecha_de_banda("flecha-derecha", 1,
                                                          "Ver más proyectos")
        # Un desvanecido en el borde por donde siguen los chips, en vez de cortarlos en seco:
        # dice que hay más por ese lado sin tener que leer la flecha.
        encima = Gtk.Overlay(child=self.banda_scroll, hexpand=True)
        self.fundidos_banda = []
        for lado, alineado in (("izquierda", Gtk.Align.START), ("derecha", Gtk.Align.END)):
            fundido = Gtk.Box(halign=alineado, can_target=False,
                              css_classes=["banda-fundido", lado])
            encima.add_overlay(fundido)
            self.fundidos_banda.append(fundido)
        fila = Gtk.Box(spacing=px(ESPACIADO_XS))
        fila.append(self.flecha_banda_atras)
        fila.append(encima)
        fila.append(self.flecha_banda_adelante)

        # Cinco partes iguales y la banda en las tres del centro: el 60 %.
        rejilla = Gtk.Grid(column_homogeneous=True, css_classes=["banda-proyectos"])
        # Las partes de los lados llevan un hueco vacío: una columna sin hijos no existe.
        rejilla.attach(Gtk.Box(), 0, 0, 1, 1)
        rejilla.attach(fila, 1, 0, FRANJA_BANDA - 2, 1)
        rejilla.attach(Gtk.Box(), FRANJA_BANDA - 1, 0, 1, 1)
        self.poner_flechas_banda()
        return rejilla

    def flecha_de_banda(self, nombre_icono, sentido, texto):
        """Una de las flechas de los lados de la banda: avanza casi una página de chips."""
        boton = con_mano(Gtk.Button(child=icono(nombre_icono, 14), focusable=False,
                                    valign=Gtk.Align.CENTER,
                                    css_classes=["flat", "banda-flecha"], tooltip_text=texto))
        etiquetar(boton, texto)
        boton.connect("clicked", lambda *_: self.desplazar_banda(sentido))
        return boton

    def desplazar_banda(self, sentido):
        ajuste = self.banda_scroll.get_hadjustment()
        self.llevar_banda_a(ajuste.get_value() + sentido * ajuste.get_page_size() * 0.8)

    def llevar_banda_a(self, valor, animar=True):
        """Mueve la banda a `valor` (acotado a sus extremos), con la animación de centrar."""
        ajuste = self.banda_scroll.get_hadjustment()
        destino = max(0.0, min(valor, ajuste.get_upper() - ajuste.get_page_size()))
        if self.animacion_banda is not None:
            self.animacion_banda.skip()
            self.animacion_banda = None
        if animar and animaciones_activas():
            objetivo = Adw.CallbackAnimationTarget.new(ajuste.set_value)
            self.animacion_banda = Adw.TimedAnimation.new(
                self.banda_scroll, ajuste.get_value(), destino, CENTRADO_MS, objetivo)
            self.animacion_banda.set_easing(Adw.Easing.EASE_OUT_CUBIC)
            self.animacion_banda.connect("done", self.al_acabar_centrado)
            self.animacion_banda.play()
        else:
            ajuste.set_value(destino)

    def al_girar_rueda_banda(self, _control, _dx, dy):
        ajuste = self.banda_scroll.get_hadjustment()
        if ajuste.get_upper() <= ajuste.get_page_size():
            return False
        ajuste.set_value(ajuste.get_value() + dy * px(ALTO_CHIP_BANDA))
        return True

    def banda_desborda(self):
        ajuste = self.banda_scroll.get_hadjustment()
        return ajuste.get_upper() - ajuste.get_page_size() > 1

    def poner_flechas_banda(self):
        """Las flechas solo existen si hay algo que no se ve, y se apagan en cada extremo.
        Sin desborde tampoco hay cursor de agarrar: no hay nada que arrastrar."""
        ajuste = self.banda_scroll.get_hadjustment()
        desborda = self.banda_desborda()
        maximo = ajuste.get_upper() - ajuste.get_page_size()
        lados = ((self.flecha_banda_atras, ajuste.get_value() > 1),
                 (self.flecha_banda_adelante, ajuste.get_value() < maximo - 1))
        for (flecha, puede), fundido in zip(lados, getattr(self, "fundidos_banda", ())):
            flecha.set_visible(desborda)
            flecha.set_sensitive(puede)
            fundido.set_visible(desborda and puede)
        self.banda_scroll.set_cursor_from_name("grab" if desborda else None)

    def al_empezar_banda(self, _gesto, _x, _y):
        if self.animacion_banda is not None:
            self.animacion_banda.skip()
            self.animacion_banda = None
        self.banda_origen = self.banda_scroll.get_hadjustment().get_value()

    def al_arrastrar_banda(self, gesto, dx, _dy):
        """Pasado un umbral, el gesto es un arrastre y no un clic: se reclama para que el chip
        sobre el que empezó no se elija al soltar. Si todo cabe, no hay arrastre."""
        if not self.banda_desborda():
            return
        if abs(dx) > UMBRAL_ARRASTRE:
            gesto.set_state(Gtk.EventSequenceState.CLAIMED)
            self.banda_scroll.set_cursor_from_name("grabbing")
        self.banda_scroll.get_hadjustment().set_value(self.banda_origen - dx)

    def al_soltar_banda(self, _gesto, _dx, _dy):
        self.poner_flechas_banda()

    def al_medir_banda(self, _ajuste, _pspec=None):
        """La banda cambió de tamaño o de contenido: flechas al día y el abierto a la vista."""
        self.poner_flechas_banda()
        GLib.idle_add(self.centrar_chip_activo, False)

    def centrar_chip_activo(self, animar=True):
        """Lleva el chip del proyecto abierto al centro de la banda, si la banda se desplaza.
        Si todo cabe, no hay nada que mover."""
        chip = getattr(self, "botones_chip", {}).get(self.seleccion)
        ajuste = self.banda_scroll.get_hadjustment()
        if chip is None or ajuste.get_page_size() <= 0 or not self.banda_desborda():
            return GLib.SOURCE_REMOVE
        ok, caja = chip.compute_bounds(self.chips)
        if ok:
            self.llevar_banda_a(posicion_centrado(caja.get_x(), caja.get_width(),
                                                  ajuste.get_page_size(),
                                                  ajuste.get_upper() - ajuste.get_page_size()),
                                animar)
        return GLib.SOURCE_REMOVE

    def al_acabar_centrado(self, animacion):
        if self.animacion_banda is animacion:
            self.animacion_banda = None
            self.poner_flechas_banda()

    def pintar_banda(self):
        proyectos = self.proyectos_con_tareas()
        nombres = [p.nombre for p in proyectos]
        if self.seleccion not in nombres and self.seleccion != TODOS:
            # Por defecto, un proyecto: ver 60 tareas de golpe es justo lo que Cotejo evita.
            self.seleccion = nombres[0] if nombres else TODOS
        self.poner_maestro()

        con_foco = self.clave_chip_enfocado()
        vaciar(self.chips)
        self.botones_chip = {}
        for clave, nombre, pendientes, esperando in self.filas_banda(proyectos):
            caja = Gtk.Box(spacing=px(ESPACIADO_SM))
            # «Todos» no es un proyecto más: es la vista de todos juntos. Lleva el ícono del
            # tablero y una raya que lo separa de los proyectos.
            if clave == TODOS:
                caja.append(icono("tablero", 13))
            caja.append(Gtk.Label(label=nombre))
            caja.append(Gtk.Label(label=str(pendientes), css_classes=["banda-cuenta"]))
            if esperando:
                caja.append(Gtk.Label(label=str(esperando), css_classes=["aviso-chip"],
                                      tooltip_text="Esperando que las compruebes"))
            chip = Gtk.Button(child=caja, css_classes=["banda-chip"])
            chip.clave = clave
            etiquetar(chip, f"{'Vista' if clave == TODOS else 'Proyecto'} {nombre}, "
                            f"{pendientes} tareas"
                      + (f", {esperando} por comprobar" if esperando else ""))
            if clave == self.seleccion:
                chip.add_css_class("activo")
            chip.connect("clicked", self.al_elegir_chip)
            self.botones_chip[clave] = chip
            self.chips.append(chip)
            if clave == TODOS and len(nombres) > 0:
                self.chips.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,
                                                css_classes=["banda-separador"],
                                                margin_top=px(ESPACIADO_SM),
                                                margin_bottom=px(ESPACIADO_SM)))
        if con_foco in self.botones_chip:
            self.botones_chip[con_foco].grab_focus()
        GLib.idle_add(self.centrar_chip_activo, False)

    def clave_chip_enfocado(self):
        enfocado = self.get_focus()
        return getattr(enfocado, "clave", None) if enfocado in getattr(
            self, "botones_chip", {}).values() else None

    def al_elegir_chip(self, chip):
        if chip.clave == self.seleccion:
            return
        self.proyecto_anterior = self.seleccion
        self.seleccion = chip.clave
        self.actualizar_volver()
        comun.guardar_board(proyecto=self.seleccion)
        for clave, otro in self.botones_chip.items():
            if clave == chip.clave:
                otro.add_css_class("activo")
            else:
                otro.remove_css_class("activo")
        self.centrar_chip_activo()
        self.poner_maestro()
        self.pintar_columnas(entrando=True)

    def filas_banda(self, proyectos):
        total = sum(len(p.tareas) for p in proyectos)
        esperando = sum(1 for p in proyectos for t in p.tareas if t.estado == "por-validar")
        filas = [(TODOS, "Todos los proyectos", total, esperando)]
        for p in proyectos:
            filas.append((p.nombre, p.nombre, len(p.tareas),
                          sum(1 for t in p.tareas if t.estado == "por-validar")))
        return filas
