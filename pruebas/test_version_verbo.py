"""`cotejo version` (v1.2.4, `tareas/version_verbo.py`): contra un repo de git de mentira con y
sin tags, y la fuente en memoria de `test_fuente.py` para las tareas."""

import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401
from test_fuente import PruebaConMemoria
from tareas import modelo


@unittest.skipUnless(shutil.which("git"), "hace falta git")
class CotejoVersion(PruebaConMemoria):

    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "LEEME").write_text("hola\n", encoding="utf-8")
        self.git("add", "LEEME")
        self.git("commit", "-q", "-m", "primero")
        # La memoria ahora es de un repo, y sus tareas son de la 1.2.4 (o de otra).
        self.memoria.carpeta_de = lambda proyecto: str(self.repo)
        self.memoria.proyecto.tareas = [
            modelo.Tarea("Una pendiente", id="a1", version="v1.2.4"),
            modelo.Tarea("Otra versión", id="a2", version="v1.3.0"),
            modelo.Tarea("Sin versión", id="a3"),
        ]
        self.memoria.proyecto.hechas = [
            modelo.Tarea("Vieja", id="h1", hecha=True, version="v1.2.4", cerrada="2026-01-01"),
            modelo.Tarea("Nueva", id="h2", hecha=True, version="v1.2.4", cerrada="2099-01-01"),
            modelo.Tarea("Sin fecha", id="h3", hecha=True, version="v1.2.4"),
        ]

    def git(self, *args):
        entorno = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=prueba",
                        "-c", "user.email=prueba@ejemplo", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgsign=false", *args],
                       check=True, capture_output=True, env=entorno)

    def proyecto_md(self, **frontmatter):
        cabecera = "".join(f"{k}: {v}\n" for k, v in frontmatter.items())
        ruta = self.repo / ".cotejo" / "proyecto.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(f"---\nid: proyecto\n{cabecera}---\n# Mi repo\n", encoding="utf-8")
        return ruta

    def version(self, *args):
        return self.correr("version", "--proyecto", "Cosas", *args)

    def test_sin_tags_cuenta_todas_las_hechas_de_la_en_curso(self):
        self.proyecto_md(version="1.2.4")
        codigo, datos = self.version()
        self.assertEqual(codigo, 0)
        self.assertEqual((datos["publicada"], datos["en_curso"], datos["tag"]),
                         (None, "1.2.4", None))
        self.assertEqual(datos["proyecto"], "Cosas")
        self.assertEqual(datos["tareas"], {"pendiente": 1, "en-curso": 0, "por-validar": 0,
                                           "hecha": 3, "total": 4, "sin_version": 1})
        self.assertEqual([t["id"] for t in datos["aprobadas"]["tareas"]], ["h1", "h2", "h3"])

    def test_con_tag_solo_cuenta_lo_cerrado_despues(self):
        self.proyecto_md(version="1.2.4")
        self.git("tag", "v1.2.3")
        _, datos = self.version()
        self.assertEqual((datos["publicada"], datos["tag"]), ("1.2.3", "v1.2.3"))
        self.assertRegex(datos["fecha_tag"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual([t["id"] for t in datos["aprobadas"]["tareas"]], ["h2"])
        self.assertEqual(datos["aprobadas"]["sin_fecha"], 1)
        self.assertEqual(datos["aprobadas"]["desde"], datos["fecha_tag"])

    def test_alcanzada_la_declarada_la_en_curso_es_el_parche_calculado(self):
        self.proyecto_md(version="1.2.4")
        self.git("tag", "v1.2.4")
        _, datos = self.version()
        self.assertEqual((datos["en_curso"], datos["calculada"]), ("1.2.5", True))
        self.assertEqual(datos["tareas"]["total"], 0)

    def test_no_escribe_nada(self):
        ruta = self.proyecto_md(version="1.2.4")
        antes = ruta.read_bytes()
        self.version()
        self.assertEqual(ruta.read_bytes(), antes)
        self.assertEqual(self.memoria.escrituras, 0)

    def test_sin_proyecto_conocido_da_la_version_sin_tareas(self):
        self.proyecto_md(version="1.2.4")
        self.memoria.carpeta_de = lambda proyecto: None
        with mock.patch("tareas.version_verbo.Path.cwd", return_value=self.repo):
            codigo, datos = self.correr("version")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["en_curso"], "1.2.4")
        self.assertIsNone(datos["proyecto"])
        self.assertIsNone(datos["tareas"])
        self.assertTrue(datos["avisos"])

    def test_sin_proyecto_pero_dentro_del_repo_del_proyecto(self):
        self.proyecto_md(version="1.2.4")
        with mock.patch("tareas.version_verbo.Path.cwd", return_value=self.repo):
            _, datos = self.correr("version")
        self.assertEqual(datos["proyecto"], "Cosas")
        self.assertEqual(datos["tareas"]["total"], 4)

    def test_errores_claros(self):
        codigo, datos = self.correr("version", "--proyecto", "Inexistente")
        self.assertNotEqual(codigo, 0)
        self.assertIn("Inexistente", datos["error"])
        self.memoria.carpeta_de = lambda proyecto: None
        codigo, datos = self.version()
        self.assertNotEqual(codigo, 0)
        self.assertIn("carpeta", datos["error"])
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        with mock.patch("tareas.version_verbo.Path.cwd", return_value=Path(fuera.name)):
            codigo, datos = self.correr("version")
        self.assertNotEqual(codigo, 0)
        self.assertIn("repo", datos["error"])

    def test_siguiente_escribe_la_menor_por_el_almacen(self):
        self.proyecto_md(version="1.2.4")
        self.git("tag", "v1.2.3")
        codigo, datos = self.version("--siguiente", "1.3.0")
        self.assertEqual(codigo, 0)
        self.assertEqual((datos["hecho"], datos["en_curso"], datos["declarada"]),
                         ("escrita", "1.3.0", "1.3.0"))
        self.assertIn("version: 1.3.0", (self.repo / ".cotejo" / "proyecto.md").read_text())
        _, otra = self.version("--siguiente", "1.3.0")
        self.assertEqual(otra["hecho"], "ya-estaba")

    def test_siguiente_acepta_la_mayor_y_crea_proyecto_md_si_falta(self):
        self.git("tag", "v1.2.3")
        codigo, datos = self.version("--siguiente", "2.0.0")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["en_curso"], "2.0.0")

    def test_siguiente_rechaza_parche_bajar_y_basura(self):
        self.proyecto_md(version="1.2.4")
        ruta = self.repo / ".cotejo" / "proyecto.md"
        antes = ruta.read_bytes()
        for texto in ("1.2.5", "1.2.4", "1.1.0", "0.9.0", "1.3", "nada", "1.3.1"):
            with self.subTest(texto=texto):
                codigo, datos = self.version("--siguiente", texto)
                self.assertNotEqual(codigo, 0)
                self.assertIn("error", datos)
        self.assertEqual(ruta.read_bytes(), antes)

    def test_siguiente_sin_version_en_curso_pide_init(self):
        codigo, datos = self.version("--siguiente", "1.3.0")
        self.assertNotEqual(codigo, 0)
        self.assertIn("versión", datos["error"])


if __name__ == "__main__":
    unittest.main()
