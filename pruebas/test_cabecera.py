"""La cabecera no se pisa al crecer la letra (cotejo-hd82wk, v1.3.1).

El subtítulo de la marca es una frase que crece con la letra y con los proyectos. Antes no
podía encoger y empujaba las pestañas Inicio | Tablero hasta que se tocaban. Aquí se fija que
el subtítulo se recorta con elipsis, que el texto entero queda en su tooltip, y que las
pestañas viven en el hueco central de la cabecera y no pegadas al título.
"""

import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base

try:
    from gi.repository import Gtk, Pango

    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class Cabecera(base.PestanaInicio):
    def test_el_subtitulo_se_recorta_en_vez_de_empujar_las_pestanas(self):
        subtitulo = self.board.subtitulo
        self.assertEqual(subtitulo.get_ellipsize(), Pango.EllipsizeMode.END)
        self.assertFalse(subtitulo.get_wrap())
        self.assertEqual(subtitulo.get_tooltip_text(), subtitulo.get_label())

    def test_las_pestanas_van_en_el_hueco_central_de_la_cabecera(self):
        self.assertIs(self.board.cabecera.get_title_widget(), self.board.selector_pestanas)
        claves = [c for c in self.board.selector_pestanas.get_css_classes()]
        self.assertIn("pestanas", claves)

    def test_el_subtitulo_largo_no_pisa_las_pestanas(self):
        b = self.board
        b.subtitulo.set_label("Esperando que las compruebes · " * 8)
        base.girar(120)
        caja = b.subtitulo.get_parent().get_parent()
        ok_caja, c_caja = caja.compute_bounds(b.cabecera)
        ok_pestanas, c_pestanas = b.selector_pestanas.compute_bounds(b.cabecera)
        self.assertTrue(ok_caja and ok_pestanas)
        # El título acaba antes de que empiecen las pestañas, y las pestañas caben dentro.
        self.assertLessEqual(c_caja.get_x() + c_caja.get_width(), c_pestanas.get_x())
        self.assertLessEqual(c_pestanas.get_x() + c_pestanas.get_width(),
                             b.cabecera.get_width())
        # La elipsis hace su trabajo: el subtítulo ocupa menos de lo que mide entero.
        self.assertLess(b.subtitulo.get_width(), b.subtitulo.get_preferred_size()[1].width)


if __name__ == "__main__":
    unittest.main()
