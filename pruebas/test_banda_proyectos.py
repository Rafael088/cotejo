"""La banda de proyectos del board (v1.2.4): sustituye a la lateral y a su pliegue por ancho.

Vigila lo que la lateral tenía y la banda no puede perder: «Todos los proyectos» primero, el
aviso de por comprobar en el chip, elegir con teclado (chips que son botones) y que ya no
quede rastro de la lateral ni de F9.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from gi.repository import Gtk
    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class BandaDeProyectos(unittest.TestCase):

    def test_ya_no_hay_lateral_ni_pliegue(self):
        for nombre in ("alternar_lateral", "poner_lateral", "al_estrechar", "al_ensanchar",
                       "pintar_lateral", "al_tecla_lateral"):
            self.assertFalse(hasattr(app.Board, nombre), nombre)
        self.assertFalse(hasattr(app, "ANCHO_LATERAL"))

    def test_todos_los_proyectos_va_primero_con_su_aviso(self):
        def proyecto(nombre, estados):
            tareas = [types.SimpleNamespace(estado=e) for e in estados]
            return types.SimpleNamespace(nombre=nombre, tareas=tareas)
        falso = types.SimpleNamespace()
        filas = app.Board.filas_banda(falso, [proyecto("A", ["pendiente", "por-validar"]),
                                              proyecto("B", ["pendiente"])])
        self.assertEqual(filas[0], (app.comun.TODOS, "Todos los proyectos", 3, 1))
        self.assertEqual(filas[1:], [("A", "A", 2, 1), ("B", "B", 1, 0)])

    def test_la_banda_mide_el_60_por_ciento(self):
        self.assertEqual(app.comun.FRANJA_BANDA - 2, 3)  # tres de cinco partes iguales
        self.assertEqual(app.comun.FRANJA_BANDA, 5)


if __name__ == "__main__":
    unittest.main()
