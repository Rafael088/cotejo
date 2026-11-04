"""Cerrar el board con un agente trabajando pregunta «pararlos o dejarlos» (cotejo-qtegjk).

En el board de verdad (GTK y pantalla; sin ellas se salta), con el cliente falso de agente
lanzado desde el board como en `test_lanzar_board.py`. La pregunta se contesta sin diálogo
(`preguntar_al_cerrar` cambiada por una respuesta), salvo en la prueba que mira el diálogo mismo.
"""

import os
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_lanzar_board as tl
import test_pestana_inicio as base
from enrutador import procesos

if base.HAY_GTK:
    from gi.repository import Adw
    from tareas import lanzados
    from tareas.app import al_cerrar


@unittest.skipUnless(base.HAY_GTK and tl.HAY_GIT, "sin GTK, sin pantalla o sin git")
class CerrarConAgentes(base.PestanaInicio):
    entorno_extra = tl.LanzarDesdeElBoard.entorno_extra
    configurar = tl.LanzarDesdeElBoard.configurar
    fila = tl.LanzarDesdeElBoard.fila
    arrastrar = tl.LanzarDesdeElBoard.arrastrar
    esperar_despacho = tl.LanzarDesdeElBoard.esperar_despacho
    linea = tl.LanzarDesdeElBoard.linea
    esperar = tl.LanzarDesdeElBoard.esperar

    def lanzar_uno(self):
        """Lanza el falso en «cotejo-con» y lo deja trabajando hasta que la prueba lo pare."""
        self.board.ver_pestana("tablero")
        self.board.present()
        base.girar()
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "60"}):
            self.arrastrar("parseo")
        registro = lanzados.leer("cotejo-con")
        self.assertTrue(procesos.vivo(registro["pid"]))
        return registro

    def contestar(self, respuesta):
        """Cambia la pregunta por `respuesta` y anota con qué agentes se preguntó."""
        preguntas = []

        def responder(board, vivos):
            preguntas.append([r["id"] for r in vivos])
            board.al_responder_cierre(respuesta, vivos)
            return None

        parche = mock.patch.object(type(self.board), "preguntar_al_cerrar", responder)
        parche.start()
        self.addCleanup(parche.stop)
        return preguntas

    def test_pararlos_para_al_agente_y_devuelve_la_tarea_a_pendiente(self):
        registro = self.lanzar_uno()
        preguntas = self.contestar(al_cerrar.PARAR)
        self.board.close()
        base.girar(200)
        self.assertEqual(preguntas, [["cotejo-con"]])
        self.assertFalse(self.board.get_visible())
        self.assertTrue(self.esperar(lambda: not procesos.vivo(registro["pid"])))
        self.assertEqual(lanzados.leer("cotejo-con")["fase"], lanzados.DETENIDO)
        self.assertEqual(lanzados.leer("cotejo-con")["motivo"], al_cerrar.MOTIVO)
        self.assertNotIn("#en-curso", self.linea("^cotejo-con"))
        self.assertIn("#agente/sonnet", self.linea("^cotejo-con"))

    def test_dejarlos_trabajando_cierra_sin_tocarlos(self):
        registro = self.lanzar_uno()
        preguntas = self.contestar(al_cerrar.DEJAR)
        self.board.close()
        base.girar(200)
        self.assertEqual(preguntas, [["cotejo-con"]])
        self.assertFalse(self.board.get_visible())
        self.assertTrue(procesos.vivo(registro["pid"]))
        self.assertEqual(lanzados.leer("cotejo-con")["fase"], lanzados.LANZADO)
        self.assertIn("#en-curso", self.linea("^cotejo-con"))

    def test_cancelar_no_cierra(self):
        registro = self.lanzar_uno()
        self.contestar(al_cerrar.CANCELAR)
        self.board.close()
        base.girar()
        self.assertTrue(self.board.get_visible())
        self.assertTrue(procesos.vivo(registro["pid"]))

    def test_sin_agentes_cierra_sin_preguntar(self):
        self.board.present()
        base.girar()
        preguntas = self.contestar(al_cerrar.CANCELAR)
        self.board.close()
        base.girar()
        self.assertEqual(preguntas, [])
        self.assertFalse(self.board.get_visible())

    def test_en_windows_cerrar_sale_de_la_app(self):
        self.lanzar_uno()
        self.contestar(al_cerrar.DEJAR)
        with mock.patch.object(al_cerrar, "sale_al_cerrar", return_value=True), \
                mock.patch.object(self.app, "quit") as salir:
            self.board.close()
            base.girar(200)
        salir.assert_called_once_with()

    def test_en_linux_cerrar_solo_oculta(self):
        self.board.present()
        base.girar()
        with mock.patch.object(al_cerrar, "sale_al_cerrar", return_value=False), \
                mock.patch.object(self.app, "quit") as salir:
            self.board.close()
            base.girar(200)
        salir.assert_not_called()

    def test_abrir_otra_vez_en_windows_no_lo_cierra(self):
        self.board.present()
        base.girar()
        with mock.patch.object(al_cerrar, "sale_al_cerrar", return_value=True):
            self.app.abrir_sin_opciones()
            base.girar()
        self.assertTrue(self.board.get_visible())
        with mock.patch.object(al_cerrar, "sale_al_cerrar", return_value=False):
            self.app.abrir_sin_opciones()   # en Linux abre o cierra (el widget de la barra)
            base.girar()
        self.assertFalse(self.board.get_visible())

    def test_el_dialogo_de_verdad_pregunta_y_al_contestar_cierra(self):
        registro = self.lanzar_uno()
        self.board.close()
        base.girar()
        dialogo = self.board.pregunta_cierre
        self.assertIsInstance(dialogo, Adw.AlertDialog)
        self.assertTrue(self.board.get_visible())
        self.assertIn("sonnet sigue trabajando", dialogo.get_heading())
        self.assertIn("sonnet: Arreglar el parseo", dialogo.get_body())
        for respuesta in (al_cerrar.CANCELAR, al_cerrar.DEJAR, al_cerrar.PARAR):
            self.assertTrue(dialogo.has_response(respuesta))
        self.assertEqual(dialogo.get_close_response(), al_cerrar.CANCELAR)
        # Otro clic en la X mientras pregunta es como Cancelar (libadwaita cierra el diálogo
        # primero): la ventana sigue y el agente también.
        self.board.close()
        base.girar()
        self.assertIsNone(self.board.pregunta_cierre)
        self.assertTrue(self.board.get_visible())
        self.assertTrue(procesos.vivo(registro["pid"]))
        self.board.close()
        base.girar()
        dialogo = self.board.pregunta_cierre
        self.assertIsInstance(dialogo, Adw.AlertDialog)
        dialogo.emit("response", al_cerrar.PARAR)
        dialogo.force_close()
        base.girar()
        self.assertIsNone(self.board.pregunta_cierre)
        self.assertFalse(self.board.get_visible())
        self.assertTrue(self.esperar(lambda: not procesos.vivo(registro["pid"])))


if __name__ == "__main__":
    unittest.main()
