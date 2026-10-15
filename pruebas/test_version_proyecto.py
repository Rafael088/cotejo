"""La versión del proyecto del usuario (v1.2.4, `tareas/version.py`), no la de Cotejo.

La publicada sale del último tag semver y la en curso de `version:` en `proyecto.md`; cuando el
tag la alcanza, la en curso es la siguiente de parche sin escribir nada. Las funciones puras se
prueban solas; la E/S, contra un repo de git de mentira con y sin tags.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import version
from tareas.almacen import Almacen
from tareas.version import Semver


class Parsear(unittest.TestCase):

    def test_con_y_sin_v(self):
        self.assertEqual(version.parsear("1.2.3"), Semver(1, 2, 3))
        self.assertEqual(version.parsear(" v10.0.12 "), Semver(10, 0, 12))

    def test_lo_que_no_es_una_version_publicada_es_none(self):
        for texto in ("", None, "1.2", "v1.2", "1.2.3.4", "v1.2.3-rc1", "01.2.3", "x1.2.3",
                      "beta", "V1.2.3"):
            with self.subTest(texto=texto):
                self.assertIsNone(version.parsear(texto))

    def test_texto_y_etiqueta(self):
        v = Semver(1, 2, 4)
        self.assertEqual(str(v), "1.2.4")
        self.assertEqual(v.etiqueta, "v1.2.4")

    def test_compara_como_numeros_no_como_texto(self):
        self.assertGreater(version.parsear("1.10.0"), version.parsear("1.9.9"))


class Calcular(unittest.TestCase):

    def test_siguiente_parche(self):
        self.assertEqual(version.siguiente_parche("v1.2.3"), Semver(1, 2, 4))
        self.assertEqual(version.siguiente_parche(Semver(0, 9, 0)), Semver(0, 9, 1))
        self.assertIsNone(version.siguiente_parche("nada"))

    def test_mas_alta_ignora_lo_que_no_es_semver(self):
        tags = ["v1.1.0", "v1.10.0", "v1.9.0", "beta", "v2.0.0-rc1", "1.2.0"]
        self.assertEqual(version.mas_alta(tags), Semver(1, 10, 0))
        self.assertIsNone(version.mas_alta(["beta", "v1"]))
        self.assertIsNone(version.mas_alta([]))

    def test_en_curso_es_la_declarada_mientras_ningun_tag_la_alcance(self):
        self.assertEqual(version.en_curso("v1.2.3", "1.2.4"), Semver(1, 2, 4))
        self.assertEqual(version.en_curso("v1.2.3", "1.3.0"), Semver(1, 3, 0))

    def test_cuando_el_tag_la_alcanza_es_la_siguiente_de_parche(self):
        self.assertEqual(version.en_curso("v1.2.4", "1.2.4"), Semver(1, 2, 5))
        self.assertEqual(version.en_curso("v1.3.0", "1.2.4"), Semver(1, 3, 1))

    def test_sin_declarada_o_sin_tags(self):
        self.assertEqual(version.en_curso("v1.2.3", None), Semver(1, 2, 4))
        self.assertEqual(version.en_curso(None, "0.1.0"), Semver(0, 1, 0))
        self.assertIsNone(version.en_curso(None, None))
        self.assertEqual(version.en_curso("v1.2.3", "no-semver"), Semver(1, 2, 4))

    def test_inicial(self):
        self.assertEqual(version.inicial(None), Semver(0, 1, 0))
        self.assertEqual(version.inicial("v1.2.3"), Semver(1, 2, 4))


@unittest.skipUnless(shutil.which("git"), "hace falta git")
class EnUnRepo(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "LEEME").write_text("hola\n", encoding="utf-8")
        self.git("add", "LEEME")
        self.git("commit", "-q", "-m", "primero")

    def git(self, *args):
        entorno = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=prueba",
                        "-c", "user.email=prueba@ejemplo", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgsign=false", *args],
                       check=True, capture_output=True, env=entorno)

    def proyecto(self, **frontmatter):
        cabecera = "".join(f"{k}: {v}\n" for k, v in frontmatter.items())
        ruta = self.repo / ".cotejo" / "proyecto.md"
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(f"---\nid: proyecto\n{cabecera}---\n# Mi repo\n", encoding="utf-8")

    def test_sin_tags_ni_version_no_hay_nada(self):
        self.assertIsNone(version.publicada(self.repo))
        self.assertEqual(version.declarada(self.repo), (None, None))
        self.assertEqual(version.estado(self.repo), {
            "publicada": None, "tag": None, "declarada": None, "en_curso": None,
            "calculada": False, "valida": True})

    def test_sin_tags_manda_la_declarada(self):
        self.proyecto(version="0.1.0")
        estado = version.estado(self.repo)
        self.assertEqual(estado["en_curso"], "0.1.0")
        self.assertFalse(estado["calculada"])

    def test_la_publicada_es_el_tag_semver_mas_alto(self):
        self.git("tag", "v1.9.0")
        self.git("tag", "v1.10.0")
        self.git("tag", "beta")
        self.git("tag", "v2.0.0-rc1")
        self.assertEqual(version.publicada(self.repo), Semver(1, 10, 0))

    def test_un_tag_que_no_alcanza_head_no_cuenta(self):
        self.git("tag", "v1.0.0")
        self.git("switch", "-q", "-c", "otra")
        (self.repo / "OTRO").write_text("x\n", encoding="utf-8")
        self.git("add", "OTRO")
        self.git("commit", "-q", "-m", "otro")
        self.git("tag", "v9.0.0")
        self.git("switch", "-q", "-")
        self.assertEqual(version.publicada(self.repo), Semver(1, 0, 0))

    def test_con_tag_por_debajo_de_la_declarada_la_en_curso_es_la_declarada(self):
        self.git("tag", "v1.2.3")
        self.proyecto(version="1.3.0")
        estado = version.estado(self.repo)
        self.assertEqual((estado["publicada"], estado["tag"], estado["en_curso"]),
                         ("1.2.3", "v1.2.3", "1.3.0"))
        self.assertFalse(estado["calculada"])

    def test_cuando_el_tag_alcanza_la_declarada_se_calcula_sin_escribir(self):
        self.proyecto(version="1.2.4")
        antes = (self.repo / ".cotejo" / "proyecto.md").read_bytes()
        self.git("tag", "v1.2.4")
        estado = version.estado(self.repo)
        self.assertEqual((estado["declarada"], estado["en_curso"]), ("1.2.4", "1.2.5"))
        self.assertTrue(estado["calculada"])
        self.assertEqual((self.repo / ".cotejo" / "proyecto.md").read_bytes(), antes)

    def test_una_version_escrita_que_no_es_semver_se_avisa(self):
        self.git("tag", "v1.0.0")
        self.proyecto(version="pronto")
        estado = version.estado(self.repo)
        self.assertEqual(estado["declarada"], "pronto")
        self.assertEqual(estado["en_curso"], "1.0.1")
        self.assertFalse(estado["valida"])

    def test_fuera_de_un_repo_no_hay_publicada(self):
        with tempfile.TemporaryDirectory() as suelta:
            self.assertIsNone(version.publicada(suelta))

    def test_leer_proyecto_sigue_dando_el_hash_aunque_tenga_version(self):
        # `version:` en el frontmatter no puede tapar la `version` (hash) de `leer`, que es
        # la que `editar --version` pide de vuelta.
        self.proyecto(version="1.2.4")
        alm = Almacen(self.repo)
        entrada = alm.leer("proyecto")
        self.assertEqual(entrada.como_dict()["version"], entrada.version)
        editada = alm.reescribir("proyecto", entrada.como_dict()["version"], texto="Nuevo.")
        self.assertEqual(editada.datos["version"], "1.2.4")

    def test_asegurar_sin_tags_pone_0_1_0_y_crea_proyecto_md(self):
        self.assertEqual(version.asegurar(self.repo), {"version": "0.1.0", "hecho": "puesta"})
        self.assertEqual(Almacen(self.repo).leer("proyecto").datos["version"], "0.1.0")

    def test_asegurar_con_tag_pone_la_siguiente_de_parche(self):
        self.git("tag", "v1.2.3")
        self.assertEqual(version.asegurar(self.repo)["version"], "1.2.4")

    def test_asegurar_es_idempotente_y_no_pisa_la_escrita(self):
        self.proyecto(version="3.0.0")
        antes = (self.repo / ".cotejo" / "proyecto.md").read_bytes()
        self.git("tag", "v1.0.0")
        self.assertEqual(version.asegurar(self.repo), {"version": "3.0.0", "hecho": "ya-estaba"})
        self.assertEqual((self.repo / ".cotejo" / "proyecto.md").read_bytes(), antes)

    def test_asegurar_conserva_el_cuerpo_de_un_proyecto_sin_version(self):
        self.proyecto()
        alm = Almacen(self.repo)
        alm.reescribir("proyecto", alm.leer("proyecto").version, texto="Mi objetivo.")
        self.assertTrue(version.falta(self.repo))
        version.asegurar(self.repo)
        self.assertFalse(version.falta(self.repo))
        self.assertIn("Mi objetivo.", Almacen(self.repo).leer("proyecto").cuerpo)

    def test_falta_es_falso_sin_proyecto_md(self):
        self.assertFalse(version.falta(self.repo))


if __name__ == "__main__":
    unittest.main()
