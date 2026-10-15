"""Una ventana estrecha (1430 px) deja ver las cuatro columnas del tablero (v1.2.4)."""

import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas.app import comun
except (ImportError, ValueError):  # sin GTK (el job pruebas-sin-gtk de la CI)
    comun = None


def pide(anchos):
    return sum(anchos.values()) + 3 * comun.ESPACIADO_SM + 2 * comun.MARGEN_TABLERO_LADOS


@unittest.skipIf(comun is None, "sin GTK no se carga tareas.app")
class TableroEstrecho(unittest.TestCase):
    def test_a_1430_las_cuatro_columnas_caben(self):
        self.assertLessEqual(pide(comun.anchos_columnas(1430)), 1430)

    def test_a_pantalla_completa_nada_cambia(self):
        for ancho in (1900, 2560):
            self.assertEqual(comun.anchos_columnas(ancho), comun.ANCHO_COLUMNAS)

    def test_nunca_baja_de_los_pisos_ni_toca_el_riel(self):
        anchos = comun.anchos_columnas(500)
        for clave, piso in comun.ANCHO_MINIMO_COLUMNAS.items():
            self.assertGreaterEqual(anchos[clave], piso)
        self.assertEqual(anchos["hecha"], comun.ANCHO_RIEL)

    def test_ventana_real_a_1430_llega_a_la_ultima_columna(self):
        try:
            from gi.repository import Gtk
            if not Gtk.init_check():
                self.skipTest("sin pantalla")
        except (ImportError, ValueError):
            self.skipTest("sin GTK")
        tablero = Gtk.Box(spacing=comun.ESPACIADO_SM, halign=Gtk.Align.CENTER,
                          margin_start=comun.MARGEN_TABLERO_LADOS,
                          margin_end=comun.MARGEN_TABLERO_LADOS)
        for ancho in comun.anchos_columnas(1430).values():
            caja = Gtk.Box()
            caja.set_size_request(ancho, -1)
            tablero.append(caja)
        scroll = Gtk.ScrolledWindow(child=tablero, hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        # Se le da el ancho a mano: un gestor de ventanas con mosaico no respeta 1430.
        scroll.allocate(1430, 600, -1, None)
        ajuste = scroll.get_hadjustment()
        self.assertEqual(ajuste.get_page_size(), 1430)
        self.assertLessEqual(ajuste.get_upper(), ajuste.get_page_size())
        # Y con los anchos de pantalla completa sí haría falta desplazarse: la prueba mide algo.
        sin_ajuste = Gtk.Box(spacing=comun.ESPACIADO_SM, margin_start=comun.MARGEN_TABLERO_LADOS,
                             margin_end=comun.MARGEN_TABLERO_LADOS)
        for ancho in comun.ANCHO_COLUMNAS.values():
            caja = Gtk.Box()
            caja.set_size_request(ancho, -1)
            sin_ajuste.append(caja)
        scroll2 = Gtk.ScrolledWindow(child=sin_ajuste)
        scroll2.allocate(1430, 600, -1, None)
        self.assertGreater(scroll2.get_hadjustment().get_upper(), 1430)


if __name__ == "__main__":
    unittest.main()
