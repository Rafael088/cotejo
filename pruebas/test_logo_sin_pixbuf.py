"""El logo del board no pasa por el cargador de SVG de gdk-pixbuf (ni por GIO de archivos).

Antes `pintar_logo` hacía `Gdk.Texture.new_from_bytes(svg)`: pixbuf SVG → `g_file_delete` →
gvfs por dbus. Con gvfsd sin contestar, el board se quedaba sin ventana y sin error. Ahora el
logo se dibuja con cairo (`tareas/logo_dibujo.py`) y se sube como `Gdk.MemoryTexture`.

1. Solo pycairo: el dibujo pone la palabra y el check en los colores pedidos.
2. Con PyGObject (sin pantalla): `pintar_logo` funciona aunque el cargador de pixbuf, la
   textura desde bytes y el borrado de archivos de GIO exploten si alguien los toca.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

from apoyo import RAIZ

sys.path.insert(0, str(RAIZ))

try:
    import cairo
except ImportError:
    cairo = None

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Adw", "1")
    HAY_GTK = cairo is not None
except (ImportError, ValueError):
    HAY_GTK = False

SVG = (Path(RAIZ) / "data" / "marca" / "cotejo-logo.svg").read_text()


def pixeles(superficie):
    ancho, alto, paso = superficie.get_width(), superficie.get_height(), superficie.get_stride()
    datos = bytes(superficie.get_data())
    return {(x, y): datos[y * paso + x * 4:y * paso + x * 4 + 4]
            for y in range(alto) for x in range(ancho)}


@unittest.skipUnless(cairo, "sin pycairo")
class DibujoConCairo(unittest.TestCase):
    def test_pone_palabra_y_check_en_sus_colores(self):
        from tareas import logo_dibujo
        svg = SVG.replace("#FFFFFF", "#FF0000").replace("#16C98D", "#0000FF")
        px = pixeles(logo_dibujo.rasterizar(svg, 264)).values()
        rojos = sum(1 for b, g, r, a in px if a == 255 and r == 255 and g == 0 and b == 0)
        azules = sum(1 for b, g, r, a in px if a == 255 and b == 255 and r == 0 and g == 0)
        self.assertGreater(rojos, 800, "falta la palabra")
        self.assertGreater(azules, 100, "falta el check")

    def test_proporcion_del_viewbox(self):
        from tareas import logo_dibujo
        s = logo_dibujo.rasterizar(SVG, 348)
        self.assertEqual((s.get_width(), s.get_height()), (348, 117))

    def test_comando_desconocido_falla_claro(self):
        from tareas import logo_dibujo
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
        with self.assertRaises(ValueError):
            logo_dibujo.trazar(cairo.Context(s), "M0 0 C1 1 2 2 3 3")


class Falso:
    def __init__(self):
        self.contenido = "sin tocar"

    def set_paintable(self, p):
        self.contenido = p


@unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4/pycairo")
class SinPixbufNiGio(unittest.TestCase):
    def test_pintar_logo_no_usa_pixbuf_ni_borra_archivos(self):
        from gi.repository import Gdk, Gio, GdkPixbuf
        from tareas.app import piezas
        colores = {"texto": "#E8E8E8", "senal": "#16C98D"}
        logo = Falso()
        with mock.patch.object(Gdk.Texture, "new_from_bytes",
                               side_effect=AssertionError("pasó por el cargador de pixbuf")), \
                mock.patch.object(GdkPixbuf.PixbufLoader, "new_with_type",
                                  side_effect=AssertionError("cargador de pixbuf")), \
                mock.patch.object(GdkPixbuf.Pixbuf, "new_from_stream",
                                  side_effect=AssertionError("pixbuf desde stream")), \
                mock.patch.object(Gio.File, "delete",
                                  side_effect=AssertionError("GIO borró un archivo")):
            piezas.pintar_logo(logo, colores)
        self.assertIsInstance(logo.contenido, piezas.Logo)
        self.assertIsInstance(logo.contenido.textura, Gdk.MemoryTexture)
        self.assertGreater(logo.contenido.get_intrinsic_width(), logo.contenido.alto)


if __name__ == "__main__":
    unittest.main()
