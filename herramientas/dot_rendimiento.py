"""Prueba de rendimiento del dot (fase D3 del planning del dot).

No es el widget final: es la prueba de viabilidad de que un `Gtk.Widget` escrito en Python,
con `do_snapshot`, `push_shadow`, `push_color_matrix` y `append_cairo`, aguanta 60 fotogramas
por segundo con `add_tick_callback` sin fugas y sin gastar CPU de más. Si no aguantara, el plan
B es un `Gtk.DrawingArea` con la sombra hecha a mano con un degradado radial.

El dibujo de prueba tiene la complejidad del dot: una docena de formas (círculos, arcos con
trazo, degradados), una sombra grande y una matriz de color como la de
`saturate(0.4) brightness(0.82)`.

Modos (los resultados salen como JSON por la salida estándar o a `--salida`):

    python3 herramientas/dot_rendimiento.py --talla 56 --duracion 20
    python3 herramientas/dot_rendimiento.py --talla 250 --duracion 60 --salida r250.json
    python3 herramientas/dot_rendimiento.py --talla 56 --duracion 20 --sin-animar   # línea base
    python3 herramientas/dot_rendimiento.py --comprobar                              # firmas y ticks

La CPU se expresa como porcentaje de UN núcleo (100 % = un núcleo entero ocupado) y es la del
proceso entero, todos sus hilos (`time.process_time`). La línea base es la misma ventana con el
widget dibujado una vez y sin animar; la CPU del widget es la resta. La RSS sale de
`/proc/self/statm` al principio, cada pocos segundos y al final.

Necesita GTK 4 y pantalla. Sin ellas sale con código 2 y lo dice.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time

TALLAS = (56, 250)
PAGINA = os.sysconf("SC_PAGE_SIZE")


def rss_kib() -> int:
    """Memoria residente del proceso, en KiB."""
    with open("/proc/self/statm") as f:
        return int(f.read().split()[1]) * PAGINA // 1024


def matriz_saturar_oscurecer(saturacion: float, brillo: float) -> list[float]:
    """Los 16 números de `saturate(s) brightness(b)` de CSS, listos para `Graphene.Matrix`.

    La saturación es la matriz de luminancia de la especificación de filtros; el brillo
    multiplica los tres canales. Graphene guarda la matriz por columnas y GSK multiplica el
    color como vector fila, así que lo que va aquí es la transpuesta de la matriz de la
    especificación. El alfa pasa tal cual.
    """
    s = saturacion
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    css = [
        [lr + (1 - lr) * s, lg - lg * s, lb - lb * s],
        [lr - lr * s, lg + (1 - lg) * s, lb - lb * s],
        [lr - lr * s, lg - lg * s, lb + (1 - lb) * s],
    ]
    filas = [[v * brillo for v in fila] + [0.0] for fila in css] + [[0.0, 0.0, 0.0, 1.0]]
    # Transpuesta, aplanada de fila en fila: la columna j de css es la fila j de graphene.
    return [filas[i][j] for j in range(4) for i in range(4)]


def definir_widget(Gtk, Gdk, Gsk, Graphene, GLib):
    """Construye la clase del widget. Va en una función para no importar GTK al cargar el módulo
    (la herramienta y sus pruebas deben poder importarse en el CI sin GTK)."""

    class DotPrueba(Gtk.Widget):
        """Un círculo de color con una docena de formas, sombra grande y matriz de color."""

        __gtype_name__ = "DotPrueba"

        def __init__(self, talla: int, animar: bool = True):
            super().__init__()
            self.talla = talla
            self.animar = animar
            self.t = 0.0
            self.fotogramas = 0      # veces que GTK llamó a do_snapshot
            self.snapshot_s = 0.0    # tiempo total dentro de do_snapshot (el código Python)
            self.ticks = 0           # veces que se ejecutó el tick
            self._tick = 0           # id de add_tick_callback, 0 si no hay
            self._inicio = None
            self.set_size_request(talla, talla)
            self.set_halign(Gtk.Align.CENTER)
            self.set_valign(Gtk.Align.CENTER)
            self._sombra = Gsk.Shadow()
            self._sombra.color = Gdk.RGBA(0, 0, 0, 0.45)
            self._sombra.dx = 0
            self._sombra.dy = talla * 0.06
            self._sombra.radius = talla * 0.18
            self._matriz = Graphene.Matrix()
            self._matriz.init_from_float(matriz_saturar_oscurecer(0.4, 0.82))
            self._desfase = Graphene.Vec4()
            self._desfase.init(0, 0, 0, 0)
            self._ajustes = Gtk.Settings.get_default()
            self._ajustes.connect("notify::gtk-enable-animations", self._cambio_ajuste)

        # --- tick: solo corre si el widget está mapeado y las animaciones están activas ---

        def _debe_animar(self) -> bool:
            return (self.animar and self.get_mapped()
                    and self._ajustes.get_property("gtk-enable-animations"))

        def _sincronizar_tick(self):
            if self._debe_animar() and not self._tick:
                self._inicio = None
                self._tick = self.add_tick_callback(self._al_tick)
            elif not self._debe_animar() and self._tick:
                self.remove_tick_callback(self._tick)
                self._tick = 0

        def _cambio_ajuste(self, *_):
            self._sincronizar_tick()

        def do_map(self):
            Gtk.Widget.do_map(self)
            self._sincronizar_tick()

        def do_unmap(self):
            self._sincronizar_tick_apagado()
            Gtk.Widget.do_unmap(self)

        def _sincronizar_tick_apagado(self):
            if self._tick:
                self.remove_tick_callback(self._tick)
                self._tick = 0

        def do_measure(self, orientation, for_size):
            return self.talla, self.talla, -1, -1

        def _al_tick(self, widget, reloj):
            us = reloj.get_frame_time()
            if self._inicio is None:
                self._inicio = us
            self.t = (us - self._inicio) / 1e6
            self.ticks += 1
            self.queue_draw()
            return GLib.SOURCE_CONTINUE

        # --- dibujo ---

        def do_snapshot(self, snapshot):
            inicio = time.perf_counter()
            self.fotogramas += 1
            ancho, alto = self.get_width(), self.get_height()
            area = Graphene.Rect().init(0, 0, ancho, alto)
            snapshot.push_color_matrix(self._matriz, self._desfase)
            snapshot.push_shadow([self._sombra])
            cr = snapshot.append_cairo(area)
            self._dibujar(cr, ancho, alto)
            snapshot.pop()   # sombra
            snapshot.pop()   # matriz de color
            self.snapshot_s += time.perf_counter() - inicio

        def _dibujar(self, cr, ancho, alto):
            """Una docena de formas que se mueven con `self.t`."""
            import cairo

            u = min(ancho, alto) / 100.0
            cr.translate(ancho / 2, alto / 2)
            cr.scale(u, u)
            t = self.t
            # 1. Cuerpo: círculo con degradado radial.
            g = cairo.RadialGradient(-10, -12, 4, 0, 0, 38)
            g.add_color_stop_rgb(0, 0.62, 0.90, 0.55)
            g.add_color_stop_rgb(1, 0.18, 0.62, 0.40)
            cr.set_source(g)
            cr.arc(0, 0, 36 + 1.5 * math.sin(t * 2.0), 0, 2 * math.pi)
            cr.fill()
            # 2. Aro exterior que gira, en dos arcos.
            cr.set_line_width(4)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(0.95, 0.97, 0.90, 0.9)
            cr.arc(0, 0, 44, t, t + 1.6)
            cr.stroke()
            cr.arc(0, 0, 44, t + math.pi, t + math.pi + 1.6)
            cr.stroke()
            # 3. Ojos: dos píldoras que parpadean.
            parpadeo = max(0.15, abs(math.cos(t * 0.9)) ** 8)
            cr.set_source_rgb(0.08, 0.20, 0.14)
            for x in (-13, 13):
                cr.save()
                cr.translate(x, -6)
                cr.scale(1, parpadeo)
                cr.arc(0, 0, 6, 0, 2 * math.pi)
                cr.fill()
                cr.restore()
            # 4. Mechón-check: una polilínea con trazo grueso.
            cr.set_line_width(6)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.set_source_rgba(0.98, 0.98, 0.92, 1)
            cr.move_to(-14, 14)
            cr.line_to(-5, 22 + 2 * math.sin(t * 3))
            cr.line_to(16, 4)
            cr.stroke()
            # 5. Seis chispas en órbita, con alfa distinto.
            for i in range(6):
                a = t * 1.3 + i * math.pi / 3
                r = 48 + 3 * math.sin(t * 2 + i)
                cr.set_source_rgba(1, 1, 1, 0.35 + 0.1 * i)
                cr.arc(r * math.cos(a), r * math.sin(a), 2.2, 0, 2 * math.pi)
                cr.fill()
            # 6. Brillo: una elipse suave arriba a la izquierda.
            cr.save()
            cr.translate(-14, -22)
            cr.rotate(-0.5)
            cr.scale(1.6, 1)
            cr.arc(0, 0, 8, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 0.28)
            cr.fill()
            cr.restore()

    return DotPrueba


def _importar_gtk():
    """Importa GTK 4 o devuelve None si no está o no hay pantalla."""
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("Gsk", "4.0")
        gi.require_version("Graphene", "1.0")
        from gi.repository import GLib, Gdk, Graphene, Gsk, Gtk
    except (ImportError, ValueError):
        return None
    if not Gtk.init_check():
        return None
    return Gtk, Gdk, Gsk, Graphene, GLib


def _correr(GLib, segundos: float):
    """Deja correr el bucle principal `segundos` segundos."""
    bucle = GLib.MainLoop()
    GLib.timeout_add(int(segundos * 1000), lambda: bucle.quit() or False)
    bucle.run()


def medir(talla: int, duracion: float, animar: bool = True) -> dict:
    """Abre una ventana con el widget y mide CPU y memoria durante `duracion` segundos."""
    modulos = _importar_gtk()
    if modulos is None:
        raise SystemExit("sin GTK 4 o sin pantalla: no se puede medir")
    Gtk, Gdk, Gsk, Graphene, GLib = modulos
    Dot = definir_widget(Gtk, Gdk, Gsk, Graphene, GLib)
    ventana = Gtk.Window(title="Dot D3")
    dot = Dot(talla, animar)
    marco = Gtk.Box()
    marco.set_margin_top(24)
    marco.set_margin_bottom(24)
    marco.set_margin_start(24)
    marco.set_margin_end(24)
    marco.append(dot)
    ventana.set_child(marco)
    ventana.set_default_size(talla + 48, talla + 48)
    ventana.present()
    # Se deja que la ventana se asiente (mapeo, primeros fotogramas) antes de medir.
    _correr(GLib, 2.0)
    gc.collect()
    rss_ini = rss_kib()
    objetos_ini = len(gc.get_objects())
    ticks_ini, fotos_ini, snap_ini = dot.ticks, dot.fotogramas, dot.snapshot_s
    cpu_ini, pared_ini = time.process_time(), time.monotonic()
    muestras = [{"s": 0.0, "rss_kib": rss_ini}]
    paso = max(1.0, min(5.0, duracion / 12))
    transcurrido = 0.0
    while transcurrido < duracion:
        espera = min(paso, duracion - transcurrido)
        _correr(GLib, espera)
        transcurrido += espera
        muestras.append({"s": round(transcurrido, 1), "rss_kib": rss_kib()})
    cpu = time.process_time() - cpu_ini
    pared = time.monotonic() - pared_ini
    gc.collect()
    rss_fin = rss_kib()
    objetos_fin = len(gc.get_objects())
    fotogramas = dot.fotogramas - fotos_ini
    resultado = {
        "talla": talla,
        "animar": animar,
        "duracion_s": round(pared, 2),
        "cpu_pct_de_un_nucleo": round(100 * cpu / pared, 2),
        "fotogramas": fotogramas,
        "ticks": dot.ticks - ticks_ini,
        "fps": round(fotogramas / pared, 1),
        "do_snapshot_us_por_fotograma": round(
            1e6 * (dot.snapshot_s - snap_ini) / fotogramas, 1) if fotogramas else 0,
        "rss_inicial_kib": rss_ini,
        "rss_final_kib": rss_fin,
        "rss_crecimiento_kib": rss_fin - rss_ini,
        "objetos_python_inicial": objetos_ini,
        "objetos_python_final": objetos_fin,
        "muestras": muestras,
        "nucleos": os.cpu_count(),
        "gtk": f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
    }
    ventana.destroy()
    _correr(GLib, 0.2)
    return resultado


def comprobar() -> dict:
    """Las comprobaciones de comportamiento, rápidas: firmas, tick parado sin mapear, tick
    parado con `gtk-enable-animations` apagado y tick vivo en el caso normal."""
    modulos = _importar_gtk()
    if modulos is None:
        raise SystemExit("sin GTK 4 o sin pantalla: no se puede comprobar")
    Gtk, Gdk, Gsk, Graphene, GLib = modulos
    Dot = definir_widget(Gtk, Gdk, Gsk, Graphene, GLib)
    ajustes = Gtk.Settings.get_default()
    previo = ajustes.get_property("gtk-enable-animations")
    res = {}

    # Sin mostrar: ni mapeado ni tick.
    suelto = Dot(56)
    _correr(GLib, 0.3)
    res["sin_mostrar_ticks"] = suelto.ticks
    res["sin_mostrar_tick_activo"] = bool(suelto._tick)

    ventana = Gtk.Window()
    dot = Dot(56)
    ventana.set_child(dot)
    ventana.present()
    _correr(GLib, 0.6)
    res["visible_ticks"] = dot.ticks
    res["visible_tick_activo"] = bool(dot._tick)

    # Ventana oculta: el widget se desmapea y el tick se retira.
    ventana.set_visible(False)
    _correr(GLib, 0.2)
    res["oculto_mapeado"] = dot.get_mapped()
    res["oculto_tick_activo"] = bool(dot._tick)
    antes = dot.ticks
    _correr(GLib, 0.4)
    res["oculto_ticks_nuevos"] = dot.ticks - antes

    # Se muestra otra vez: el tick vuelve.
    ventana.set_visible(True)
    _correr(GLib, 0.4)
    res["reaparece_tick_activo"] = bool(dot._tick)

    # Animaciones apagadas con el widget a la vista: el tick se para y se pinta una vez al menos.
    ajustes.set_property("gtk-enable-animations", False)
    _correr(GLib, 0.2)
    res["sin_animaciones_tick_activo"] = bool(dot._tick)
    antes = dot.ticks
    _correr(GLib, 0.4)
    res["sin_animaciones_ticks_nuevos"] = dot.ticks - antes
    # Y se reanuda al encenderlas.
    ajustes.set_property("gtk-enable-animations", True)
    _correr(GLib, 0.3)
    res["con_animaciones_otra_vez_tick_activo"] = bool(dot._tick)
    ajustes.set_property("gtk-enable-animations", previo)

    # Firmas reales.
    snap = Gtk.Snapshot()
    snap.push_color_matrix(dot._matriz, dot._desfase)
    snap.push_shadow([dot._sombra])
    cr = snap.append_cairo(Graphene.Rect().init(0, 0, 56, 56))
    res["append_cairo_devuelve"] = type(cr).__module__ + "." + type(cr).__name__
    snap.pop()
    snap.pop()
    nodo = snap.to_node()
    res["nodo_raiz"] = type(nodo).__name__ if nodo is not None else None
    res["firmas"] = {
        "push_shadow": "Gtk.Snapshot.push_shadow(shadow: list[Gsk.Shadow])",
        "push_color_matrix": "Gtk.Snapshot.push_color_matrix(color_matrix: Graphene.Matrix, "
                             "color_offset: Graphene.Vec4)",
        "append_cairo": "Gtk.Snapshot.append_cairo(bounds: Graphene.Rect) -> cairo.Context",
    }
    ventana.destroy()
    return res


def _argumentos(argv=None):
    p = argparse.ArgumentParser(description="Prueba de rendimiento del dot (D3).")
    p.add_argument("--talla", type=int, default=56, help="lado del widget en px (56 o 250)")
    p.add_argument("--duracion", type=float, default=20, help="segundos de medición")
    p.add_argument("--sin-animar", action="store_true",
                   help="línea base: el widget se dibuja una vez y no hay tick")
    p.add_argument("--comprobar", action="store_true",
                   help="comprueba firmas y que el tick se pare (rápido, sin medir CPU)")
    p.add_argument("--salida", help="archivo donde escribir el JSON (si no, la salida estándar)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = _argumentos(argv)
    if _importar_gtk() is None:
        print("sin GTK 4 o sin pantalla: no se puede correr la prueba", file=sys.stderr)
        return 2
    resultado = comprobar() if a.comprobar else medir(a.talla, a.duracion, not a.sin_animar)
    texto = json.dumps(resultado, indent=2, ensure_ascii=False)
    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
