"""La evidencia estructurada de `entregar`: lo que se puede volver a comprobar sin creerle a nadie.

Todo corre contra repos de git temporales y vaults de mentira; nada toca el repo de Cotejo ni
la bitácora de verdad. Las pruebas que se anotan son `python -c ...` con el intérprete de la
prueba, para que valgan igual en Linux, macOS y Windows.
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

from apoyo import PruebaDeCLI, proyecto

from tareas import evidencia

HAY_GIT = shutil.which("git") is not None


def py(codigo):
    """Un comando de prueba como texto: el intérprete actual corriendo `codigo`."""
    return shlex.join([sys.executable, "-c", codigo])


class RepoTemporal:
    """Un repo con `main` y una rama de trabajo con dos commits, como un worktree de agente."""

    def __init__(self, raiz):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        (self.raiz / "a.txt").write_text("uno\ndos\n", encoding="utf-8")
        (self.raiz / "viejo.txt").write_text("se va a mover\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("switch", "-q", "-c", "cotejo/prueba")
        (self.raiz / "a.txt").write_text("uno\nDOS\ntres\n", encoding="utf-8")
        self.git("commit", "-q", "-am", "cambia a")
        self.git("mv", "viejo.txt", "nuevo.txt")
        (self.raiz / "b.txt").write_text("b\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "mueve y agrega")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.raiz), "-c", "user.name=Prueba", "-c", "user.email=p@p",
             "-c", "commit.gpgsign=false", *args],
            check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(HAY_GIT, "sin git")
class Git(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.tmp = Path(temporal.name)
        self.repo = RepoTemporal(self.tmp / "repo")

    def test_rama_y_commits_de_la_rama_y_no_los_de_la_base(self):
        datos = evidencia.git(self.repo.raiz)
        self.assertEqual(datos["rama"], "cotejo/prueba")
        self.assertEqual(datos["base"], "main")
        self.assertEqual([c["asunto"] for c in datos["commits"]], ["mueve y agrega", "cambia a"])
        self.assertEqual(datos["head"], self.repo.git("rev-parse", "HEAD"))
        self.assertEqual(datos["commits"][0]["hash"], datos["head"])
        self.assertFalse(datos["sin_commitear"])

    def test_resumen_del_diff_con_mas_y_menos_por_archivo(self):
        diff = evidencia.git(self.repo.raiz)["diff"]
        por_ruta = {a["ruta"]: a for a in diff["archivos"]}
        self.assertEqual(set(por_ruta), {"a.txt", "b.txt", "nuevo.txt"})
        self.assertEqual((por_ruta["a.txt"]["mas"], por_ruta["a.txt"]["menos"]), (2, 1))
        self.assertEqual((por_ruta["b.txt"]["mas"], por_ruta["b.txt"]["menos"]), (1, 0))
        self.assertEqual(diff["mas"], sum(a["mas"] for a in diff["archivos"]))

    def test_dice_si_queda_algo_sin_commitear(self):
        (self.repo.raiz / "suelto.txt").write_text("x", encoding="utf-8")
        self.assertTrue(evidencia.git(self.repo.raiz)["sin_commitear"])

    def test_sobre_la_base_misma_apunta_el_ultimo_commit(self):
        self.repo.git("switch", "-q", "main")
        datos = evidencia.git(self.repo.raiz)
        self.assertIsNone(datos["base"])
        self.assertEqual([c["asunto"] for c in datos["commits"]], ["base"])

    def test_fuera_de_un_repo_no_hay_git(self):
        fuera = self.tmp / "suelta"
        fuera.mkdir()
        self.assertIsNone(evidencia.git(fuera))
        self.assertNotIn("git", evidencia.reunir(fuera))


class Pruebas(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.tmp = temporal.name

    def test_guarda_argv_salida_y_codigo(self):
        registro = evidencia.correr_prueba(py("print('542 en verde')"), self.tmp)
        self.assertEqual(registro["argv"], [sys.executable, "-c", "print('542 en verde')"])
        self.assertEqual(registro["codigo"], 0)
        self.assertIn("542 en verde", registro["salida"])
        self.assertEqual(registro["carpeta"], self.tmp)

    def test_el_codigo_de_salida_es_el_de_verdad(self):
        registro = evidencia.correr_prueba(py("import sys; print('falla'); sys.exit(3)"), self.tmp)
        self.assertEqual(registro["codigo"], 3)

    def test_la_salida_de_error_tambien_se_guarda(self):
        registro = evidencia.correr_prueba(py("import sys; sys.stderr.write('roto')"), self.tmp)
        self.assertIn("roto", registro["salida"])

    def test_sin_shell_una_tuberia_no_es_una_tuberia(self):
        """`| cat` llega como argumentos: lo que se guarda es exactamente lo que se corrió."""
        registro = evidencia.correr_prueba(
            py("import sys; print(sys.argv[1:])") + " '|' cat", self.tmp)
        self.assertIn("['|', 'cat']", registro["salida"])

    def test_un_programa_que_no_existe_no_es_un_cero_ni_un_uno(self):
        registro = evidencia.correr_prueba("no-existe-este-programa-cotejo", self.tmp)
        self.assertIsNone(registro["codigo"])
        self.assertTrue(registro["error"])

    def test_se_corta_por_tiempo(self):
        registro = evidencia.correr_prueba(py("import time; time.sleep(5)"), self.tmp, tiempo=0.5)
        self.assertIsNone(registro["codigo"])
        self.assertIn("0.5", registro["error"])

    def test_guarda_el_final_de_una_salida_larga(self):
        registro = evidencia.correr_prueba(
            py(f"print('x' * {evidencia.SALIDA_MAX * 2}); print('RESUMEN')"), self.tmp)
        self.assertLessEqual(len(registro["salida"]), evidencia.SALIDA_MAX)
        self.assertIn("RESUMEN", registro["salida"])
        self.assertTrue(registro["salida_recortada"])

    def test_el_argv_guardado_se_puede_volver_a_correr(self):
        """Lo que hará `comprobar`: correr el argv de la bitácora y obtener lo mismo."""
        registro = evidencia.correr_prueba(py("import sys; sys.exit(7)"), self.tmp)
        otra_vez = subprocess.run(registro["argv"], cwd=registro["carpeta"])
        self.assertEqual(otra_vez.returncode, registro["codigo"])


class Entregar(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Haciéndola #en-curso #agente/opus"))
        self.trabajo = self.vault / "trabajo"
        self.trabajo.mkdir()

    def id_tarea(self):
        _, datos = self.correr("tareas")
        return datos["tareas"][0]["id"]

    def entrega(self):
        lineas = self.bitacora.read_text(encoding="utf-8").splitlines()
        return [json.loads(l) for l in lineas if json.loads(l)["operacion"] == "entregar"][-1]

    def test_anota_las_pruebas_con_argv_y_codigo(self):
        codigo, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "hecho",
                                    "--repo", str(self.trabajo),
                                    "--prueba", py("print('ok')"))
        self.assertEqual(codigo, 0)
        anotada = self.entrega()
        self.assertEqual(anotada["evidencia"], "hecho")
        prueba, = anotada["pruebas"]
        self.assertEqual(prueba["argv"][0], sys.executable)
        self.assertEqual(prueba["codigo"], 0)
        self.assertIn("ok", prueba["salida"])
        self.assertEqual(anotada["evidencia_esquema"], evidencia.ESQUEMA)
        self.assertEqual(datos["pruebas"], anotada["pruebas"])

    def test_varias_pruebas_en_orden(self):
        self.correr("entregar", self.id_tarea(), "--evidencia", "x", "--repo", str(self.trabajo),
                    "--prueba", py("print(1)"), "--prueba", py("print(2)"))
        self.assertEqual([p["salida"].strip() for p in self.entrega()["pruebas"]], ["1", "2"])

    def test_una_prueba_roja_se_entrega_pero_se_avisa(self):
        codigo, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                    "--repo", str(self.trabajo),
                                    "--prueba", py("import sys; sys.exit(1)"))
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")
        self.assertEqual(self.entrega()["pruebas"][0]["codigo"], 1)
        self.assertEqual(len(datos["avisos"]), 1)

    def test_una_prueba_que_no_se_puede_partir_no_llega_a_escribir(self):
        antes = self.leer_nota("Uno.md")
        with self.assertRaises(SystemExit):
            self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                        "--prueba", "pytest 'sin cerrar")
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_un_repo_que_no_existe_no_llega_a_escribir(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                    "--repo", str(self.vault / "no-esta"))
        self.assertNotEqual(codigo, 0)
        self.assertIn("No se escribió nada", datos["salida"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_sin_repo_ni_pruebas_sigue_valiendo_el_texto_solo(self):
        codigo, _ = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                "--repo", str(self.trabajo))
        self.assertEqual(codigo, 0)
        anotada = self.entrega()
        self.assertNotIn("git", anotada)
        self.assertNotIn("pruebas", anotada)

    def test_reentregar_no_vuelve_a_correr_las_pruebas(self):
        identificador = self.id_tarea()
        _, primera = self.correr("entregar", identificador, "--evidencia", "x",
                                 "--repo", str(self.trabajo))
        marca = self.trabajo / "corrio"
        _, segunda = self.correr("entregar", primera["tarea"]["id"], "--evidencia", "y",
                                 "--repo", str(self.trabajo),
                                 "--prueba", py(f"open({str(marca)!r}, 'w')"))
        self.assertFalse(segunda["cambio"])
        self.assertFalse(marca.exists())

    def test_las_claves_de_siempre_siguen_ahi(self):
        """La bitácora es un contrato: lo estructurado se agrega, no sustituye nada."""
        self.correr("entregar", self.id_tarea(), "--evidencia", "x", "--repo", str(self.trabajo),
                    "--prueba", py("pass"))
        anotada = self.entrega()
        for clave in ("cuando", "operacion", "id", "proyecto", "texto", "nota", "agente",
                      "de", "a", "evidencia"):
            self.assertIn(clave, anotada)

    def repo_con_proyecto(self, fecha):
        """Un repo con `.cotejo/proyecto.md` commiteado en `fecha` (AAAA-MM-DD)."""
        from tareas import almacen
        repo = RepoTemporal(self.vault / "repo")
        almacen.Almacen(repo.raiz).crear("proyecto", "Repo", "## Objetivo\nQue funcione.\n\n"
                                         "## Siguiente paso\nPruebas.\n")
        repo.git("add", "-A")
        momento = f"{fecha}T12:00:00+0000"
        subprocess.run(["git", "-C", str(repo.raiz), "-c", "user.name=Prueba", "-c",
                        "user.email=p@p", "-c", "commit.gpgsign=false", "commit", "-q", "-m",
                        "proyecto"], check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_DATE": momento,
                            "GIT_COMMITTER_DATE": momento})
        return repo

    @unittest.skipUnless(HAY_GIT, "sin git")
    def test_un_proyecto_viejo_se_avisa_sin_frenar_la_entrega(self):
        repo = self.repo_con_proyecto("2020-01-01")
        codigo, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                    "--repo", str(repo.raiz))
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")
        aviso, = [a for a in datos.get("avisos", []) if "proyecto.md" in a]
        self.assertIn("2020-01-01", aviso)
        self.assertIn("cotejo editar proyecto", aviso)

    @unittest.skipUnless(HAY_GIT, "sin git")
    def test_un_proyecto_fresco_no_se_avisa(self):
        import datetime
        repo = self.repo_con_proyecto(datetime.date.today().isoformat())
        _, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                               "--repo", str(repo.raiz))
        self.assertFalse([a for a in datos.get("avisos", []) if "proyecto.md" in a])

    @unittest.skipUnless(HAY_GIT, "sin git")
    def test_sin_cotejo_no_hay_aviso_de_proyecto(self):
        repo = RepoTemporal(self.vault / "repo")
        codigo, datos = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                    "--repo", str(repo.raiz))
        self.assertEqual(codigo, 0)
        self.assertNotIn("avisos", datos)

    @unittest.skipUnless(HAY_GIT, "sin git")
    def test_con_repo_anota_rama_commits_y_diff(self):
        repo = RepoTemporal(self.vault / "repo")
        self.correr("entregar", self.id_tarea(), "--evidencia", "x", "--repo", str(repo.raiz))
        anotada = self.entrega()
        self.assertEqual(anotada["git"]["rama"], "cotejo/prueba")
        self.assertEqual(len(anotada["git"]["commits"]), 2)
        self.assertTrue(anotada["git"]["diff"]["archivos"])

    @unittest.skipUnless(HAY_GIT, "sin git")
    def test_sin_repo_usa_la_carpeta_actual(self):
        repo = RepoTemporal(self.vault / "repo")
        antes = os.getcwd()
        os.chdir(repo.raiz)
        self.addCleanup(os.chdir, antes)
        self.correr("entregar", self.id_tarea(), "--evidencia", "x")
        self.assertEqual(self.entrega()["git"]["rama"], "cotejo/prueba")


class Comprobar(Entregar):
    """`comprobar` (B2): vuelve a correr lo que `entregar` guardó, y nada más que eso."""

    def test_sin_entrega_no_hay_nada_que_comprobar(self):
        codigo, datos = self.correr("comprobar", self.id_tarea())
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["pruebas"], [])
        self.assertIsNone(datos["sigue_igual"])

    def test_una_entrega_sin_pruebas_no_hay_nada_que_comprobar(self):
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo))
        codigo, datos = self.correr("comprobar", entregada["tarea"]["id"])
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["pruebas"], [])
        self.assertIsNone(datos["sigue_igual"])

    def test_vuelve_a_correr_y_dice_que_sigue_igual(self):
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo),
                                   "--prueba", py("print('542 en verde')"))
        codigo, datos = self.correr("comprobar", entregada["tarea"]["id"])
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["sigue_igual"])
        prueba, = datos["pruebas"]
        self.assertEqual((prueba["antes"], prueba["ahora"]), (0, 0))
        self.assertTrue(prueba["igual"])
        self.assertIn("542 en verde", prueba["salida"])
        self.assertEqual(prueba["carpeta"], str(self.trabajo))

    def test_detecta_que_el_resultado_cambio(self):
        """La prueba pasaba al entregar; algo en la carpeta cambió y ahora falla."""
        marca = self.trabajo / "marca"
        comando = py(f"import sys, os; sys.exit(1 if os.path.exists({str(marca)!r}) else 0)")
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo), "--prueba", comando)
        marca.write_text("ya está", encoding="utf-8")
        _, datos = self.correr("comprobar", entregada["tarea"]["id"])
        self.assertFalse(datos["sigue_igual"])
        prueba, = datos["pruebas"]
        self.assertEqual((prueba["antes"], prueba["ahora"]), (0, 1))
        self.assertFalse(prueba["igual"])

    def test_varias_pruebas_cada_una_con_su_resultado(self):
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo),
                                   "--prueba", py("print(1)"), "--prueba", py("import sys; sys.exit(1)"))
        _, datos = self.correr("comprobar", entregada["tarea"]["id"])
        self.assertTrue(datos["sigue_igual"])  # las dos siguen dando lo mismo que al entregar
        self.assertEqual([p["ahora"] for p in datos["pruebas"]], [0, 1])

    def test_una_carpeta_que_ya_no_existe_no_es_un_cero_ni_un_uno(self):
        """El worktree de la tarea pudo borrarse entre la entrega y el comprobar."""
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo), "--prueba", py("print('ok')"))
        shutil.rmtree(self.trabajo)
        _, datos = self.correr("comprobar", entregada["tarea"]["id"])
        prueba, = datos["pruebas"]
        self.assertIsNone(prueba["ahora"])
        self.assertTrue(prueba["error"])
        self.assertFalse(datos["sigue_igual"])

    def test_no_escribe_en_la_bitacora_ni_cambia_el_estado(self):
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo), "--prueba", py("print('ok')"))
        identificador = entregada["tarea"]["id"]
        antes = self.bitacora.read_text(encoding="utf-8")
        estado_antes = self.correr("tareas")[1]["tareas"][0]["estado"]
        self.correr("comprobar", identificador)
        self.assertEqual(self.bitacora.read_text(encoding="utf-8"), antes)
        estado_despues = self.correr("tareas")[1]["tareas"][0]["estado"]
        self.assertEqual(estado_despues, estado_antes)

    def test_un_rechazo_posterior_no_tapa_las_pruebas_de_la_entrega(self):
        """`ultimas()` se queda con lo último que trae texto; esto tiene que buscar más atrás."""
        _, entregada = self.correr("entregar", self.id_tarea(), "--evidencia", "x",
                                   "--repo", str(self.trabajo), "--prueba", py("print('ok')"))
        identificador = entregada["tarea"]["id"]
        proyectos = self.fuente.escanear(incluir_hechas=True)
        proyecto = proyectos[0]
        tarea = proyecto.tareas[0] if proyecto.tareas else proyecto.hechas[0]
        from tareas import bitacora as modulo_bitacora
        modulo_bitacora.anotar("rechazar", proyecto, tarea, de="por-validar", a="pendiente",
                               motivo="le falta tal cosa")
        _, datos = self.correr("comprobar", identificador)
        prueba, = datos["pruebas"]
        self.assertEqual(prueba["antes"], 0)


if __name__ == "__main__":
    unittest.main()
