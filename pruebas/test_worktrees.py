"""Un worktree por despacho (B3): cada tarea de un repo se hace en su carpeta y su rama.

Todo corre contra repos de git temporales, vaults de mentira y carpetas de worktrees y de
registro temporales (`apoyo.PruebaDeCLI` las redirige): nada toca el repo de Cotejo, el vault de
verdad ni la carpeta de estado de quien corre las pruebas.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI, PruebaDeEnrutador, proyecto

from enrutador import verbos
from tareas import worktrees

HAY_GIT = shutil.which("git") is not None


def git(carpeta, *args):
    return subprocess.run(
        ["git", "-C", str(carpeta), "-c", "user.name=Prueba", "-c", "user.email=p@p",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True).stdout.strip()


def repo_de_prueba(carpeta):
    """Un repo con un commit en `main`. Nunca el checkout de Cotejo."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    git(carpeta, "init", "-q", "-b", "main")
    (carpeta / "a.txt").write_text("uno\n", encoding="utf-8")
    git(carpeta, "add", "-A")
    git(carpeta, "commit", "-q", "-m", "base")
    return carpeta


def ramas(repo):
    return git(repo, "branch", "--format=%(refname:short)").splitlines()


def py(codigo):
    return shlex.join([sys.executable, "-c", codigo])


class Nombres(unittest.TestCase):
    def test_un_id_con_marca_queda_tal_cual(self):
        self.assertEqual(worktrees.seguro("cotejo-bndz54"), "cotejo-bndz54")
        self.assertEqual(worktrees.rama_de("cotejo-bndz54"), "cotejo/cotejo-bndz54")

    def test_un_id_de_nota_y_linea_vale_como_carpeta_y_como_rama(self):
        # `:` y `/` no valen en una carpeta de Windows ni en una rama.
        nombre = worktrees.seguro("01-Proyectos/Uno.md:3")
        self.assertRegex(nombre, r"^[A-Za-z0-9_-]+$")
        self.assertNotEqual(nombre, worktrees.seguro("01-Proyectos/Uno.md:4"))

    def test_dentro_compara_rutas_y_no_textos(self):
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            self.assertTrue(worktrees.dentro(raiz / "a" / "b", raiz / "a"))
            self.assertTrue(worktrees.dentro(raiz / "a", raiz / "a"))
            # «a-b» empieza por «a» pero no está dentro.
            self.assertFalse(worktrees.dentro(raiz / "a-b", raiz / "a"))

    def test_la_carpeta_por_defecto_es_la_de_estado_y_se_puede_mover(self):
        self.assertEqual(worktrees.carpeta_base(), worktrees.BASE)
        self.assertEqual(worktrees.carpeta_base("/otra/parte"), Path("/otra/parte"))
        with mock.patch.dict(os.environ, {"COTEJO_WORKTREES": "/del/entorno"}):
            self.assertEqual(worktrees.carpeta_base("/otra/parte"), Path("/del/entorno"))


@unittest.skipUnless(HAY_GIT, "sin git")
class CrearYRetirar(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        self.repo = repo_de_prueba(raiz / "repo")
        self.base = raiz / "wt"
        for parche in (mock.patch.object(worktrees, "REGISTRO", raiz / "registro"),
                       mock.patch.object(worktrees, "BASE", self.base)):
            parche.start()
            self.addCleanup(parche.stop)

    def plan(self, tarea="cotejo-a1"):
        return worktrees.planear(tarea, self.repo, self.base)

    def test_fuera_de_un_repo_no_hay_worktree_y_no_es_un_error(self):
        with tempfile.TemporaryDirectory() as suelta:
            self.assertIsNone(worktrees.planear("cotejo-a1", suelta, self.base))
        self.assertIsNone(worktrees.planear("cotejo-a1", None, self.base))

    def test_planear_no_crea_nada(self):
        plan = self.plan()
        self.assertEqual(plan["rama"], "cotejo/cotejo-a1")
        self.assertEqual(Path(plan["ruta"]), self.base / "cotejo-a1")
        self.assertFalse(self.base.exists())
        self.assertNotIn("cotejo/cotejo-a1", ramas(self.repo))

    def test_dentro_del_repo_se_rechaza(self):
        with self.assertRaises(worktrees.ErrorWorktree) as error:
            worktrees.planear("cotejo-a1", self.repo, self.repo / ".wt")
        self.assertIn("dentro de el repo", error.exception.mensaje)

    def test_dentro_del_vault_se_rechaza(self):
        vault = self.base.parent / "vault"
        with self.assertRaises(worktrees.ErrorWorktree) as error:
            worktrees.planear("cotejo-a1", self.repo, vault / "wt", vedadas=[vault])
        self.assertIn("vault", error.exception.mensaje)

    def test_crea_la_rama_y_la_carpeta_y_lo_registra(self):
        hecho = worktrees.crear("cotejo-a1", self.plan())
        ruta = Path(hecho["ruta"])
        self.assertTrue((ruta / "a.txt").is_file())
        self.assertEqual(git(ruta, "symbolic-ref", "--short", "HEAD"), "cotejo/cotejo-a1")
        self.assertFalse(hecho["reutilizado"])
        registrado = worktrees.de_tarea("cotejo-a1")
        self.assertEqual((registrado["rama"], registrado["existe"]), ("cotejo/cotejo-a1", True))
        self.assertEqual(worktrees.carpeta_de("cotejo-a1"), str(ruta))
        self.assertEqual([w["tarea"] for w in worktrees.todos()], ["cotejo-a1"])

    def test_despachar_otra_vez_la_misma_tarea_sigue_donde_quedo(self):
        primero = worktrees.crear("cotejo-a1", self.plan())
        (Path(primero["ruta"]) / "nuevo.txt").write_text("a medias\n", encoding="utf-8")
        segundo = worktrees.crear("cotejo-a1", self.plan())
        self.assertTrue(segundo["reutilizado"])
        self.assertTrue((Path(segundo["ruta"]) / "nuevo.txt").exists())

    def test_si_la_rama_sigue_pero_la_carpeta_no_se_rehace_con_sus_commits(self):
        hecho = worktrees.crear("cotejo-a1", self.plan())
        ruta = Path(hecho["ruta"])
        (ruta / "b.txt").write_text("b\n", encoding="utf-8")
        git(ruta, "add", "-A")
        git(ruta, "commit", "-q", "-m", "trabajo")
        self.assertTrue(worktrees.retirar("cotejo-a1")["retirado"])
        otra = worktrees.crear("cotejo-a1", self.plan())
        self.assertTrue((Path(otra["ruta"]) / "b.txt").exists())

    def test_una_carpeta_ajena_en_su_sitio_no_se_pisa(self):
        ajena = self.base / "cotejo-a1"
        ajena.mkdir(parents=True)
        (ajena / "mio.txt").write_text("no me borres\n", encoding="utf-8")
        with self.assertRaises(worktrees.ErrorWorktree):
            worktrees.crear("cotejo-a1", self.plan())
        self.assertTrue((ajena / "mio.txt").exists())

    def test_retirar_quita_la_carpeta_pero_no_la_rama(self):
        hecho = worktrees.crear("cotejo-a1", self.plan())
        resultado = worktrees.retirar("cotejo-a1")
        self.assertTrue(resultado["retirado"])
        self.assertFalse(Path(hecho["ruta"]).exists())
        self.assertIn("cotejo/cotejo-a1", ramas(self.repo))
        self.assertIsNone(worktrees.de_tarea("cotejo-a1"))

    def test_con_cambios_sin_commitear_no_se_retira(self):
        hecho = worktrees.crear("cotejo-a1", self.plan())
        (Path(hecho["ruta"]) / "a.txt").write_text("cambiado\n", encoding="utf-8")
        resultado = worktrees.retirar("cotejo-a1")
        self.assertFalse(resultado["retirado"])
        self.assertIn("sin commitear", resultado["motivo"])
        self.assertTrue(Path(hecho["ruta"]).exists())
        self.assertIsNotNone(worktrees.de_tarea("cotejo-a1"))

    def test_una_carpeta_borrada_a_mano_se_olvida_al_retirar(self):
        hecho = worktrees.crear("cotejo-a1", self.plan())
        shutil.rmtree(hecho["ruta"])
        self.assertFalse(worktrees.de_tarea("cotejo-a1")["existe"])
        self.assertIsNone(worktrees.carpeta_de("cotejo-a1"))
        self.assertTrue(worktrees.retirar("cotejo-a1")["retirado"])
        self.assertNotIn(str(hecho["ruta"]), git(self.repo, "worktree", "list"))

    def test_sin_nada_registrado_no_hay_nada_que_retirar(self):
        self.assertEqual(worktrees.retirar("cotejo-zz"), {"retirado": False, "registrado": False})


@unittest.skipUnless(HAY_GIT, "sin git")
class DespacharRepoSinCommits(PruebaDeEnrutador):
    """Un repo recién `init`ado sin commits no tiene HEAD: se dice antes de tomar la tarea
    (v1.2.5), en vez del «referencia inválida: HEAD» de `git worktree add`."""

    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.repo = Path(fuera.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.escribir_nota("Uno.md", proyecto("- [ ] Algo #agente/haiku ^cotejo-sc"))
        self.escribir_config({"proyectos": {"Uno": str(self.repo)}})

    def test_lo_dice_y_no_toma_la_tarea(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-sc")
        self.assertEqual(codigo, verbos.ERROR, datos)
        self.assertIn("no tiene ningún commit", datos["error"])
        self.assertIn("haz uno", datos["error"])
        self.assertIn("sigue pendiente", datos["salida"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])
        self.assertEqual(self.despachados()[-1]["rechazo"], "sin_commits")

    def test_con_un_commit_ya_despacha(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "inicial")
        codigo, datos = self.correr("despachar", "cotejo-sc")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertTrue(datos["worktree"]["creado"])


class Despachar(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.repo = repo_de_prueba(Path(fuera.name) / "repo")
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo de los tags #agente/haiku ^cotejo-asig",
            "- [ ] Sin marca todavía #agente/haiku",
        ))
        self.escribir_config({"proyectos": {"Uno": str(self.repo)}})

    def test_crea_su_worktree_con_rama_propia_fuera_del_repo_y_del_vault(self):
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertTrue(datos["aislado"])
        worktree = datos["worktree"]
        self.assertEqual(worktree["rama"], "cotejo/cotejo-asig")
        self.assertEqual(Path(worktree["ruta"]), self.worktrees_base / "cotejo-asig")
        self.assertTrue(worktree["creado"])
        self.assertFalse(worktrees.dentro(worktree["ruta"], self.repo))
        self.assertFalse(worktrees.dentro(worktree["ruta"], self.vault))
        self.assertIn("cotejo/cotejo-asig", ramas(self.repo))
        # El encargo lo manda ahí, no al repo que comparten todos.
        self.assertIn(worktree["ruta"], datos["salida"])
        self.assertIn("cotejo/cotejo-asig", datos["salida"])

    def test_despachos_dice_donde_quedo(self):
        self.correr("despachar", "cotejo-asig")
        despacho, = self.despachados()
        self.assertEqual(despacho["worktree"]["rama"], "cotejo/cotejo-asig")
        _, crudo = self.correr("despachos")
        self.assertEqual(crudo["despachos"][-1]["worktree"]["rama"], "cotejo/cotejo-asig")

    def test_revisar_dice_donde_quedo_y_si_sigue_ahi(self):
        _, datos = self.correr("despachar", "cotejo-asig")
        _, revision = self.correr("revisar")
        fila, = revision["repartidas"]
        self.assertEqual(fila["worktree"]["ruta"], datos["worktree"]["ruta"])
        self.assertTrue(fila["worktree"]["existe"])
        worktrees.retirar("cotejo-asig")
        _, revision = self.correr("revisar")
        self.assertFalse(revision["repartidas"][0]["worktree"]["existe"])

    def test_sin_aislar_trabaja_en_el_proyecto_como_antes(self):
        codigo, datos = self.correr("despachar", "cotejo-asig", "--sin-aislar")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["aislado"])
        self.assertEqual(datos["sin_aislar"], "--sin-aislar")
        self.assertNotIn("cotejo/cotejo-asig", ramas(self.repo))
        self.assertIn(f"El proyecto vive en {self.repo}", datos["salida"])
        self.assertNotIn("worktree", self.despachados()[0])

    def test_la_config_puede_apagarlo_para_todos(self):
        self.escribir_config({"proyectos": {"Uno": str(self.repo)},
                              "worktrees": {"aislar": False}})
        _, datos = self.correr("despachar", "cotejo-asig")
        self.assertFalse(datos["aislado"])
        self.assertNotIn("cotejo/cotejo-asig", ramas(self.repo))

    def test_una_tarea_que_no_es_de_un_repo_se_despacha_como_siempre(self):
        self.escribir_config({})
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["aislado"])
        self.assertIn("no es de un repo", datos["sin_aislar"])

    def test_el_ensayo_dice_donde_caeria_sin_crear_nada(self):
        antes = self.leer_nota("Uno.md")
        _, datos = self.correr("despachar", "cotejo-asig", "--simular")
        self.assertFalse(datos["worktree"]["creado"])
        self.assertFalse(self.worktrees_base.exists())
        self.assertNotIn("cotejo/cotejo-asig", ramas(self.repo))
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_la_carpeta_se_puede_mover_por_config(self):
        otra = self.worktrees_base.parent / "otra"
        self.escribir_config({"proyectos": {"Uno": str(self.repo)},
                              "worktrees": {"carpeta": str(otra)}})
        _, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(Path(datos["worktree"]["ruta"]), otra / "cotejo-asig")

    def test_una_carpeta_dentro_del_repo_se_rechaza_sin_tomar_la_tarea(self):
        self.escribir_config({"proyectos": {"Uno": str(self.repo)},
                              "worktrees": {"carpeta": str(self.repo / "wt")}})
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("dentro de el repo", datos["error"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.despachados()[0]["rechazo"], "worktree")

    def test_una_carpeta_dentro_del_vault_se_rechaza_sin_tomar_la_tarea(self):
        # El repo de Cotejo vive dentro del vault: un worktree ahí metería sus `- [ ]` como
        # tareas de verdad.
        self.escribir_config({"proyectos": {"Uno": str(self.repo)},
                              "worktrees": {"carpeta": str(self.vault / "wt")}})
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("vault", datos["error"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_si_no_se_puede_crear_la_tarea_se_suelta_con_el_motivo(self):
        ajena = self.worktrees_base / "cotejo-asig"
        ajena.mkdir(parents=True)
        (ajena / "mio.txt").write_text("no me borres\n", encoding="utf-8")
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("se soltó", datos["salida"])
        _, tareas = self.correr("tareas", "--todas")
        tarea = next(t for t in tareas["tareas"] if t["id"] == "cotejo-asig")
        # Pendiente y con la asignación que puso la persona: un despacho fallido no se la
        # quita, o el siguiente `despachar` preguntaría otra vez el modelo (cotejo-fyj565).
        self.assertEqual((tarea["estado"], tarea["agente"]), ("pendiente", "haiku"))
        self.assertIn("worktree", tarea["motivo"])
        self.assertTrue((ajena / "mio.txt").exists())

    def test_una_tarea_sin_marca_se_nombra_por_el_id_que_le_queda_al_tomarla(self):
        _, tareas = self.correr("tareas")
        sin_marca = next(t for t in tareas["tareas"] if t["texto"] == "Sin marca todavía")
        _, datos = self.correr("despachar", sin_marca["id"])
        definitivo = datos["tarea"]["id"]
        self.assertNotEqual(definitivo, sin_marca["id"])
        self.assertEqual(datos["worktree"]["rama"], f"cotejo/{definitivo}")
        self.assertEqual(worktrees.de_tarea(definitivo)["tarea"], definitivo)


@unittest.skipUnless(HAY_GIT, "sin git")
class EntregarYComprobar(PruebaDeEnrutador):
    """`entregar` y `comprobar` encuentran solos el worktree de la tarea."""

    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.repo = repo_de_prueba(Path(fuera.name) / "repo")
        self.otra = Path(fuera.name) / "otra"
        self.otra.mkdir()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/haiku ^cotejo-asig"))
        self.escribir_config({"proyectos": {"Uno": str(self.repo)}})
        _, datos = self.correr("despachar", "cotejo-asig")
        self.ruta = datos["worktree"]["ruta"]

    def test_entregar_sin_repo_anota_la_rama_del_worktree(self):
        with mock.patch("os.getcwd", return_value=str(self.otra)):
            codigo, datos = self.correr("entregar", "cotejo-asig", "--evidencia", "x",
                                        "--prueba", py("import os; print(os.getcwd())"))
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(datos["git"]["rama"], "cotejo/cotejo-asig")
        self.assertEqual(os.path.realpath(datos["pruebas"][0]["salida"].strip()),
                         os.path.realpath(self.ruta))

    def test_comprobar_corre_en_el_worktree_aunque_se_entregara_desde_otra_carpeta(self):
        self.correr("entregar", "cotejo-asig", "--evidencia", "x", "--repo", str(self.otra),
                    "--prueba", py("import os; print(os.getcwd())"))
        _, datos = self.correr("comprobar", "cotejo-asig")
        prueba, = datos["pruebas"]
        self.assertEqual(prueba["carpeta"], self.ruta)
        self.assertEqual(prueba["carpeta_entrega"], str(self.otra))
        self.assertEqual(os.path.realpath(prueba["salida"].strip()), os.path.realpath(self.ruta))
        self.assertEqual(datos["worktree"], self.ruta)

    def test_sin_worktree_comprobar_usa_la_carpeta_de_la_entrega(self):
        self.correr("entregar", "cotejo-asig", "--evidencia", "x", "--repo", str(self.otra),
                    "--prueba", py("print('ok')"))
        worktrees.retirar("cotejo-asig")
        _, datos = self.correr("comprobar", "cotejo-asig")
        self.assertEqual(datos["pruebas"][0]["carpeta"], str(self.otra))
        self.assertNotIn("worktree", datos)


@unittest.skipUnless(HAY_GIT, "sin git")
class VerboWorktrees(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.repo = repo_de_prueba(Path(fuera.name) / "repo")
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Una #agente/haiku ^cotejo-una",
            "- [ ] Otra #agente/haiku ^cotejo-otra"))
        self.escribir_config({"proyectos": {"Uno": str(self.repo)}})
        self.correr("despachar", "cotejo-una")
        self.correr("despachar", "cotejo-otra")

    def test_lista_cada_uno_con_el_estado_de_su_tarea(self):
        _, datos = self.correr("worktrees")
        por_tarea = {w["tarea"]: w for w in datos["worktrees"]}
        self.assertEqual(set(por_tarea), {"cotejo-una", "cotejo-otra"})
        self.assertEqual(por_tarea["cotejo-una"]["estado"], "en-curso")
        self.assertFalse(por_tarea["cotejo-una"]["sobra"])

    def test_limpiar_solo_retira_los_que_sobran_y_no_toca_ninguna_tarea(self):
        self.correr("bloquear", "cotejo-otra", "--motivo", "para probar")
        antes = self.leer_nota("Uno.md")
        _, datos = self.correr("worktrees", "--limpiar")
        por_tarea = {w["tarea"]: w for w in datos["worktrees"]}
        self.assertTrue(por_tarea["cotejo-otra"]["retirado"])
        self.assertNotIn("retirado", por_tarea["cotejo-una"])
        self.assertIsNotNone(worktrees.carpeta_de("cotejo-una"))
        self.assertIsNone(worktrees.de_tarea("cotejo-otra"))
        self.assertIn("cotejo/cotejo-otra", ramas(self.repo))  # la rama se queda
        self.assertEqual(self.leer_nota("Uno.md"), antes)


@unittest.skipUnless(HAY_GIT, "sin git")
class FuenteRepo(PruebaDeEnrutador):
    """En la fuente de repos el proyecto *es* el repo: no hace falta `enrutador.proyectos`."""

    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.repo = repo_de_prueba(Path(fuera.name) / "app")
        (self.repo / ".cotejo").mkdir()
        (self.repo / ".cotejo" / "tareas.md").write_text(
            "- [ ] Arreglar el login #agente/haiku ^cotejo-log\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "tareas")
        parche = mock.patch.dict(os.environ, {"COTEJO_FUENTE": "repo",
                                              "COTEJO_REPOS": str(self.repo)})
        parche.start()
        self.addCleanup(parche.stop)

    def test_despachar_crea_el_worktree_del_repo_del_proyecto(self):
        codigo, datos = self.correr("despachar", "cotejo-log")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertEqual(datos["worktree"]["rama"], "cotejo/cotejo-log")
        self.assertEqual(os.path.realpath(datos["worktree"]["repo"]),
                         os.path.realpath(self.repo))
        self.assertIn("cotejo/cotejo-log", ramas(self.repo))
        # El worktree trae su copia de `.cotejo/tareas.md`, y no por eso cuenta como otro
        # proyecto: sigue habiendo uno solo, con la tarea tomada.
        _, tareas = self.correr("tareas", "--todas")
        self.assertEqual([t["id"] for t in tareas["tareas"]], ["cotejo-log"])


if __name__ == "__main__":
    unittest.main()
