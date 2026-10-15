"""`cotejo --board` sin pantalla (ssh, TTY): un mensaje y código 1, sin traceback ni core dump.

Corre el verbo de punta a punta en un subproceso sin WAYLAND_DISPLAY, DISPLAY ni XDG_RUNTIME_DIR
(para que GTK no encuentre ningún socket). Si PyGObject no está, se salta.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from apoyo import RAIZ

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    HAY_GTK = True
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4")
class BoardSinPantalla(unittest.TestCase):
    def correr(self, *argumentos):
        with tempfile.TemporaryDirectory() as casa:
            entorno = {k: v for k, v in os.environ.items()
                       if k not in ("WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR")}
            entorno.update(HOME=casa, XDG_CONFIG_HOME=casa + "/c", XDG_STATE_HOME=casa + "/s",
                           XDG_DATA_HOME=casa + "/d")
            return subprocess.run([sys.executable, "-m", "tareas", *argumentos], cwd=RAIZ,
                                  env=entorno, capture_output=True, text=True, timeout=60)

    def comprobar(self, *argumentos):
        r = self.correr(*argumentos)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("No hay pantalla gráfica", r.stderr)
        self.assertIn("la CLI funciona igual", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_board(self):
        self.comprobar("--board")

    def test_sin_argumentos(self):
        self.comprobar()


if __name__ == "__main__":
    unittest.main()
