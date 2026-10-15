"""La animación de arranque del board (cotejo-o7mpws): la C se dibuja y el check entra.

La línea de tiempo y la geometría se prueban sin GTK; el fotograma, con cairo si está; y el
paso del logo al board, con GTK y pantalla (si no, se salta).
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import marca

try:
    from gi.repository import GLib, Gtk

    from tareas import app, temas
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False

try:
    import cairo
except ImportError:
    cairo = None


class LineaDeTiempo(unittest.TestCase):
    def test_empieza_vacia_y_acaba_con_el_logo_entero(self):
        self.assertEqual(marca.trazos(0), (0, 0))
        self.assertEqual(marca.trazos(1), (1, 1))

    def test_primero_la_c_y_el_check_entra_cuando_se_esta_cerrando(self):
        c, check = marca.trazos(0.3)
        self.assertGreater(c, 0.5)
        self.assertEqual(check, 0)
        c, check = marca.trazos(0.55)
        self.assertLess(c, 1)
        self.assertGreater(check, 0)

    def test_nunca_retrocede(self):
        anteriores = (0, 0)
        for paso in range(101):
            ahora = marca.trazos(paso / 100)
            self.assertGreaterEqual(ahora[0], anteriores[0])
            self.assertGreaterEqual(ahora[1], anteriores[1])
            anteriores = ahora

    def test_no_retrasa_el_arranque_mas_de_800_ms(self):
        self.assertLessEqual(marca.ARRANQUE_MS + marca.FUNDIDO_MS, 800)


class Geometria(unittest.TestCase):
    def test_la_c_va_de_la_punta_de_abajo_a_la_boca_sin_cerrarse(self):
        desde, recorre = marca.barrido(marca.LETRA)
        self.assertAlmostEqual(desde, 0.5236, places=3)   # 30°, la punta de abajo
        self.assertGreater(recorre, 4.0)                  # más de 3/4 de vuelta
        self.assertLess(recorre, 6.0)                     # y deja la boca abierta


@unittest.skipUnless(HAY_GTK and cairo, "sin GTK o sin cairo no se dibuja el fotograma")
class Fotograma(unittest.TestCase):
    def pixel(self, t, x, y):
        superficie = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        app.piezas.dibujar_arranque(cairo.Context(superficie), 200, 200, t,
                             temas.cargar(temas.DEFECTO)["colores"])
        datos = superficie.get_data()
        i = y * superficie.get_stride() + x * 4
        return datos[i + 3]   # alfa: si hay algo pintado ahí

    def en_pantalla(self, x, y):
        """Un punto del logo (unidades de Sora) en el área de 200×200, como lo dibuja."""
        x0, y0, x1, y1 = marca.caja(marca.LETRA)
        escala = app.comun.LADO_ARRANQUE / max(x1 - x0, y1 - y0)
        return (round(100 + (x - (x0 + x1) / 2) * escala),
                round(100 + (y - (y0 + y1) / 2) * escala))

    def test_al_principio_no_hay_nada_y_al_final_estan_la_c_y_el_check(self):
        (cx, cy), r = marca.LETRA["centro"], marca.LETRA["radio"]
        abajo_de_la_c = self.en_pantalla(cx, cy + r)
        (ax, ay), (bx, by) = marca.LETRA["check"][1:]
        brazo = self.en_pantalla((ax + bx) / 2, (ay + by) / 2)
        for punto in (abajo_de_la_c, brazo):
            self.assertEqual(self.pixel(0, *punto), 0)
            self.assertEqual(self.pixel(1, *punto), 255)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se construye la pila")
class DelLogoAlBoard(unittest.TestCase):
    def test_al_terminar_se_ve_el_board_y_el_logo_se_va(self):
        entradas = []
        falso = types.SimpleNamespace(app=types.SimpleNamespace(
            colores=temas.cargar(temas.DEFECTO)["colores"]),
            entrar_dot=lambda: entradas.append(True))
        falso.pila = Gtk.Stack()
        falso.pila.add_named(Gtk.Label(label="el board"), "board")
        app.Board.mostrar_arranque(falso)
        contexto = GLib.MainContext.default()
        limite = GLib.get_monotonic_time() + 3_000_000
        while falso.animacion_arranque is not None and GLib.get_monotonic_time() < limite:
            contexto.iteration(False)
        self.assertIsNone(falso.animacion_arranque)
        self.assertEqual(falso.pila.get_visible_child_name(), "board")
        limite = GLib.get_monotonic_time() + 1_000_000
        while falso.pila.get_child_by_name("arranque") and GLib.get_monotonic_time() < limite:
            contexto.iteration(False)
        self.assertIsNone(falso.pila.get_child_by_name("arranque"))
        # El dot entra después del logo, cuando el board ya se ve (D5).
        limite = GLib.get_monotonic_time() + 1_000_000
        while not entradas and GLib.get_monotonic_time() < limite:
            contexto.iteration(False)
        self.assertEqual(entradas, [True])


if __name__ == "__main__":
    unittest.main()
