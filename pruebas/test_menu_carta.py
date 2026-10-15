"""El menú de los 3 puntos de una carta tiene que caber en la ventana, tenga los modelos que tenga.

Un `Gtk.Popover` más alto que la ventana no se abre, y no da error: el clic simplemente no hace
nada. Pasó el 2026-09-26 con 34 modelos en el catálogo (ver «Bugs conocidos» en CLAUDE.md). La
lista «ASIGNAR A» crece con cada modelo que registra un cliente, así que lo que se vigila es que
el alto del menú no dependa de cuántos haya.

Construye el menú de verdad con un Board falso —solo lo que `menu()` lee—, sin abrir ventana.
Necesita GTK y una pantalla: sin ellas se salta en vez de tumbar la suite.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

try:
    from gi.repository import Gtk

    from tareas import app, modelo
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def board_falso(cuantos_modelos):
    falso = types.SimpleNamespace(
        orden=[clave for clave, _ in modelo.COLUMNAS],
        agentes=tuple(f"modelo-{i}" for i in range(cuantos_modelos)),
        alias_persona=("persona",),  # Alias de personas de la configuración
        app=types.SimpleNamespace(bitacora={}),
        fuente=types.SimpleNamespace(accion_abrir="Abrir la nota"),
        al_mover=None, al_asignar=None, al_ver=None)
    falso.opcion = types.MethodType(app.Board.opcion, falso)
    falso.lista_de_agentes = types.MethodType(app.Board.lista_de_agentes, falso)
    return falso


def menu_de(estado, cuantos_modelos=3):
    hecha = estado == modelo.HECHA
    tarea = modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="01-Proyectos/Uno.md",
                         estado="por-validar" if hecha else estado, hecha=hecha, agente="opus")
    return app.Board.menu(board_falso(cuantos_modelos), None, tarea).get_popover().get_child()


def alto_del_menu(cuantos_modelos):
    return menu_de("pendiente", cuantos_modelos).measure(Gtk.Orientation.VERTICAL, -1).natural


def textos(widget):
    if isinstance(widget, Gtk.Label):
        yield widget.get_label()
    hijo = widget.get_first_child()
    while hijo is not None:
        yield from textos(hijo)
        hijo = hijo.get_next_sibling()


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir el menú")
class ElMenuDeLaCartaCabe(unittest.TestCase):
    def test_el_alto_no_crece_con_los_modelos_del_catalogo(self):
        self.assertEqual(alto_del_menu(40), alto_del_menu(200))

    def test_cabe_en_una_ventana_pequena(self):
        # 720 px es una pantalla de portátil pequeña con la barra de arriba descontada.
        self.assertLess(alto_del_menu(200), 720)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir el menú")
class LoQueOfreceElMenu(unittest.TestCase):
    def test_no_ofrece_abrir_la_tarea_en_su_app(self):
        for estado in ("pendiente", "en-curso", "por-validar", "hecha"):
            self.assertFalse(any("Abrir" in t for t in textos(menu_de(estado))), estado)

    def test_en_finalizada_no_se_asigna(self):
        self.assertNotIn("ASIGNAR A", list(textos(menu_de("hecha"))))
        self.assertIn("ASIGNAR A", list(textos(menu_de("pendiente"))))



if __name__ == "__main__":
    unittest.main()
