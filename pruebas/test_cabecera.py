"""La cabecera de marca y la navegación entre pantallas."""

import unittest
from types import SimpleNamespace

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

    def test_el_titulo_de_pantalla_va_en_el_centro(self):
        self.assertIs(self.board.cabecera.get_title_widget(), self.board.titulo_pantalla)
        self.assertEqual(self.board.titulo_pantalla.get_label(), "")

    def test_titulo_central_de_cada_pantalla(self):
        b = self.board
        b.mapa_proyecto = ("Faro", "")
        b.plan_estado = {"proyecto": "Faro"}
        b.pantalla_preparando.vista = SimpleNamespace(proyecto="Faro")
        esperados = {"tablero": "Tablero", "equipo": "Tus agentes",
                     "entrevista": "Nuevo proyecto", "preparando": "Faro",
                     "plan": "Faro", "mapa": "Faro"}
        for pantalla, titulo in esperados.items():
            with self.subTest(pantalla=pantalla):
                self.assertEqual(b.titulo_de_pantalla(pantalla), titulo)

    def test_la_marca_no_dice_board(self):
        caja_marca = self.board.boton_inicio.get_parent().get_parent().get_parent()
        self.assertNotIn("Board", base.textos(caja_marca))
        self.assertEqual(self.board.logo.get_alternative_text(), "Cotejo")
        self.assertIn("flat", self.board.boton_inicio.get_css_classes())
        self.assertEqual(self.board.boton_inicio.get_tooltip_text(), "Inicio")

    def test_subtitulo_solo_en_tablero_y_volver_fuera_del_inicio(self):
        b = self.board
        self.assertFalse(b.subtitulo.get_visible())
        self.assertFalse(b.boton_volver.get_visible())
        b.ver_pestana("tablero")
        self.assertTrue(b.subtitulo.get_visible())
        self.assertTrue(b.boton_volver.get_visible())
        self.assertEqual(b.titulo_pantalla.get_label(), "Tablero")
        b.ver_pestana("entrevista")
        self.assertFalse(b.subtitulo.get_visible())
        self.assertTrue(b.boton_volver.get_visible())
        self.assertEqual(b.titulo_pantalla.get_label(), "Nuevo proyecto")


if __name__ == "__main__":
    unittest.main()
