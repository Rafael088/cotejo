"""Las columnas del tablero miden un ancho fijo y un texto largo no las ensancha (7.3.3).

Se salta sin GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import modelo

try:
    from gi.repository import Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False

LARGO = "palabra" * 40 + " " + "y otra cosa bastante larga " * 8


def hijos(widget):
    hijo = widget.get_first_child()
    while hijo is not None:
        yield hijo
        yield from hijos(hijo)
        hijo = hijo.get_next_sibling()


def tablero():
    falso = types.SimpleNamespace(
        columnas={},
        altura_encabezados=Gtk.SizeGroup(mode=Gtk.SizeGroupMode.VERTICAL),
        menu_filtro_finalizada=lambda b: None, presentar_finalizada=lambda: None,
        vigilar_teclas=lambda *a: None, al_activar=lambda *a: None, al_tecla_columna=lambda *a: None,
        al_entrar_arrastre=lambda *a: None, al_salir_arrastre=lambda *a: None,
        al_soltar=lambda *a: None,
        alias_persona=(), app=types.SimpleNamespace(bitacora={}),
        fuente=types.SimpleNamespace(accion_abrir="Abrir la nota"),
        menu=lambda p, t: Gtk.MenuButton(popover=Gtk.Popover()),
        arrastrable=lambda f: None, anotacion=lambda t: None,
        revision_en_carta=lambda p, t: Gtk.Label(label="revision"))
    falso.poner_nombre_riel = lambda: app.Board.poner_nombre_riel(falso)
    falso.chip_agente = types.MethodType(app.Board.chip_agente, falso)
    falso.motivo_en_espera = types.MethodType(app.Board.motivo_en_espera, falso)
    falso.detalles_de_carta = types.MethodType(app.Board.detalles_de_carta, falso)
    cajas = {clave: app.Board.columna(falso, i, clave, nombre)
             for i, (clave, nombre) in enumerate(modelo.COLUMNAS)}
    return falso, cajas


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir el tablero")
class ColumnasFijas(unittest.TestCase):
    def test_ancho_fijo_y_sin_hexpand(self):
        _f, cajas = tablero()
        esperado = {"pendiente": 354, "en-curso": 450, "por-validar": 540}
        for clave, ancho in esperado.items():
            self.assertEqual(cajas[clave].get_size_request()[0], ancho, clave)
        for clave, caja in cajas.items():
            self.assertFalse(caja.get_hexpand(), clave)

    def test_ninguna_carta_ensancha_su_columna(self):
        """El ancho fijo es un mínimo en GTK: lo que lo sostiene es que ninguna carta pida más.

        Visto en la captura del 2026-10-10: un id de ruta («01-Proyectos/…/Bot.md:45») sin
        recortar llevaba Pendiente de 354 a ~560 px.
        """
        falso, cajas = tablero()
        proyecto = types.SimpleNamespace(nombre="Uno")
        for clave in ("pendiente", "en-curso", "por-validar"):
            tarea = modelo.Tarea("v1.2.4 · " + LARGO + ": " + LARGO,
                                 id="01-Proyectos/Un proyecto con nombre largo/Nota.md:45",
                                 donde="Uno.md", estado=clave, agente="opus", dificultad="media")
            falso.columnas[clave][0].append(app.Board.carta(falso, proyecto, tarea))
            minimo, natural, _, _ = cajas[clave].measure(Gtk.Orientation.HORIZONTAL, -1)
            self.assertEqual(minimo, app.comun.ANCHO_COLUMNAS[clave], clave)

    def test_riel_de_52(self):
        self.assertEqual(app.comun.ANCHO_RIEL, 52)

    def test_margenes_del_tablero(self):
        self.assertEqual((app.comun.MARGEN_TABLERO_LADOS, app.comun.MARGEN_TABLERO_VERTICAL), (40, 28))

    def test_texto_larguisimo_no_ensancha_la_columna(self):
        falso, cajas = tablero()
        proyecto = types.SimpleNamespace(nombre="Uno")
        estados = {"pendiente": "pendiente", "en-curso": "en-curso", "por-validar": "por-validar"}
        for clave, estado in estados.items():
            tarea = modelo.Tarea(LARGO, id="cotejo-8y7t68", donde="Uno.md", estado=estado,
                                 agente="opus", dificultad="media")
            fila = app.Board.carta(falso, proyecto, tarea)
            lista = falso.columnas[clave][0]
            lista.append(fila)
            etiquetas = [h for h in hijos(fila) if isinstance(h, Gtk.Label)
                         and h.get_label() and "palabra" in h.get_label()]
            self.assertTrue(etiquetas, clave)
            for etiqueta in etiquetas:
                if clave == "pendiente":
                    # La compacta no envuelve: recorta el nombre con elipsis.
                    self.assertEqual(etiqueta.get_ellipsize().value_nick, "end", clave)
                else:
                    self.assertTrue(etiqueta.get_wrap(), clave)
                    self.assertEqual(etiqueta.get_ellipsize().value_nick, "none", clave)
                natural = etiqueta.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
                self.assertLessEqual(natural, app.comun.ANCHO_COLUMNAS[clave], clave)
            natural = cajas[clave].measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            self.assertEqual(natural, app.comun.ANCHO_COLUMNAS[clave], clave)


if __name__ == "__main__":
    unittest.main()
