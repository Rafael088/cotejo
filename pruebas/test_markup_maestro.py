"""El formato de las respuestas del maestro no depende de GTK."""

import unittest

from tareas.markup import texto_a_markup


class MarkupDelMaestro(unittest.TestCase):
    def test_pinta_negrita_codigo_listas_y_parrafos(self):
        self.assertEqual(
            texto_a_markup("**Importante**\n\n- abre `app.py`\n- prueba"),
            '<b>Importante</b>\n\n• abre <span font_family="IBM Plex Mono" '
            'size="92%">app.py</span>\n• prueba')

    def test_escapa_texto_y_codigo_antes_de_crear_markup(self):
        self.assertEqual(
            texto_a_markup('Usa <b> & `x < y && y > 0` **sin <i>**'),
            'Usa &lt;b&gt; &amp; <span font_family="IBM Plex Mono" size="92%">'
            'x &lt; y &amp;&amp; y &gt; 0</span> <b>sin &lt;i&gt;</b>')

    def test_deja_los_delimitadores_sin_pareja_como_texto(self):
        self.assertEqual(texto_a_markup("**abierta y `código"),
                         "**abierta y `código")


if __name__ == "__main__":
    unittest.main()
