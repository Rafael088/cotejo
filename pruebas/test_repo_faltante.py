"""Un repo de la lista que ya no existe se salta con aviso (v1.3.0), en vez de tumbar la fuente.

Caso real: el repo «nuevo» de una preparación se borró y `crear` fallaba entero, y el Inicio
decía «Todavía no tienes proyectos». Aquí corre el CLI de verdad (subproceso, config temporal)
con un repo bueno y uno inexistente.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import apoyo
from tareas import resumen_inicio
from tareas.fuentes.repo import Repo

RAIZ = apoyo.RAIZ


class ConUnRepoQueFalta(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.bueno = self.raiz / "bueno"
        (self.bueno / ".git").mkdir(parents=True)
        (self.bueno / ".cotejo").mkdir()
        (self.bueno / ".cotejo" / "tareas.md").write_text(
            "# Tareas\n\n- [ ] Una tarea #facil ^b1\n", encoding="utf-8")
        self.perdido = self.raiz / "perdido"
        config = self.raiz / "config.json"
        config.write_text(json.dumps({"fuente": "repo", "fuentes": {"repo": {
            "repos": [str(self.perdido), str(self.bueno)]}}}), encoding="utf-8")
        self.entorno = {k: v for k, v in os.environ.items() if not k.startswith("COTEJO_")}
        self.entorno.update(HOME=str(self.raiz / "home"), XDG_CONFIG_HOME=str(self.raiz / "xc"),
                            XDG_STATE_HOME=str(self.raiz / "xs"), COTEJO_CONFIG=str(config),
                            COTEJO_ESTADO=str(self.raiz / "estado"))
        (self.raiz / "home").mkdir()

    def correr(self, *args):
        r = subprocess.run([sys.executable, "-m", "tareas", *args], cwd=RAIZ, env=self.entorno,
                           capture_output=True, text=True, timeout=60)
        try:
            return r.returncode, json.loads(r.stdout)
        except ValueError:
            self.fail(f"{args}: salida {r.stdout!r} / {r.stderr!r}")

    def aviso_de_faltante(self, avisos):
        faltan = [a for a in avisos if a.get("repo_falta")]
        self.assertEqual(len(faltan), 1, avisos)
        self.assertEqual(faltan[0]["repo_falta"], str(self.perdido))
        self.assertIn(str(self.perdido), faltan[0]["motivo"])
        self.assertIn("quítalo", faltan[0]["motivo"])

    def test_tareas_sigue_y_avisa_cual_falta(self):
        codigo, datos = self.correr("tareas")
        self.assertEqual(codigo, 0)
        self.assertEqual([t["id"] for t in datos["tareas"]], ["b1"])
        self.aviso_de_faltante(datos["avisos"])

    def test_crear_funciona_en_el_repo_bueno(self):
        codigo, datos = self.correr("crear", "Otra cosa", "--proyecto", "bueno")
        self.assertEqual(codigo, 0, datos)
        self.assertIn("Otra cosa", (self.bueno / ".cotejo" / "tareas.md").read_text(encoding="utf-8"))

    def test_estado_cuenta_y_avisa(self):
        codigo, datos = self.correr("estado")
        self.assertEqual(codigo, 0)
        self.assertNotIn("error", datos)
        self.assertEqual(datos["pendientes"], 1)
        self.aviso_de_faltante(datos["avisos"])

    def test_doctor_esta_ok_y_lista_el_aviso(self):
        codigo, datos = self.correr("doctor")
        self.assertEqual(datos["fuente"]["ok"], True, datos)
        self.assertEqual(datos["fuente"]["proyectos"], 1)
        self.aviso_de_faltante(datos["fuente"]["avisos"])

    def test_plan_reparte_las_del_repo_bueno(self):
        codigo, datos = self.correr("plan")
        self.assertEqual(codigo, 0, datos)
        self.assertIn("b1", json.dumps(datos))

    def test_si_no_queda_ninguno_sigue_siendo_un_problema(self):
        repo = Repo({"repos": [str(self.perdido)]})
        self.assertIn("no existe", repo.problema)
        self.assertEqual(Repo({"repos": [str(self.perdido), str(self.bueno)]}).problema, None)

    def test_el_aviso_va_en_llano_para_el_inicio(self):
        avisos = []
        Repo({"repos": [str(self.perdido), str(self.bueno)]}).escanear(avisos=avisos)
        titulo, detalles = resumen_inicio.repos_que_faltan(avisos)
        self.assertIn("1 repo de tu lista ya no existe", titulo)
        self.assertIn(str(self.perdido), detalles[0])
        self.assertIsNone(resumen_inicio.repos_que_faltan([{"nota": "x", "motivo": "y"}]))
        self.assertIsNone(resumen_inicio.repos_que_faltan(None))


if __name__ == "__main__":
    unittest.main()
