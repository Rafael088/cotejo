"""La prueba de rendimiento del dot (D3): la matriz de color sin GTK, y con GTK y pantalla que
el tick se pare sin mapear y con las animaciones apagadas y que las firmas de PyGObject sean
las esperadas. Las mediciones largas no están aquí: se corren a mano (docs/dot/rendimiento.md).
"""

import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from herramientas import dot_rendimiento

try:
    from gi.repository import Gdk, Gtk

    # init_check() da True sin DISPLAY ni WAYLAND_DISPLAY: hace falta una pantalla de verdad.
    HAY_GTK = Gtk.init_check() and Gdk.Display.get_default() is not None
except (ImportError, ValueError):
    HAY_GTK = False


class MatrizDeColor(unittest.TestCase):
    def columnas(self, plano):
        """La matriz como lista de columnas, que es como la guarda Graphene."""
        return [plano[i * 4:(i + 1) * 4] for i in range(4)]

    def test_sin_saturar_ni_oscurecer_es_la_identidad(self):
        plano = dot_rendimiento.matriz_saturar_oscurecer(1.0, 1.0)
        for i, valor in enumerate(plano):
            self.assertAlmostEqual(valor, 1.0 if i % 5 == 0 else 0.0, places=6)

    def test_el_gris_se_queda_gris_y_el_brillo_lo_oscurece(self):
        plano = dot_rendimiento.matriz_saturar_oscurecer(0.4, 0.82)
        cols = self.columnas(plano)
        # Un gris (0.5, 0.5, 0.5) con saturate no cambia; con brightness(0.82) pasa a 0.41.
        for fila in range(3):
            self.assertAlmostEqual(sum(cols[c][fila] for c in range(3)) * 0.5, 0.41, places=4)

    def test_el_alfa_pasa_tal_cual(self):
        cols = self.columnas(dot_rendimiento.matriz_saturar_oscurecer(0.4, 0.82))
        self.assertEqual(cols[3], [0.0, 0.0, 0.0, 1.0])


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se construye el widget")
class WidgetConGtk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = dot_rendimiento.comprobar()

    def test_sin_mostrar_no_hay_tick(self):
        self.assertEqual(self.r["sin_mostrar_ticks"], 0)
        self.assertFalse(self.r["sin_mostrar_tick_activo"])

    def test_a_la_vista_el_tick_corre(self):
        self.assertGreater(self.r["visible_ticks"], 5)
        self.assertTrue(self.r["visible_tick_activo"])

    def test_oculto_el_tick_se_para_y_al_volver_se_reanuda(self):
        self.assertFalse(self.r["oculto_mapeado"])
        self.assertFalse(self.r["oculto_tick_activo"])
        self.assertEqual(self.r["oculto_ticks_nuevos"], 0)
        self.assertTrue(self.r["reaparece_tick_activo"])

    def test_sin_animaciones_no_hay_tick(self):
        self.assertFalse(self.r["sin_animaciones_tick_activo"])
        self.assertEqual(self.r["sin_animaciones_ticks_nuevos"], 0)
        self.assertTrue(self.r["con_animaciones_otra_vez_tick_activo"])

    def test_las_firmas_de_pygobject(self):
        self.assertEqual(self.r["append_cairo_devuelve"], "cairo.Context")
        self.assertEqual(self.r["nodo_raiz"], "ColorMatrixNode")


if __name__ == "__main__":
    unittest.main()
