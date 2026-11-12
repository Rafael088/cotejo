"""La frontera de texto del board: sin controles de terminal y con errores comprensibles."""

import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en sys.path)

from tareas import texto_board


class TextoDelBoard(unittest.TestCase):
    def test_quita_colores_cursor_osc_y_secuencias_que_llegan_sin_escape(self):
        crudo = ("\x1b[91m\x1b[1mError:\x1b[0m "
                 "\x1b]8;;https://ejemplo.test\x07enlace\x1b]8;;\x07 "
                 "\x1b[2K[32mfin[0m")
        self.assertEqual(texto_board.sin_ansi(crudo), "Error: enlace fin")

    def test_traduce_los_cuatro_errores_y_deja_el_original_limpio_debajo(self):
        casos = (
            ("\x1b[91mError: Invalid model reference\x1b[0m", "modelo configurado"),
            ("Error: Insufficient account funds", "no tiene saldo"),
            ("Not logged in · Please run /login", "sesión iniciada"),
            ("HTTP 429: usage limit reached", "límite de uso"),
        )
        for crudo, frase in casos:
            with self.subTest(crudo=crudo):
                mostrado = texto_board.para_mostrar(crudo)
                self.assertIn(frase, mostrado)
                self.assertIn("\n\nOriginal:\n", mostrado)
                self.assertIn(texto_board.sin_ansi(crudo), mostrado)
                self.assertNotIn("\x1b", mostrado)

    def test_el_texto_desconocido_solo_pierde_ansi_y_la_funcion_es_idempotente(self):
        self.assertEqual(texto_board.para_mostrar("\x1b[33mcompilando…\x1b[0m"),
                         "compilando…")
        una = texto_board.para_mostrar("Invalid model reference")
        self.assertEqual(texto_board.para_mostrar(una), una)


if __name__ == "__main__":
    unittest.main()
