"""La pestaña Inicio en el board de verdad (v1.3.0): abre antes que el tablero.

Prueba de humo con GTK y pantalla (sin ellas se salta), sobre un vault de mentira: el board
abre en Inicio con el titular y una tarjeta por proyecto; «Nuevo proyecto» de momento avisa;
una tarjeta lleva al tablero con su proyecto elegido; y sin de dónde leer abre en el tablero,
donde está la explicación del primer arranque. La lógica de lo que se enseña se prueba sin
GTK en `test_resumen_inicio.py`.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app  # antes que gi.repository: pide las versiones de GTK 4
    from tareas.app import pestana_inicio
    from gi.repository import Gio, GLib, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def girar(ms=60):
    contexto = GLib.MainContext.default()
    limite = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < limite:
        contexto.iteration(False)


def textos(widget, acumulado=None):
    acumulado = [] if acumulado is None else acumulado
    if isinstance(widget, Gtk.Label) and widget.get_label():
        acumulado.append(widget.get_label())
    hijo = widget.get_first_child()
    while hijo is not None:
        textos(hijo, acumulado)
        hijo = hijo.get_next_sibling()
    return acumulado


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class PestanaInicio(unittest.TestCase):
    apps = 0
    con_vault = True

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        entorno = {"COTEJO_CONFIG": str(raiz / "config.json"), "COTEJO_ESTADO": str(raiz / "estado")}
        if self.con_vault:
            (raiz / "vault" / "01-Proyectos").mkdir(parents=True)
            for nombre, lineas in (("Faro", "- [ ] Uno\n- [ ] Dos #por-validar\n"),
                                   ("Horizonte", "- [ ] Tres\n")):
                (raiz / "vault" / "01-Proyectos" / f"{nombre}.md").write_text(
                    f"---\ntipo: proyecto\n---\n\n# {nombre}\n\n{lineas}", encoding="utf-8")
            entorno["COTEJO_VAULT"] = str(raiz / "vault")
        else:
            entorno["COTEJO_FUENTE"] = "repo"   # una fuente de repos sin ninguno: primer arranque
        parche = mock.patch.dict(os.environ)
        parche.start()
        self.addCleanup(parche.stop)
        for var in ("COTEJO_REPOS", "COTEJO_RAIZ_REPOS", "COTEJO_FUENTE", "COTEJO_VAULT"):
            os.environ.pop(var, None)
        os.environ.update(entorno)
        parche = mock.patch.object(app.App, "poner_lo_del_usuario", return_value=None)
        parche.start()
        self.addCleanup(parche.stop)

        ajustes = Gtk.Settings.get_default()
        antes = ajustes.get_property("gtk-enable-animations")
        ajustes.set_property("gtk-enable-animations", False)
        self.addCleanup(ajustes.set_property, "gtk-enable-animations", antes)

        self.app = app.App()
        PestanaInicio.apps += 1
        self.app.set_application_id(f"io.github.cotejoapp.CotejoPruebaInicio{os.getpid()}n{self.apps}")
        self.app.set_flags(self.app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        self.app.register(None)
        self.addCleanup(self.cerrar)
        self.app.desde_cero = False
        self.app.abrir_board()
        self.board = self.app.board
        girar()

    def cerrar(self):
        for monitor in self.app.monitores:
            monitor.cancel()
        if self.app.board is not None:
            self.app.board.destroy()
        self.app.release()


class ConProyectos(PestanaInicio):
    def test_abre_en_inicio_con_el_resumen_y_una_tarjeta_por_proyecto(self):
        b = self.board
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        self.assertTrue(b.botones_pestana[pestana_inicio.INICIO].get_active())
        self.assertFalse(b.banda_proyectos.get_visible())
        self.assertFalse(b.buscador.get_visible())
        todo = textos(b.pestanas.get_child_by_name(pestana_inicio.INICIO))
        self.assertIn("Tienes 2 proyectos y 1 entrega por comprobar", todo)
        self.assertIn("1 por comprobar", todo)
        self.assertIn("sin arquitectura todavía", todo)
        self.assertIn("Empezar un proyecto", todo)
        # Faro (con una entrega por comprobar) primero; «Nuevo proyecto» al final.
        nombres = [t for t in todo if t in ("Faro", "Horizonte")]
        self.assertEqual(nombres, ["Faro", "Horizonte"])
        # El hueco de la constelación existe y está vacío hasta que llegue.
        self.assertFalse(b.area_constelacion.get_visible())
        b.poner_constelacion(Gtk.Label(label="constelación"))
        self.assertTrue(b.area_constelacion.get_visible())

    def test_nuevo_proyecto_de_momento_avisa(self):
        with mock.patch.object(self.board, "aviso") as aviso:
            self.board.nuevo_proyecto()
        aviso.assert_called_once_with(pestana_inicio.AVISO_NUEVO)

    def test_una_tarjeta_lleva_al_tablero_con_su_proyecto(self):
        b = self.board
        b.abrir_proyecto("Horizonte")
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.TABLERO)
        self.assertEqual(b.seleccion, "Horizonte")
        self.assertTrue(b.banda_proyectos.get_visible())
        self.assertTrue(b.buscador.get_visible())
        # Y el selector de la cabecera vuelve a Inicio.
        b.botones_pestana[pestana_inicio.INICIO].set_active(True)
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def test_buscar_lleva_al_tablero(self):
        self.app.buscar()
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


class SinFuente(PestanaInicio):
    con_vault = False

    def test_sin_de_donde_leer_abre_en_el_tablero(self):
        self.assertIsNotNone(self.board.fuente.problema)
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


if __name__ == "__main__":
    unittest.main()
