"""La barra del Maestro en el pie: una indicación opcional y un solo botón para abrirlo.

Construye la barra de verdad con un Board falso, sin abrir ventana. Se salta sin GTK. Lo que se
escribe viaja al maestro como indicación (no se anota como tarea), Enter y el botón hacen lo
mismo, y el desplegable del botón elige el cliente y lo recuerda.
"""

import types
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from enrutador import clientes

try:
    from tareas import app
    from gi.repository import Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def board_falso(seleccion="Uno"):
    falso = types.SimpleNamespace(seleccion=seleccion, avisos=[],
                                  fuente=types.SimpleNamespace(problema=None))
    falso.aviso = lambda texto, segundos=4: falso.avisos.append(texto)
    for metodo in ("barra_maestro", "al_ejecutar_maestro", "abrir_maestro", "poner_maestro",
                   "menu_maestro", "cliente_del_maestro"):
        setattr(falso, metodo, types.MethodType(getattr(app.Board, metodo), falso))
    falso.barra = falso.barra_maestro()
    return falso


def abierto(proyecto="Uno", asignadas=2):
    return {"proyecto": proyecto, "asignadas": [{}] * asignadas}


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir la barra")
class BarraMaestro(unittest.TestCase):
    def setUp(self):
        guardado = {}
        for nombre, valor in (("cargar_board", lambda: dict(guardado)),
                              ("guardar_board", lambda **c: guardado.update(c))):
            parche = mock.patch.object(app.comun, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.guardado = guardado
        parche = mock.patch("enrutador.clientes.instalados", return_value=["claude", "codex"])
        parche.start()
        self.addCleanup(parche.stop)

    def test_un_solo_boton_para_abrir_el_maestro(self):
        falso = board_falso()
        botones = []
        hijo = falso.boton_maestro.get_parent().get_first_child()
        while hijo is not None:
            if isinstance(hijo, (Gtk.Button, Gtk.MenuButton)) or hasattr(hijo, "get_dropdown_tooltip"):
                botones.append(hijo)
            hijo = hijo.get_next_sibling()
        self.assertEqual(botones, [falso.boton_maestro])

    def test_enter_abre_el_maestro_con_la_indicacion(self):
        falso = board_falso()
        falso.entrada_maestro.set_text("  haz las tareas   de la v1.2.4 ")
        with mock.patch("enrutador.verbos.abrir_maestro", return_value=abierto()) as abrir:
            falso.entrada_maestro.emit("activate")
        abrir.assert_called_once_with("Uno", "claude", indicacion="haz las tareas de la v1.2.4")
        self.assertEqual(falso.entrada_maestro.get_text(), "")
        self.assertIn("indicación", falso.avisos[-1])

    def test_el_boton_dice_que_envia_cuando_hay_texto(self):
        falso = board_falso()
        falso.poner_maestro()
        self.assertEqual(falso.boton_maestro.get_label(), "Abrir maestro")
        falso.entrada_maestro.set_text("solo la web")
        self.assertEqual(falso.boton_maestro.get_label(), "Enviar al maestro")

    def test_si_el_maestro_se_niega_lo_escrito_se_queda(self):
        from tareas.cli import ErrorCLI
        falso = board_falso()
        falso.entrada_maestro.set_text("solo la web")
        with mock.patch("enrutador.verbos.abrir_maestro", side_effect=ErrorCLI("No", "Asígnalas")):
            falso.al_ejecutar_maestro()
        self.assertEqual(falso.entrada_maestro.get_text(), "solo la web")
        self.assertTrue(falso.avisos)

    def test_elegir_otro_cliente_lo_abre_y_lo_recuerda(self):
        falso = board_falso()
        falso.menu_maestro(falso.boton_maestro)
        caja = falso.boton_maestro.get_popover().get_child()
        opciones = []
        hijo = caja.get_first_child()
        while hijo is not None:
            if isinstance(hijo, Gtk.Button):
                opciones.append(hijo)
            hijo = hijo.get_next_sibling()
        self.assertEqual(len(opciones), 2)
        with mock.patch("enrutador.verbos.abrir_maestro", return_value=abierto()) as abrir:
            opciones[1].emit("clicked")
            falso.al_ejecutar_maestro()
        self.assertEqual([c.args[1] for c in abrir.call_args_list], ["codex", "codex"])

    def test_con_todos_los_proyectos_la_barra_no_se_usa(self):
        falso = board_falso(seleccion=app.comun.TODOS)
        falso.poner_maestro()
        for control in (falso.boton_maestro, falso.entrada_maestro):
            self.assertFalse(control.get_sensitive())

    def test_sin_clientes_avisa(self):
        falso = board_falso()
        with mock.patch("enrutador.clientes.instalados", return_value=[]), \
                mock.patch("enrutador.verbos.abrir_maestro") as abrir:
            falso.al_ejecutar_maestro()
        abrir.assert_not_called()
        self.assertEqual(falso.avisos, [clientes.SIN_AGENTE_TEXTO])


if __name__ == "__main__":
    unittest.main()
