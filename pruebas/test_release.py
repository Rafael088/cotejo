"""`cotejo release` (v1.2.4, `tareas/release.py`): contra un repo de git de mentira con y sin
tags, la fuente en memoria de `test_fuente.py` para las tareas y el almacén del repo para las
decisiones y los problemas."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401
from test_fuente import PruebaConMemoria
from tareas import almacen, decision, modelo

ANTES, DESPUES = "2000-01-01", "2099-01-01"  # el tag se crea hoy: una antes y otra después


@unittest.skipUnless(shutil.which("git"), "hace falta git")
class CotejoRelease(PruebaConMemoria):

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
        self.memoria.carpeta_de = lambda proyecto: str(self.repo)
        # Todo lo de la 1.2.4 está aprobado; lo abierto es de otra versión o no tiene.
        self.memoria.proyecto.tareas = [
            modelo.Tarea("Otra versión", id="a2", version="v1.3.0"),
            modelo.Tarea("Sin versión", id="a3"),
        ]
        self.memoria.proyecto.hechas = [
            modelo.Tarea("Vieja", id="h1", hecha=True, version="v1.2.4", cerrada=ANTES),
            modelo.Tarea("Nueva", id="h2", hecha=True, version="v1.2.4", cerrada=DESPUES),
            modelo.Tarea("Sin fecha", id="h3", hecha=True, version="v1.2.4"),
        ]
        ruta = self.repo / ".cotejo" / "proyecto.md"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("---\nid: proyecto\nversion: 1.2.4\n---\n# Mi repo\n", encoding="utf-8")
        alm = almacen.Almacen(self.repo)
        self.dec_vieja = alm.crear("decision", "Decidida hace mucho", estado="aceptada",
                                   fecha=ANTES).id
        self.dec_nueva = alm.crear("decision", "Decidida ahora", estado="aceptada",
                                   aceptada_el=DESPUES).id
        self.dec_propuesta = alm.crear("decision", "Solo propuesta", fecha=DESPUES).id
        self.dec_importada = alm.crear("decision", "Importada", estado="aceptada",
                                       autor="importado", fecha=DESPUES).id
        self.pro_resuelto = alm.crear("problema", "Se rompía", estado="resuelto", fecha=ANTES,
                                      resuelto_el=DESPUES, solucion="Ya no").id
        self.pro_abierto = alm.crear("problema", "Sigue roto", fecha=DESPUES).id

    def git(self, *args):
        entorno = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=prueba",
                               "-c", "user.email=prueba@ejemplo", "-c", "commit.gpgsign=false",
                               "-c", "tag.gpgsign=false", *args],
                              check=True, capture_output=True, text=True, env=entorno).stdout

    def release(self, *args):
        return self.correr("release", "--proyecto", "Cosas", *args)

    def notas(self):
        return self.repo / ".cotejo" / "releases" / "v1.2.4.md"

    def test_sin_tags_ensayo_con_todo_y_sin_escribir(self):
        codigo, datos = self.release()
        self.assertEqual(codigo, 0, datos)
        self.assertEqual((datos["version"], datos["tag"], datos["aplicado"]),
                         ("1.2.4", "v1.2.4", False))
        self.assertEqual(datos["desde"], {"tag": None, "fecha": None})
        self.assertEqual([t["id"] for t in datos["tareas"]], ["h1", "h2", "h3"])
        self.assertEqual({d["id"] for d in datos["decisiones"]},
                         {self.dec_vieja, self.dec_nueva})
        self.assertEqual([p["id"] for p in datos["problemas"]], [self.pro_resuelto])
        self.assertIn("--aplicar", datos["salida"])
        self.assertNotIn("comando", datos)
        self.assertIn("# Cosas 1.2.4", datos["notas"])
        self.assertIn("Se rompía (`%s`): Ya no" % self.pro_resuelto, datos["notas"])
        self.assertFalse((self.repo / ".cotejo" / "releases").exists())
        self.assertEqual(self.memoria.escrituras, 0)

    def test_con_tag_solo_lo_de_despues(self):
        self.git("tag", "v1.2.3")
        _, datos = self.release()
        self.assertEqual(datos["desde"]["tag"], "v1.2.3")
        self.assertRegex(datos["desde"]["fecha"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual([t["id"] for t in datos["tareas"]], ["h2"])
        self.assertEqual([d["id"] for d in datos["decisiones"]], [self.dec_nueva])
        self.assertEqual([p["id"] for p in datos["problemas"]], [self.pro_resuelto])
        self.assertTrue(any("sin fecha" in a for a in datos["avisos"]))
        self.assertIn("desde: v1.2.3", datos["notas"])

    def test_se_niega_nombrando_las_tareas_sin_aprobar(self):
        self.memoria.proyecto.tareas.append(
            modelo.Tarea("Falta esta", id="a1", version="v1.2.4", agente="opus"))
        for args in ((), ("--aplicar",)):
            with self.subTest(args=args):
                codigo, datos = self.release(*args)
                self.assertNotEqual(codigo, 0)
                self.assertIn("a1", datos["error"])
                self.assertIn("Falta esta", datos["error"])
        self.assertFalse(self.notas().exists())

    def test_aplicar_escribe_devuelve_el_tag_y_no_etiqueta(self):
        proyecto_md = (self.repo / ".cotejo" / "proyecto.md").read_bytes()
        codigo, datos = self.release("--aplicar")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(datos["hecho"], "escrita")
        self.assertEqual(datos["archivo"], ".cotejo/releases/v1.2.4.md")
        self.assertEqual(self.notas().read_text(encoding="utf-8"), datos["notas"])
        self.assertIn("tag -a v1.2.4", datos["comando"])
        self.assertIn(datos["comando"], datos["salida"])
        # Ni etiqueta ni toca `version:`: eso es de la persona y del tag.
        self.assertEqual(self.git("tag", "--list"), "")
        self.assertEqual((self.repo / ".cotejo" / "proyecto.md").read_bytes(), proyecto_md)

    def test_aplicar_es_idempotente(self):
        self.release("--aplicar")
        antes = self.notas().read_bytes()
        codigo, datos = self.release("--aplicar")
        self.assertEqual((codigo, datos["hecho"]), (0, "ya-estaba"))
        self.assertEqual(self.notas().read_bytes(), antes)

    def test_otro_contenido_se_niega_y_reemplazar_con_hash_lo_reescribe(self):
        self.release("--aplicar")
        self.notas().write_text("retocadas a mano\n", encoding="utf-8")
        codigo, datos = self.release("--aplicar")
        self.assertEqual(codigo, 4)
        self.assertIn("--reemplazar", datos["salida"])
        self.assertEqual(self.notas().read_text(encoding="utf-8"), "retocadas a mano\n")
        codigo, _ = self.release("--aplicar", "--reemplazar", "000000000000")
        self.assertEqual(codigo, 4)
        hash_actual = almacen.version_de(b"retocadas a mano\n")
        codigo, datos = self.release("--aplicar", "--reemplazar", hash_actual)
        self.assertEqual((codigo, datos["hecho"]), (0, "reescrita"))
        self.assertEqual(self.notas().read_text(encoding="utf-8"), datos["notas"])

    def test_version_ya_etiquetada_o_que_no_sube_o_basura(self):
        self.git("tag", "v1.2.4")  # la declarada ya está: la en curso pasa a 1.2.5
        for version, texto in (("1.2.4", "no sube"), ("1.0.0", "no sube"), ("nada", "versión")):
            with self.subTest(version=version):
                codigo, datos = self.release("--version", version)
                self.assertNotEqual(codigo, 0)
                self.assertIn(texto, datos["error"])
        self.git("tag", "v1.3.0", "HEAD")
        self.git("tag", "-d", "v1.2.4")
        codigo, datos = self.release("--version", "1.3.0")
        self.assertNotEqual(codigo, 0)

    def test_tag_que_existe_fuera_de_head(self):
        self.git("switch", "-q", "-c", "otra")
        (self.repo / "OTRO").write_text("x\n", encoding="utf-8")
        self.git("add", "OTRO")
        self.git("commit", "-q", "-m", "otro")
        self.git("tag", "v1.2.4")
        self.git("switch", "-q", "-")
        codigo, datos = self.release()
        self.assertNotEqual(codigo, 0)
        self.assertIn("ya está etiquetada", datos["error"])

    def test_sin_proyecto_ensayo_con_aviso_y_aplicar_se_niega(self):
        self.memoria.carpeta_de = lambda proyecto: None
        with mock.patch("tareas.version_verbo.Path.cwd", return_value=self.repo):
            codigo, datos = self.correr("release")
            self.assertEqual(codigo, 0, datos)
            self.assertIsNone(datos["proyecto"])
            self.assertEqual(datos["tareas"], [])
            self.assertTrue(datos["avisos"])
            codigo, datos = self.correr("release", "--aplicar")
        self.assertNotEqual(codigo, 0)
        self.assertFalse(self.notas().exists())


class FechasDeCierre(unittest.TestCase):
    """`resolver` y aceptar una decisión anotan cuándo: es lo que `release` compara con el tag."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.alm = almacen.Almacen(Path(temporal.name))

    def test_aceptar_anota_aceptada_el(self):
        entrada = self.alm.crear("decision", "Una")
        with mock.patch("tareas.almacen._hoy", return_value="2031-02-03"):
            aceptada, _ = decision.aceptar(self.alm, entrada.id, entrada.version)
        self.assertEqual(aceptada.datos["aceptada_el"], "2031-02-03")

    def test_escribir_release_valida_la_etiqueta(self):
        with self.assertRaises(ValueError):
            self.alm.escribir_release("../fuera", "x")
        hecho, ruta, _ = self.alm.escribir_release("v0.1.0", "notas\n")
        self.assertEqual((hecho, ruta), ("escrita", "releases/v0.1.0.md"))
        self.assertIsNotNone(self.alm.release("v0.1.0"))
        self.assertIsNone(self.alm.release("v9.9.9"))



class GitConRutasLargas(unittest.TestCase):
    """En Windows, git no lee los tags de una raíz de ~240 caracteres sin `core.longpaths`: la
    publicada salía None y `release` no veía el tag (run de windows.yml del 2026-10-10)."""

    def test_en_windows_va_con_longpaths_y_fuera_no(self):
        from tareas import version
        with mock.patch("tareas.rutas.sistema", return_value="windows"):
            self.assertEqual(version.comando_git("C:/r", "tag")[:3],
                             ["git", "-c", "core.longpaths=true"])
        with mock.patch("tareas.rutas.sistema", return_value="linux"):
            self.assertEqual(version.comando_git("/r", "tag"), ["git", "-C", "/r", "tag"])

if __name__ == "__main__":
    unittest.main()
