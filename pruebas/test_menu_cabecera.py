"""El menú de la cabecera (⋮) se abre entero dentro de la ventana, no cortado en el borde derecho.

Que de verdad quepa solo se comprueba a ojo; aquí se fija la colocación que lo consigue:
debajo del botón y alineado a su borde derecho. Se salta sin GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from gi.repository import Gtk

    from tareas.app import ventana
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK")
class MenuCabecera(unittest.TestCase):
    def test_el_popover_se_abre_debajo_y_alineado_al_borde_derecho(self):
        falso = types.SimpleNamespace(ver_atajos=lambda: None, fila_tamano=lambda _p: Gtk.Box(),
                                      abrir_anadir_modelo=lambda: None)
        boton = ventana.Board.menu_cabecera(falso)
        popover = boton.get_popover()
        self.assertEqual(popover.get_position(), Gtk.PositionType.BOTTOM)
        self.assertEqual(popover.get_halign(), Gtk.Align.END)


if __name__ == "__main__":
    unittest.main()
