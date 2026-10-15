"""El vacío del primer arranque: sin fuente configurada, qué es Cotejo y cómo empezar.

Se salta sin GTK. Sin repos ni carpeta no sale la tarjeta ámbar de «edita config.json»: sale
una explicación, el camino recomendado copiable y, con un vault de Obsidian, su comando.
Un repo que no existe sigue siendo un problema en ámbar. Y sin de dónde leer, el botón del
maestro se desactiva con tooltip.
"""

import os
import types
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app
    from tareas.app import primer_arranque
    from gi.repository import Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def textos(widget, acumulado=None):
    """Todos los textos de etiquetas y botones bajo un widget."""
    acumulado = [] if acumulado is None else acumulado
    if isinstance(widget, (Gtk.Label, Gtk.Button)) and widget.get_label():
        acumulado.append(widget.get_label())
    hijo = widget.get_first_child()
    while hijo is not None:
        textos(hijo, acumulado)
        hijo = hijo.get_next_sibling()
    return acumulado


def fuente_repo(**config):
    from tareas.fuentes.repo import Repo
    return Repo(config)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir la tarjeta")
class PrimerArranque(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.dict("os.environ")
        parche.start()
        self.addCleanup(parche.stop)
        for var in ("COTEJO_REPOS", "COTEJO_RAIZ_REPOS"):
            os.environ.pop(var, None)

    def test_sin_repos_ni_raiz_es_primer_arranque(self):
        self.assertTrue(primer_arranque.es_primer_arranque(fuente_repo()))

    def test_un_repo_que_no_existe_sigue_siendo_un_problema(self):
        fuente = fuente_repo(repos=["/no/existe/de/verdad"])
        self.assertIsNotNone(fuente.problema)
        self.assertFalse(primer_arranque.es_primer_arranque(fuente))

    def test_la_tarjeta_explica_y_da_los_comandos(self):
        caja = primer_arranque.vacio_de_arranque(lambda *_: None, vault=None)
        todo = " | ".join(textos(caja))
        self.assertIn("agentes de IA", todo)
        self.assertIn("Empieza un proyecto con Cotejo", todo)
        self.assertIn("cotejo init --repo <carpeta>", todo)
        self.assertNotIn("obsidian", todo.lower())
        self.assertNotIn("config.json", todo)

    def test_con_vault_ofrece_su_comando(self):
        caja = primer_arranque.vacio_de_arranque(lambda *_: None, vault="/mi/vault")
        todo = " | ".join(textos(caja))
        self.assertIn("/mi/vault", todo)
        self.assertIn("cotejo fuentes usar obsidian", todo)

    def test_copiar_pone_el_comando_en_el_portapapeles_y_avisa(self):
        avisos = []
        caja = primer_arranque.vacio_de_arranque(avisos.append)
        portapapeles = mock.Mock()
        with mock.patch("tareas.app.primer_arranque.Gdk.Display.get_default") as pantalla:
            pantalla.return_value.get_clipboard.return_value = portapapeles
            botones = []

            def buscar(w):
                if isinstance(w, Gtk.Button):
                    botones.append(w)
                h = w.get_first_child()
                while h:
                    buscar(h)
                    h = h.get_next_sibling()
            buscar(caja)
            botones[1].emit("clicked")
        portapapeles.set.assert_called_once_with("cotejo init --repo <carpeta>")
        self.assertEqual(avisos, ["Copiado al portapapeles"])

    def test_sin_fuente_el_maestro_se_desactiva_con_tooltip(self):
        falso = types.SimpleNamespace(seleccion="Uno", avisos=[],
                                      fuente=types.SimpleNamespace(problema="no hay"))
        falso.aviso = falso.avisos.append
        for metodo in ("barra_maestro", "poner_maestro", "al_ejecutar_maestro", "menu_maestro"):
            setattr(falso, metodo, types.MethodType(getattr(app.Board, metodo), falso))
        falso.barra = falso.barra_maestro()
        falso.poner_maestro()
        for control in (falso.boton_maestro, falso.entrada_maestro):
            self.assertFalse(control.get_sensitive())
        self.assertIn("de dónde leer", falso.boton_maestro.get_tooltip_text())
        falso.fuente.problema = None
        falso.poner_maestro()
        self.assertTrue(falso.boton_maestro.get_sensitive())


if __name__ == "__main__":
    unittest.main()
