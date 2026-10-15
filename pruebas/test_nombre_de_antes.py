"""Lo que quedó de cuando Cotejo se llamaba Foco, y tiene que seguir funcionando.

El cambio de nombre no puede costarle nada a quien ya lo usaba: sus tareas llevan marcas
`^foco-…`, su config vive en `~/.config/foco/`, sus scripts exportan `FOCO_VAULT` y sus agentes
tienen instalada la skill `foco`. Cada prueba de aquí es una de esas cosas.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaConVault, proyecto

from tareas import bitacora, configuracion, modelo, skill
from tareas.fuentes import obsidian

RAIZ = Path(__file__).resolve().parent.parent


class Marcas(PruebaConVault):
    def test_una_tarea_con_marca_foco_se_sigue_encontrando_por_su_id(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] De antes ^foco-abc123"))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([t.id for t in tareas], ["foco-abc123"])

    def test_las_marcas_nuevas_nacen_con_el_nombre_nuevo(self):
        self.assertEqual(obsidian.PREFIJO_MARCA, "cotejo-")

    def test_una_tarea_migrada_se_encuentra_por_su_id_de_antes(self):
        # Una sesión que ya la tenía, o una evidencia, la sigue nombrando foco-….
        self.escribir_nota("Uno.md", proyecto("- [ ] Migrada ^cotejo-abc123"))
        proyecto_, tarea = modelo.buscar(self.escanear(), "foco-abc123")
        self.assertEqual(tarea.id, "cotejo-abc123")

    def test_el_id_nuevo_encuentra_una_tarea_sin_migrar(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Sin migrar ^foco-abc123"))
        _, tarea = modelo.buscar(self.escanear(), "cotejo-abc123")
        self.assertEqual(tarea.id, "foco-abc123")

    def test_el_id_exacto_gana_al_equivalente(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Nueva ^cotejo-abc123", "- [ ] Vieja ^foco-abc123"))
        _, tarea = modelo.buscar(self.escanear(), "foco-abc123")
        self.assertEqual(tarea.texto, "Vieja")


class BitacoraConIdsDeAntes(unittest.TestCase):
    def test_la_evidencia_anotada_con_el_id_viejo_sale_con_el_nuevo(self):
        archivo = Path(tempfile.mkdtemp()) / "bitacora.jsonl"
        archivo.write_text(json.dumps({"id": "foco-abc123", "operacion": "entregar",
                                       "evidencia": "commit 1234"}) + "\n", encoding="utf-8")
        with mock.patch.object(bitacora, "ARCHIVO", archivo):
            ultimas = bitacora.ultimas()
        self.assertEqual(ultimas.get("cotejo-abc123")["evidencia"], "commit 1234")
        self.assertEqual(ultimas.get("foco-abc123")["evidencia"], "commit 1234")


class Carpeta(unittest.TestCase):
    def setUp(self):
        self.xdg = Path(tempfile.mkdtemp())
        parche = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.xdg)})
        parche.start()
        self.addCleanup(parche.stop)
        os.environ.pop("COTEJO_CONFIG", None)

    def test_sin_ninguna_es_la_nueva(self):
        self.assertEqual(configuracion.carpeta(), self.xdg / "cotejo")

    def test_si_solo_esta_la_de_foco_se_sigue_usando_esa(self):
        (self.xdg / "foco").mkdir()
        (self.xdg / "foco" / "config.json").write_text('{"fuente": "obsidian"}', encoding="utf-8")
        self.assertEqual(configuracion.ruta(), self.xdg / "foco" / "config.json")

    def test_si_estan_las_dos_manda_la_nueva(self):
        (self.xdg / "foco").mkdir()
        (self.xdg / "cotejo").mkdir()
        self.assertEqual(configuracion.carpeta(), self.xdg / "cotejo")

    def test_foco_como_enlace_a_cotejo_no_confunde(self):
        # Lo que deja install.sh después de mover la carpeta.
        (self.xdg / "cotejo").mkdir()
        (self.xdg / "foco").symlink_to("cotejo")
        self.assertEqual(configuracion.carpeta(), self.xdg / "cotejo")


class Entorno(unittest.TestCase):
    def correr(self, entorno):
        codigo = "import os, tareas; print(os.environ.get('COTEJO_VAULT', ''))"
        limpio = {k: v for k, v in os.environ.items() if not k.startswith(("FOCO_", "COTEJO_"))}
        salida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True,
                                text=True, env={**limpio, **entorno}, check=True)
        return salida.stdout.strip()

    def test_una_variable_foco_vale_como_la_cotejo(self):
        self.assertEqual(self.correr({"FOCO_VAULT": "/de/antes"}), "/de/antes")

    def test_si_estan_las_dos_manda_la_cotejo(self):
        self.assertEqual(self.correr({"FOCO_VAULT": "/vieja", "COTEJO_VAULT": "/nueva"}), "/nueva")


class Skills(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_el_bloque_de_foco_se_reemplaza_y_no_se_acumula(self):
        antes = "# Lo mío\n\n<!-- foco:inicio -->\nllama a `foco plan`\n<!-- foco:fin -->\n"
        despues = skill.inyectar(antes)
        self.assertNotIn("foco:inicio", despues)
        self.assertEqual(despues.count(skill.INICIO), 1)
        self.assertTrue(despues.startswith("# Lo mío"))

    def test_las_skills_de_foco_se_quitan_al_instalar(self):
        (self.dir / ".claude").mkdir()
        for vieja in ("foco", "foco-fuentes", "foco-modelos"):
            (self.dir / ".claude/skills" / vieja).mkdir(parents=True)
            (self.dir / ".claude/skills" / vieja / "SKILL.md").write_text("vieja")
        skill.instalar(hogar=self.dir)
        self.assertFalse((self.dir / ".claude/skills/foco").exists())
        self.assertFalse((self.dir / ".claude/skills/foco-fuentes").exists())
        self.assertFalse((self.dir / ".claude/skills/foco-modelos").exists())
        self.assertTrue((self.dir / ".claude/skills/cotejo-modelos/SKILL.md").exists())
        self.assertTrue((self.dir / ".claude/skills/cotejo/SKILL.md").exists())
        self.assertTrue((self.dir / ".claude/skills/cotejo-fuentes/SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
