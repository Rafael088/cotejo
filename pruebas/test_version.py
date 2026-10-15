"""Una sola versión: `tareas.__version__`, y todo lo que la dice la lee de ahí.

Sin una sola fuente el ZIP de Windows y el paquete de Linux no se pueden comparar, un informe
de fallo no dice qué versión era y el instalador no sabe si actualiza (docs/v1.0.md, A).
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest

from apoyo import RAIZ, PruebaDeCLI, proyecto
import tareas

CONSTRUIR_WINDOWS = RAIZ / "empaquetado" / "windows" / "construir.py"


class LaVersion(unittest.TestCase):
    def test_es_semver(self):
        self.assertRegex(tareas.__version__, r"^\d+\.\d+\.\d+$")

    def test_cotejo_version_la_imprime(self):
        hecho = subprocess.run([sys.executable, "-m", "tareas", "--version"], cwd=RAIZ,
                               capture_output=True, text=True, check=True)
        self.assertEqual(hecho.stdout.strip(), f"cotejo {tareas.__version__}")

    def test_el_widget_de_la_barra_dice_la_misma(self):
        manifiesto = json.loads((RAIZ / "barra/cotejo.barra/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifiesto["version"], tareas.__version__)

    @unittest.skipUnless(CONSTRUIR_WINDOWS.exists(), "no está el script de Windows")
    def test_construir_de_windows_la_usa_por_defecto(self):
        spec = importlib.util.spec_from_file_location("construir_windows", CONSTRUIR_WINDOWS)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        self.assertEqual(modulo.version_por_defecto(), tareas.__version__)

    @unittest.skipUnless((RAIZ / ".git").exists() and shutil.which("git"), "no es un checkout de git")
    def test_construir_de_linux_la_lee_de_head(self):
        # construir.sh publica HEAD, así que su versión es la de HEAD, no la del árbol.
        en_head = subprocess.run(["git", "-C", str(RAIZ), "show", "HEAD:tareas/__init__.py"],
                                 capture_output=True, text=True, check=True).stdout
        esperada = re.search(r'^__version__ = "([^"]+)"$', en_head, re.MULTILINE)
        if not esperada:
            self.skipTest("HEAD es anterior a __version__")
        hecho = subprocess.run(["sh", str(RAIZ / "empaquetado/linux/construir.sh"), "--version"],
                               capture_output=True, text=True, check=True)
        self.assertEqual(hecho.stdout.strip(), esperada.group(1))


class ElDoctor(PruebaDeCLI):
    def test_dice_la_version(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Algo ^cotejo-uno1"))
        _, datos = self.correr("doctor")
        self.assertEqual(datos["version"], tareas.__version__)


if __name__ == "__main__":
    unittest.main()
