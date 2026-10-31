"""El maestro ve trabajo aislado antes de concluir que la carpeta está vacía."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from enrutador import maestro
from tareas import ramas_pendientes


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Prueba", "-c",
         "user.email=prueba@localhost", *args], check=True, capture_output=True,
        text=True).stdout.strip()


class RamasPendientes(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "app.txt")
        git(self.repo, "commit", "-qm", "base")

    def rama(self, nombre, contenido, asunto):
        git(self.repo, "switch", "-qc", nombre, "main")
        (self.repo / "app.txt").write_text(contenido, encoding="utf-8")
        git(self.repo, "commit", "-qam", asunto)
        git(self.repo, "switch", "-q", "main")

    def test_encuentra_commits_fuera_de_main_y_explica_la_columna(self):
        self.rama("cotejo/cotejo-uno123", "la app completa\n", "Construir la app")
        tareas = [{"id": "cotejo-uno123", "texto": "Construir la app",
                   "estado": "por-validar"}]
        ramas = ramas_pendientes.detectar(self.repo, tareas)
        self.assertEqual(len(ramas), 1)
        self.assertEqual(ramas[0]["commits"], 1)
        self.assertIn("falta que una persona la apruebe", ramas[0]["motivo"])

        prompt = maestro.instruccion("Uno", [], str(self.repo), "no se abre", ramas=ramas)
        self.assertIn("cotejo/cotejo-uno123", prompt)
        self.assertIn("el trabajo sí existe", prompt)
        self.assertIn("No crees una tarea para rehacer", prompt)

    def test_no_enseña_una_rama_que_ya_entro(self):
        self.rama("cotejo/cotejo-dos123", "hecho\n", "Trabajo integrado")
        git(self.repo, "merge", "-q", "--no-ff", "cotejo/cotejo-dos123", "-m", "integrar")
        tareas = [{"id": "cotejo-dos123", "texto": "Trabajo integrado", "estado": "hecha"}]
        self.assertEqual(ramas_pendientes.detectar(self.repo, tareas), [])

    def test_ignora_una_rama_historica_que_ya_no_pertenece_al_tablero(self):
        self.rama("cotejo/cotejo-huerf1", "guardado\n", "Trabajo guardado")
        self.assertEqual(ramas_pendientes.detectar(self.repo, []), [])


if __name__ == "__main__":
    unittest.main()
