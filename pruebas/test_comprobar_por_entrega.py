"""A Para comprobar solo se llega entregando (cotejo-2sxw7p): una tarea asignada a un agente no
se pasa a mano desde Pendiente o Haciendo, y el board le dice a la persona por qué."""

import unittest
from types import SimpleNamespace
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import modelo
from tareas.modelo import Tarea

try:
    from tareas.app.movimientos import Movimientos
except (ImportError, ValueError):
    Movimientos = None

PERSONA = ("persona", "yo")


def tarea(estado, agente, **extra):
    return Tarea(texto="Algo", id="t-1", estado=estado, agente=agente, **extra)


class AvisoComprobarAMano(unittest.TestCase):
    def test_una_de_un_agente_no_pasa_de_pendiente_ni_de_haciendo(self):
        for estado in ("pendiente", "en-curso"):
            aviso = modelo.aviso_comprobar_a_mano(tarea(estado, "sonnet"), "por-validar", PERSONA)
            self.assertIn("sonnet", aviso)
            self.assertIn("Para comprobar", aviso)
            self.assertIn("«persona»", aviso)

    def test_las_de_una_persona_o_sin_asignar_si(self):
        for agente in ("persona", "yo", ""):
            for estado in ("pendiente", "en-curso"):
                self.assertEqual(modelo.aviso_comprobar_a_mano(
                    tarea(estado, agente), "por-validar", PERSONA), "")

    def test_solo_cuenta_el_salto_a_para_comprobar_desde_pendiente_o_haciendo(self):
        self.assertEqual(modelo.aviso_comprobar_a_mano(
            tarea("en-curso", "sonnet"), "pendiente", PERSONA), "")
        self.assertEqual(modelo.aviso_comprobar_a_mano(
            tarea("en-curso", "sonnet"), "hecha", PERSONA), "")
        # Ya en Para comprobar, o ya hecha: no es el salto que se cierra.
        self.assertEqual(modelo.aviso_comprobar_a_mano(
            tarea("por-validar", "sonnet"), "por-validar", PERSONA), "")
        self.assertEqual(modelo.aviso_comprobar_a_mano(
            tarea("en-curso", "sonnet", hecha=True), "por-validar", PERSONA), "")


@unittest.skipIf(Movimientos is None, "sin GTK")
class EnElBoard(unittest.TestCase):
    def board(self):
        return SimpleNamespace(
            alias_persona=PERSONA, aviso=mock.Mock(), app=SimpleNamespace(refrescar=mock.Mock()),
            escribir_movimiento=mock.Mock(), lanzar_al_mover=mock.Mock(return_value=False),
            pausar_al_mover=mock.Mock(), preguntar_motivo=mock.Mock())

    def test_el_salto_se_niega_y_se_dice_sin_escribir_nada(self):
        board = self.board()
        for estado in ("pendiente", "en-curso"):
            Movimientos.mover(board, "P", tarea(estado, "sonnet"), "por-validar")
        self.assertEqual(board.aviso.call_count, 2)
        self.assertIn("sonnet", board.aviso.call_args.args[0])
        board.escribir_movimiento.assert_not_called()
        board.lanzar_al_mover.assert_not_called()

    def test_una_de_una_persona_se_mueve_como_siempre(self):
        board = self.board()
        Movimientos.mover(board, "P", tarea("en-curso", "persona"), "por-validar")
        board.aviso.assert_not_called()
        board.escribir_movimiento.assert_called_once()


if __name__ == "__main__":
    unittest.main()
