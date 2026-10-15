"""Que `cotejo-dev` no toque nada del Cotejo de todos los días.

El de desarrollo corre el código del repo con su propia config, su estado, su vault de prueba
y otro APP_ID. Si alguna de esas cosas se colara a la del usuario, desarrollar volvería a
pisar las tareas de verdad, que es justo lo que separarlos quería evitar.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

SCRIPT = RAIZ / "herramientas" / "cotejo_dev.py"


class CotejoDev(unittest.TestCase):

    def correr(self, carpeta, *argumentos, **entorno):
        limpio = {k: v for k, v in os.environ.items()
                  if not k.startswith(("COTEJO_", "FOCO_"))}
        limpio.update(COTEJO_DEV=str(carpeta), **entorno)
        # Desde fuera del repo: que el código salga de la ruta del script, no del directorio.
        return subprocess.run([sys.executable, str(SCRIPT), *argumentos], cwd=carpeta,
                              env=limpio, capture_output=True, text=True, timeout=60)

    def test_todo_lo_suyo_cae_en_su_carpeta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            hecho = self.correr(carpeta, "doctor")
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            datos = json.loads(hecho.stdout)
            self.assertEqual(datos["config"]["ruta"], str(Path(carpeta) / "config.json"))
            self.assertEqual(datos["fuente"]["proyectos"], 2)  # Faro y Horizonte, de mentira
            self.assertTrue((Path(carpeta) / "vault" / "01-Proyectos" / "Faro.md").exists())
            escrito = [p for p in Path(carpeta).rglob("*") if p.is_file()
                       and "vault" not in p.relative_to(carpeta).parts]
            fuera = [p for p in escrito if not p.is_relative_to(Path(carpeta) / "estado")]
            self.assertEqual(fuera, [], "lo que escribe Cotejo va a <dev>/estado")

    def test_lo_que_viene_puesto_gana(self):
        with tempfile.TemporaryDirectory() as carpeta, tempfile.TemporaryDirectory() as otro:
            vault = Path(otro) / "01-Proyectos"
            vault.mkdir()
            (vault / "Solo.md").write_text("---\ntipo: proyecto\n---\n\n- [ ] Una\n")
            hecho = self.correr(carpeta, "tareas", COTEJO_VAULT=otro)
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            self.assertEqual({t["proyecto"] for t in json.loads(hecho.stdout)["tareas"]},
                             {"Solo"})

    def test_el_board_de_desarrollo_tiene_su_propio_app_id(self):
        # Por texto y no importando `tareas.app`: esta prueba corre también donde no hay GTK.
        sys.path.insert(0, str(RAIZ))
        from herramientas import cotejo_dev
        comun = (RAIZ / "tareas" / "app" / "comun.py").read_text(encoding="utf-8")
        publicado = re.search(r'^APP_ID = "([^"]+)"', comun, re.M).group(1)
        self.assertNotEqual(cotejo_dev.APP_ID_DEV, publicado)


if __name__ == "__main__":
    unittest.main()
