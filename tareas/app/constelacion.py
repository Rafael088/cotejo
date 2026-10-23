"""La constelación de proyectos en el Inicio (v1.3.0, cotejo-7wc9hb): el widget y su leyenda.

La geometría y el dibujo viven sin GTK en `tareas/constelacion.py`; aquí solo se pone lo que
GTK sabe hacer: el alto según el ancho, los nombres con Pango, tocar un núcleo para abrir el
proyecto, la accesibilidad y el reloj.

**El reloj respeta el interruptor de animaciones** (`gtk-enable-animations`, el mismo que
`animaciones_activas()` y el dot): hay `add_tick_callback` solo mientras el widget está
mapeado y las animaciones están activas. Apagadas, la constelación se pinta quieta una vez y no
pide ni un fotograma más; el ajuste se escucha solo mientras se ve, como en `dot_widget.Dot`.

Los colores son los del tema que se está viendo (`colores()`, lo que `App.aplicar_tema` deja en
`app.colores`), así que cambiar de tema la repinta sin rehacerla.
"""

from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from .. import constelacion as c
from .comun import ESPACIADO_LG, ESPACIADO_SM, ESPACIADO_XS
from .piezas import etiquetar

LADO_LEYENDA = 14


class Constelacion(Gtk.Widget):
    """Los proyectos como núcleos con sus piezas alrededor, pintados por estado.

    `colores` es una función que devuelve los tokens del tema; `al_tocar(nombre)`, lo que pasa
    al tocar un proyecto (en el Inicio, `abrir_proyecto`).
    """

    __gtype_name__ = "CotejoConstelacion"

    def __init__(self, colores, al_tocar=None, **kwargs):
        super().__init__(accessible_role=Gtk.AccessibleRole.IMG, hexpand=True,
                         css_classes=["constelacion"], **kwargs)
        self._colores = colores
        self._al_tocar = al_tocar
        self.proyectos = []
        self.nucleos = []
        self._ancho_nucleos = None
        self._inicio = GLib.get_monotonic_time()
        self._tick = 0
        self._ajustes = None
        self._aviso_ajustes = 0
        self.fotogramas = 0            # veces que se pintó: las pruebas lo miran
        self.piezas_pintadas = 0
        if al_tocar is not None:
            self.set_cursor_from_name("pointer")
            toque = Gtk.GestureClick()
            toque.connect("released", self._al_soltar)
            self.add_controller(toque)

    # --- la API del Inicio ----------------------------------------------------------------------

    def poner(self, proyectos):
        """Los proyectos a dibujar (las `Tarjeta` del Inicio: `nombre` y `estados`)."""
        self.proyectos = list(proyectos)
        self._ancho_nucleos = None
        etiquetar(self, c.descripcion(self.proyectos))
        self.queue_resize()
        self._sincronizar_tick()

    def animada(self):
        """Si ahora mismo hay reloj de fotogramas (las pruebas lo miran)."""
        return bool(self._tick)

    # --- por dentro -----------------------------------------------------------------------------

    def _animaciones(self):
        ajustes = self._ajustes or self.get_settings()
        return bool(ajustes and ajustes.get_property("gtk-enable-animations"))

    def _nucleos(self, ancho):
        if ancho != self._ancho_nucleos:
            self.nucleos = c.disponer(self.proyectos, ancho)
            self._ancho_nucleos = ancho
        return self.nucleos

    def _al_soltar(self, _gesto, _n, x, y):
        nucleo = c.nucleo_en(self._nucleos(self.get_width()), x, y)
        if nucleo is not None and self._al_tocar is not None:
            self._al_tocar(nucleo.nombre)

    # --- el reloj -------------------------------------------------------------------------------

    def _hace_falta_tick(self):
        return self.get_mapped() and self._animaciones() and any(
            n.puntos for n in self._nucleos(self.get_width()))

    def _sincronizar_tick(self):
        if self._hace_falta_tick():
            if not self._tick:
                self._tick = self.add_tick_callback(self._al_tick)
        elif self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0
        self.queue_draw()

    def _al_tick(self, _widget, _reloj):
        self.queue_draw()
        if not self._hace_falta_tick():
            self._tick = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def do_map(self):
        Gtk.Widget.do_map(self)
        self._ajustes = self.get_settings()
        self._aviso_ajustes = self._ajustes.connect("notify::gtk-enable-animations",
                                                    lambda *_: self._sincronizar_tick())
        self._sincronizar_tick()

    def do_unmap(self):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0
        if self._aviso_ajustes:
            self._ajustes.disconnect(self._aviso_ajustes)
            self._aviso_ajustes = 0
        self._ajustes = None
        Gtk.Widget.do_unmap(self)

    # --- el tamaño y el dibujo ------------------------------------------------------------------

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientacion, para):
        if orientacion == Gtk.Orientation.HORIZONTAL:
            return c.ANCHO_CELDA_MIN, c.ANCHO_CELDA_MIN * c.POR_FILA, -1, -1
        ancho = para if para > 0 else c.ANCHO_CELDA_MIN * c.POR_FILA
        alto = c.alto_para(len(self.proyectos), ancho)
        return alto, alto, -1, -1

    def do_size_allocate(self, ancho, alto, linea_base):
        self._sincronizar_tick()

    def _ahora(self):
        reloj = self.get_frame_clock() if self.get_mapped() else None
        momento = reloj.get_frame_time() if reloj is not None else GLib.get_monotonic_time()
        return max(0.0, (momento - self._inicio) / 1e6)

    def do_snapshot(self, snapshot):
        ancho, alto = self.get_width(), self.get_height()
        if ancho <= 0 or alto <= 0 or not self.proyectos:
            return
        self.fotogramas += 1
        nucleos = self._nucleos(ancho)
        colores = self._colores() or {}
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, ancho, alto))
        self.piezas_pintadas = c.dibujar(cr, nucleos, colores, t=self._ahora(),
                                         quieto=not self._animaciones())
        tenue = color_gdk(colores, "tenue")
        for nucleo in nucleos:
            x0, y0, celda, alto_fila = nucleo.celda
            capa = self.create_pango_layout(nucleo.nombre)
            capa.set_width(int((celda - ESPACIADO_SM * 2) * Pango.SCALE))
            capa.set_ellipsize(Pango.EllipsizeMode.END)
            capa.set_alignment(Pango.Alignment.CENTER)
            _, logico = capa.get_pixel_extents()
            snapshot.save()
            snapshot.translate(Graphene.Point().init(
                x0 + ESPACIADO_SM, y0 + alto_fila * c.ALTO_NOMBRE - logico.height))
            snapshot.append_layout(capa, tenue)
            snapshot.restore()


def color_gdk(colores, token):
    r, g, b, a = c.rgba(colores, token)
    return Gdk.RGBA(red=r, green=g, blue=b, alpha=a)


def leyenda(colores):
    """Hecho · En curso · Espera que lo compruebes · Falta, con el mismo punto del dibujo."""
    caja = Gtk.Box(spacing=ESPACIADO_LG, css_classes=["constelacion-leyenda"])
    for estado in c.ESTADOS_LEYENDA:
        uno = Gtk.Box(spacing=ESPACIADO_XS)
        punto = Gtk.DrawingArea(content_width=LADO_LEYENDA, content_height=LADO_LEYENDA,
                                valign=Gtk.Align.CENTER)
        punto.set_draw_func(lambda _a, cr, w, h, e=estado: c.dibujar_punto(
            cr, w / 2, h / 2, e, colores() or {}))
        uno.append(punto)
        uno.append(Gtk.Label(label=c.NOMBRES[estado], css_classes=["dato"]))
        caja.append(uno)
    return caja


def caja_constelacion(colores, al_tocar=None):
    """(caja, constelación): el dibujo con su leyenda debajo, lista para `poner_constelacion`."""
    dibujo = Constelacion(colores, al_tocar)
    caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACIADO_SM,
                   css_classes=["constelacion-caja"])
    caja.append(dibujo)
    caja.append(leyenda(colores))
    return caja, dibujo
