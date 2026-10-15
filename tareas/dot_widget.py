"""El widget `Dot` del board: el dot de Cotejo vivo, con su reloj, su brillo y su etiqueta.

Junta las dos mitades sin GTK —`dot.pose()` dice cómo está el dot en cada instante y
`dot_dibujo.dibujar_dot()` lo pinta— y pone lo que solo GTK sabe hacer bien:

- **El brillo** de la piel (`drop-shadow` del laboratorio) con `push_shadow`, solo a la talla
  grande, como en el laboratorio: a 56 y 24 px va sin brillo.
- **El desaturado** de `falla` con `push_color_matrix`, dentro de la sombra y solo sobre la
  mitad de la piel que lo lleva: en CSS el `drop-shadow` de la piel tiñe con su color fijo lo
  que ya viene filtrado, así que el brillo sigue verde aunque el dot se apague (si la matriz
  fuera por fuera, desaturaría también el brillo; lo midió D3).
- **El reloj**: `add_tick_callback` solo mientras el widget está mapeado y las animaciones
  están activas (`gtk-enable-animations`, lo mismo que `animaciones_activas()` del board). Con
  ellas apagadas, la pose fija del estado (`quieto=True`, como `prefers-reduced-motion`) y el
  tick solo mientras duran sus fundidos de 200 ms. Se registra en `do_map` y se quita en
  `do_unmap`: así el reloj de fotogramas se duerme (la pauta de D3, `docs/dot/rendimiento.md`).
- **La accesibilidad**: rol imagen y una etiqueta que dice el estado. Cambia cuando cambia el
  estado o cuando el board la pone (`set_etiqueta`), nunca por fotograma.

Los colores son los del dot con cualquier tema del board: el modo claro (`claro`) solo baja el
alfa del brillo. Va en su propio módulo, no en `tareas/app/` (el planning, sección 2): el board solo
pone el overlay y las anclas (D5).
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, GObject, Graphene, Gsk, Gtk  # noqa: E402

from . import dot, dot_dibujo  # noqa: E402

TALLA = 56            # la del board
TALLA_GRANDE = 250    # la única con brillo, como `.avatar` en el laboratorio
TALLAS = (24, 56, 250)

# El `radius` de `Gsk.Shadow` no es la desviación de la gaussiana: GSK difumina con
# σ = radius / 2. El laboratorio pide σ = 22 unidades del lienzo (`drop-shadow` toma la
# desviación tal cual), así que a 250 px el radio es 2 × 27,5 = 55 px. Calibrado contra el PNG
# de oro de 250 px en `pruebas/test_dot_dibujo.py`.
FACTOR_RADIO_GSK = 2.1

# Lo que dice el lector de pantalla si el board no ha puesto otra cosa.
ETIQUETAS = {
    "idle": "Cotejo: nada en juego",
    "trabaja": "Cotejo: hay una tarea en curso",
    "comprobar": "Cotejo: hay tareas que esperan que las compruebes",
    "celebra": "Cotejo: una tarea pasó a Finalizada",
    "falla": "Cotejo: se devolvió una tarea",
}

# Cuánto se sale el dibujo del cuadrado del widget, en fracción del lado: el SVG del
# laboratorio no recorta (`overflow: visible`) y en el salto de `celebra` el mechón sube por
# encima del lienzo.
DESBORDE = 0.15


def sombra_gsk(lado, claro=False):
    """La sombra de la piel para `push_shadow`, ya calibrada a `lado` px."""
    r, g, b, a = dot_dibujo.color_sombra(claro)
    sombra = Gsk.Shadow()
    sombra.color = Gdk.RGBA(red=r, green=g, blue=b, alpha=a)
    sombra.dx = 0
    sombra.dy = 0
    sombra.radius = FACTOR_RADIO_GSK * dot_dibujo.sigma_sombra(lado)
    return sombra


def matriz_gsk(saturacion, brillo):
    """(Graphene.Matrix, Graphene.Vec4) de `saturate·brightness` para `push_color_matrix`."""
    m = Graphene.Matrix()
    m.init_from_float(dot_dibujo.matriz_graphene(saturacion, brillo))
    v = Graphene.Vec4()
    v.init(0, 0, 0, 0)
    return m, v


class Dot(Gtk.Widget):
    """El dot. `Dot(estado="idle", talla=56)`; luego `poner_estado`, `set_etiqueta`, `entrar`.

    Propiedades de GObject (se pueden fijar con `set_property` o en el constructor y escuchar
    con `notify::`): `estado` (uno de `dot.ESTADOS`), `talla` (lado en px; con
    `TALLA_GRANDE` o más lleva brillo) y `claro` (el brillo del modo claro).
    """

    __gtype_name__ = "CotejoDot"

    def __init__(self, estado="idle", talla=TALLA, claro=False, **kwargs):
        super().__init__(accessible_role=Gtk.AccessibleRole.IMG, **kwargs)
        if estado not in dot.ESTADOS:
            raise ValueError(f"estado desconocido: {estado}")
        self._estado = estado          # el de la propiedad
        self._estado_pose = estado     # el que se pide a dot.pose (la entrada es `entrada`)
        self._desde = None             # la pose del cambio de estado, para las transiciones
        self._inicio = GLib.get_monotonic_time()
        self._talla = talla
        self._claro = claro
        self._tick = 0
        self._ajustes = None
        self._aviso_ajustes = 0
        self._etiqueta = None
        self.fotogramas = 0            # veces que se pintó: las pruebas lo miran
        self.set_overflow(Gtk.Overflow.VISIBLE)
        self._poner_etiqueta(ETIQUETAS[estado])

    # --- propiedades ---------------------------------------------------------------------------

    @GObject.Property(type=str, default="idle")
    def estado(self):
        return self._estado

    @estado.setter
    def estado(self, valor):
        self.poner_estado(valor)

    @GObject.Property(type=int, default=TALLA, minimum=1)
    def talla(self):
        return self._talla

    @talla.setter
    def talla(self, valor):
        if valor != self._talla:
            self._talla = valor
            self.queue_resize()

    @GObject.Property(type=bool, default=False)
    def claro(self):
        return self._claro

    @claro.setter
    def claro(self, valor):
        if valor != self._claro:
            self._claro = valor
            self.queue_draw()

    # --- la API del board -----------------------------------------------------------------------

    def poner_estado(self, estado, etiqueta=None):
        """Pasa al `estado` desde donde esté el dot ahora, con las transiciones del laboratorio,
        y pone `etiqueta` (o la de `ETIQUETAS`). Volver a pedir el estado en el que ya está no
        reinicia nada: el board lo puede llamar en cada repintado sin que el dot dé saltos."""
        if estado not in dot.ESTADOS:
            raise ValueError(f"estado desconocido: {estado} (están {', '.join(dot.ESTADOS)})")
        if etiqueta is not None or estado != self._estado:
            self._poner_etiqueta(etiqueta or ETIQUETAS[estado])
        if estado == self._estado:     # también durante la entrada, que ya acaba en idle
            return
        self._cambiar(estado)
        self._estado = estado
        self.notify("estado")

    def entrar(self):
        """La entrada: el dot sube desde abajo y se queda en `idle` (760 ms)."""
        self._cambiar(dot.ENTRADA_ESTADO, de_cero=True)
        if self._estado != "idle":
            self._estado = "idle"
            self.notify("estado")
            self._poner_etiqueta(ETIQUETAS["idle"])

    def set_etiqueta(self, texto):
        """La etiqueta del lector de pantalla («Cotejo: 2 tareas esperan que las compruebes»).
        Solo se manda a la accesibilidad si cambia: el lector no tiene que oírla de nuevo."""
        self._poner_etiqueta(texto)

    def get_etiqueta(self):
        return self._etiqueta

    def pose_actual(self):
        """La pose de ahora mismo, la que se pintaría en este fotograma."""
        return self._pose(self._ahora())

    # --- por dentro -----------------------------------------------------------------------------

    def _poner_etiqueta(self, texto):
        if texto != self._etiqueta:
            self._etiqueta = texto
            self.update_property([Gtk.AccessibleProperty.LABEL], [texto])

    def _cambiar(self, estado_pose, de_cero=False):
        ahora = self._ahora()
        # La pose del instante del cambio lleva las transiciones y los relojes en marcha.
        self._desde = None if de_cero else self._pose(ahora)
        self._estado_pose = estado_pose
        self._inicio = ahora
        self._sincronizar_tick()
        self.queue_draw()

    def _ahora(self):
        reloj = self.get_frame_clock() if self.get_mapped() else None
        return reloj.get_frame_time() if reloj is not None else GLib.get_monotonic_time()

    def _pose(self, ahora):
        t = max(0.0, (ahora - self._inicio) / 1e6)
        return dot.pose(self._estado_pose, t, desde=self._desde, quieto=not self._animaciones())

    def _animaciones(self):
        ajustes = self._ajustes or self.get_settings()
        return bool(ajustes and ajustes.get_property("gtk-enable-animations"))

    # --- el reloj -------------------------------------------------------------------------------

    def _hace_falta_tick(self):
        if not self.get_mapped():
            return False
        if self._animaciones():
            return True
        # Movimiento reducido: solo mientras dure algún fundido del último cambio.
        return bool(self._desde is not None and self.pose_actual().transiciones)

    def _sincronizar_tick(self):
        if self._hace_falta_tick():
            if not self._tick:
                self._tick = self.add_tick_callback(self._al_tick)
        elif self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _al_tick(self, _widget, _reloj):
        self.queue_draw()
        if not self._hace_falta_tick():
            self._tick = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _cambio_animaciones(self, *_):
        self._sincronizar_tick()
        self.queue_draw()

    def do_map(self):
        Gtk.Widget.do_map(self)
        # Se escucha el ajuste solo mientras se ve: conectado para siempre al objeto de ajustes,
        # que vive lo que la pantalla, el widget no se liberaría nunca.
        self._ajustes = self.get_settings()
        self._aviso_ajustes = self._ajustes.connect("notify::gtk-enable-animations",
                                                    self._cambio_animaciones)
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

    # --- el dibujo ------------------------------------------------------------------------------

    def do_measure(self, orientacion, para):
        return self._talla, self._talla, -1, -1

    def do_snapshot(self, snapshot):
        self.fotogramas += 1
        lado = self._talla
        x = (self.get_width() - lado) / 2
        y = (self.get_height() - lado) / 2
        snapshot.save()
        snapshot.translate(Graphene.Point().init(x, y))
        pintar_pose(snapshot, self.pose_actual(), lado, self._claro)
        snapshot.restore()


def pintar_pose(snapshot, pose, lado, claro=False, sombra=None):
    """Apila en `snapshot` los nodos de un fotograma del dot a `lado` px.

    Es el `do_snapshot` del widget sin el widget: las pruebas lo usan para renderizar un
    fotograma con GSK sin ventana. `sombra` es si va el brillo (por defecto, a `TALLA_GRANDE`).
    El orden es el del laboratorio: anillos, piel (mechón y cuerpo, cada uno con su filtro) con
    el brillo debajo, ideas y chispas, todo dentro de la opacidad del mundo.
    """
    if sombra is None:
        sombra = lado >= TALLA_GRANDE
    mundo = pose.opacidad["mundo"]
    if mundo <= 0:
        return
    margen = lado * DESBORDE
    area = Graphene.Rect().init(-margen, -margen, lado + 2 * margen, lado + 2 * margen)

    def capa(nombre):
        if dot_dibujo.capa_visible(pose, nombre):
            dot_dibujo.dibujar_dot(snapshot.append_cairo(area), pose, lado, nombre)

    if mundo < 1:
        snapshot.push_opacity(mundo)
    capa("fondo")
    if sombra:
        snapshot.push_shadow([sombra_gsk(lado, claro)])
    for mitad in dot_dibujo.PIEL:
        filtro = pose.filtro.get(mitad)
        if filtro and filtro != (1.0, 1.0):
            snapshot.push_color_matrix(*matriz_gsk(*filtro))
            capa(mitad)
            snapshot.pop()
        else:
            capa(mitad)
    if sombra:
        snapshot.pop()
    capa("frente")
    if mundo < 1:
        snapshot.pop()
