"""El overlay del dot (D5): dónde se ancla y cómo se mueve."""

import time

from gi.repository import GLib, Gdk, Gtk

from .. import configuracion, estado, presencia
from ..dot_widget import Dot
from .comun import animaciones_activas


class CapaDot:
    """El overlay del dot (D5): dónde se ancla y cómo se mueve."""

    # --- el dot (D5) ---------------------------------------------------

    def montar_dot(self):
        """El dot es opcional (`"dot": true` en la config, apagado por defecto): con la clave
        apagada no se crea nada, ni overlay ni timers. Qué estado y qué ancla tocan lo decide
        `presencia` (sin GTK); aquí solo se leen los rectángulos de los widgets y se mueve. La
        posición se calcula en `get-child-position`, que el overlay pide al redimensionar y al
        repintar, y que el scroll y el viaje piden con `queue_allocate`."""
        self.presencia = None
        self.dot = None
        self.dot_entrado = False
        self.dot_entrando = False   # durante los 760 ms de la entrada no cambia de estado
        self.dot_ancla = None       # dónde está o a dónde va
        self.dot_pos = None         # (x, y) de la última vez que se colocó
        self.dot_viaje = None       # (desde, instante de salida en µs) mientras viaja
        self.dot_tick = 0
        self.dot_fin_momento = 0
        self.dot_fin_entrada = 0
        self.dot_conexiones = []    # (objeto, id) para soltarlos al apagarlo
        if configuracion.dot_activo():
            self.encender_dot()     # entra cuando el board ya se ve (`entrar_dot`)

    def sincronizar_dot(self):
        """Con el board abierto, deja el dot como dice la config: lo crea si se encendió, lo
        destruye si se apagó."""
        quiere = configuracion.dot_activo()
        if quiere and self.dot is None:
            self.encender_dot()
            self.entrar_dot()
            self.actualizar_dot()
        elif not quiere and self.dot is not None:
            self.apagar_dot()

    def encender_dot(self):
        self.presencia = presencia.Presencia()
        self.dot = Dot(talla=presencia.TALLA, visible=False, can_target=False,
                       claro=getattr(self.app, "esquema", None) == "claro",
                       halign=Gtk.Align.START, valign=Gtk.Align.START)
        self.encima.add_overlay(self.dot)
        self.dot_conexiones = [(self.encima, self.encima.connect(
            "get-child-position", self.al_colocar_dot))]
        recolocar = lambda *_a: self.encima.queue_allocate()  # noqa: E731
        ajustes = [self.scroll_tablero.get_hadjustment()]
        ajustes += [scroll.get_vadjustment() for _l, _c, scroll in self.columnas.values()]
        for ajuste in ajustes:
            self.dot_conexiones.append((ajuste, ajuste.connect("value-changed", recolocar)))

    def apagar_dot(self):
        """Lo contrario de `encender_dot`: no queda overlay, ni timers, ni señales."""
        for fuente in (self.dot_fin_momento, self.dot_fin_entrada):
            if fuente:
                GLib.source_remove(fuente)
        if self.dot_tick:
            self.encima.remove_tick_callback(self.dot_tick)
        for objeto, id_ in self.dot_conexiones:
            objeto.disconnect(id_)
        self.dot_conexiones = []
        self.encima.remove_overlay(self.dot)
        self.dot = self.presencia = self.dot_ancla = self.dot_pos = self.dot_viaje = None
        self.dot_tick = self.dot_fin_momento = self.dot_fin_entrada = 0
        self.dot_entrado = self.dot_entrando = False

    def entrar_dot(self):
        """La entrada: el dot sube hasta el pie, su casa, y de ahí sale a donde le toque."""
        if self.dot is None or self.dot_entrado:
            return
        # Con Inicio delante (v1.3.0) no entra: lo hará al verse el tablero (`ver_pestana`).
        if not self.tablero_a_la_vista():
            return
        self.dot_entrado = True
        self.dot_ancla, self.dot_viaje = presencia.PIE, None
        self.dot.set_visible(True)
        self.dot.entrar()
        if animaciones_activas():
            self.dot_entrando = True
            self.dot_fin_entrada = GLib.timeout_add(
                round(presencia.ENTRADA_S * 1000), self.al_acabar_entrada)
        else:
            self.poner_dot()

    def al_acabar_entrada(self):
        self.dot_fin_entrada = 0
        self.dot_entrando = False
        self.poner_dot()
        return False

    def actualizar_dot(self):
        """Después de cada repintado: qué hay en Haciéndola y en Para comprobar."""
        if getattr(self, "presencia", None) is None:
            return
        en_curso = [fila.clave for fila in self.cartas(self.columnas["en-curso"][0])]
        por_comprobar = len(self.cartas(self.columnas["por-validar"][0]))
        self.presencia.ver(en_curso, por_comprobar)
        self.poner_dot()

    def poner_dot(self):
        if self.dot is None or not self.dot_entrado or self.dot_entrando:
            return
        ahora = time.monotonic()
        vista = self.presencia.vigente(ahora)
        self.dot.poner_estado(vista.estado, vista.etiqueta)
        if vista.ancla != self.dot_ancla:
            self.dot_ancla = vista.ancla
            # Sin animaciones, salta; con ellas, viaja desde donde esté (también a medio viaje).
            if self.dot_pos is not None and animaciones_activas() and self.dot.get_mapped():
                self.dot_viaje = (self.dot_pos, self.ahora_dot())
                if not self.dot_tick:
                    self.dot_tick = self.encima.add_tick_callback(self.al_tick_dot)
            else:
                self.dot_viaje = None
        if self.dot_fin_momento:
            GLib.source_remove(self.dot_fin_momento)
            self.dot_fin_momento = 0
        if vista.hasta is not None:
            self.dot_fin_momento = GLib.timeout_add(
                max(1, round((vista.hasta - ahora) * 1000)), self.al_acabar_momento)
        self.encima.queue_allocate()

    def al_acabar_momento(self):
        self.dot_fin_momento = 0
        self.poner_dot()
        return False

    def al_tecla_dot(self, _control, tecla, _codigo, estado):
        """Alt+← → pasa el dot a la tarea en curso de al lado, solo mientras está en una."""
        otros = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if (tecla not in (Gdk.KEY_Left, Gdk.KEY_Right) or not estado & Gdk.ModifierType.ALT_MASK
                or estado & otros):
            return False
        if self.presencia is None:
            return False
        if self.presencia.vigente(time.monotonic()).estado != "trabaja":
            return False
        if self.presencia.pasar(-1 if tecla == Gdk.KEY_Left else 1):
            self.poner_dot()
        return True

    def ahora_dot(self):
        reloj = self.encima.get_frame_clock()
        return reloj.get_frame_time() if reloj is not None else GLib.get_monotonic_time()

    def al_tick_dot(self, _widget, _reloj):
        self.encima.queue_allocate()
        if self.dot_viaje is None:
            self.dot_tick = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def al_colocar_dot(self, _overlay, widget, rect):
        if widget is not self.dot:
            return False
        destino = self.donde_va_el_dot(self.dot_ancla)
        if self.dot_viaje is not None:
            desde, salida = self.dot_viaje
            t = (self.ahora_dot() - salida) / 1e6
            x, y = presencia.de_camino(desde, destino, t)
            if presencia.viaje_terminado(t):
                self.dot_viaje = None
        else:
            x, y = destino
        self.dot_pos = (x, y)
        rect.x, rect.y = round(x), round(y)
        rect.width = rect.height = presencia.TALLA
        return True

    def caja_en_encima(self, widget):
        hecho, r = widget.compute_bounds(self.encima)
        return (r.get_x(), r.get_y(), r.get_width(), r.get_height()) if hecho else None

    def fila_de(self, clave, columna):
        """La carta de una tarea por su id: las cartas se rehacen en cada repintado."""
        orden = [columna] + [c for c in self.orden if c != columna]
        for col in orden:
            if col not in self.columnas:
                continue
            for fila in self.cartas(self.columnas[col][0]):
                if fila.clave == clave:
                    return col, fila
        return None, None

    def donde_va_el_dot(self, ancla):
        """(x, y) del dot en el overlay para esa ancla. Si la carta no está a la vista (un
        filtro, un scroll), cae al borde de su columna; si tampoco hay columna, al pie."""
        ancla = ancla or presencia.PIE
        if ancla.sitio == "riel":
            caja = self.caja_en_encima(self.finalizada.riel)
            if caja:
                return presencia.en_riel(caja)
        columna = ancla.columna
        if ancla.sitio == "carta":
            col, fila = self.fila_de(ancla.clave, ancla.columna)
            columna = col or columna
            carta = self.caja_en_encima(fila) if fila is not None else None
            vista = self.caja_en_encima(self.columnas[col][2]) if fila is not None else None
            if carta and vista and presencia.a_la_vista(carta, vista):
                return presencia.en_carta(carta)
        if ancla.sitio in ("carta", "columna") and columna in self.columnas:
            caja = self.caja_en_encima(self.columnas[columna][2].get_parent())
            if caja:
                return presencia.en_columna(caja)
        barra, pie = self.caja_en_encima(self.barra_del_maestro), self.caja_en_encima(self.pie)
        if barra and pie:
            return presencia.en_pie(barra, pie)
        return self.dot_pos or (0, 0)
