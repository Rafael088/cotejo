"""Abrir y reabrir la ventana del board, sin necesitar una pantalla real."""

import sys
import types
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app
    from tareas.app import escala
    HAY_GTK = True
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK")
class AbrirBoard(unittest.TestCase):
    def test_en_windows_vuelve_a_pedir_maximizar_al_reabrir_tras_ocultarlo(self):
        llamadas = []
        board = mock.Mock()
        board.get_visible.return_value = False
        board.maximize.side_effect = lambda: llamadas.append("maximizar")
        board.present.side_effect = lambda: llamadas.append("presentar")
        board.close.side_effect = lambda: llamadas.append("ocultar")
        aplicacion = types.SimpleNamespace(
            board=board, desde_cero=False, vigilando_escala=False,
        )
        aplicacion.abrir_board = lambda: app.App.abrir_board(aplicacion)

        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(escala, "forzado", return_value=1.0):
            app.App.abrir_board(aplicacion)
            board.close()  # GTK la oculta porque la ventana tiene hide-on-close.
            app.App.alternar_board(aplicacion)  # El acceso del menú Inicio llega por aquí.

        self.assertEqual(llamadas, [
            "maximizar", "presentar", "ocultar", "maximizar", "presentar",
        ])

    def test_fuera_de_windows_solo_presenta(self):
        board = mock.Mock()
        aplicacion = types.SimpleNamespace(
            board=board, desde_cero=False, vigilando_escala=False,
        )

        with mock.patch.object(sys, "platform", "linux"):
            app.App.abrir_board(aplicacion)

        board.present.assert_called_once_with()
        board.maximize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
