"""La vista de revisión del board (B4): qué enseña una entrega y qué hace Aprobar.

La lógica vive en `tareas/revision.py`, sin GTK, y se prueba aquí entera: qué dice la carta a
partir de la evidencia, cómo se parte un diff, volver a comprobar y lo que pasa al aprobar
—**ofrecer** integrar la rama, nunca integrarla sin que la persona diga que sí—. Todo corre
contra repos de git temporales, con el registro de worktrees redirigido: nada toca el repo de
Cotejo, el vault de verdad ni la carpeta de estado de quien corre las pruebas.

Al final, unas pocas pruebas construyen los widgets de verdad con un Board falso; necesitan
GTK y pantalla, y sin ellas se saltan.
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import evidencia, modelo, revision, worktrees

HAY_GIT = shutil.which("git") is not None


def git(carpeta, *args):
    return subprocess.run(
        ["git", "-C", str(carpeta), "-c", "user.name=Prueba", "-c", "user.email=p@p",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True).stdout.strip()


def py(codigo):
    return shlex.join([sys.executable, "-c", codigo])


def entrega(pruebas=(), archivos=None, commits=1, **git_extra):
    """Una anotación de `entregar` como la que deja la CLI, con lo justo para la carta."""
    datos = {"operacion": "entregar", "id": "cotejo-aaa111", "evidencia": "hecho"}
    if pruebas:
        datos["pruebas"] = [{"comando": f"prueba {i}", "codigo": codigo, "carpeta": "/tmp",
                             "salida": ""} for i, codigo in enumerate(pruebas)]
    if archivos is not None or commits:
        archivos = archivos or []
        datos["git"] = {"rama": "cotejo/cotejo-aaa111", "head": "b" * 40, "desde": "a" * 40,
                        "commits": [{"hash": f"{i:040d}", "asunto": f"commit {i}"}
                                    for i in range(commits)],
                        "diff": {"archivos": archivos,
                                 "mas": sum(a["mas"] or 0 for a in archivos),
                                 "menos": sum(a["menos"] or 0 for a in archivos)},
                        **git_extra}
    return datos


class LaCarta(unittest.TestCase):
    """Qué dice la carta de *Para comprobar* a partir de la evidencia estructurada."""

    def test_sin_evidencia_estructurada_la_carta_se_queda_como_estaba(self):
        self.assertIsNone(revision.resumen(None))
        self.assertIsNone(revision.resumen({"operacion": "entregar", "evidencia": "hecho"}))
        # Un rechazo también lleva texto, pero no es una entrega.
        self.assertIsNone(revision.resumen({"operacion": "rechazar", "motivo": "no",
                                            "git": {"rama": "x"}}))

    def test_todas_las_pruebas_en_verde(self):
        datos = revision.resumen(entrega(pruebas=(0, 0)))
        self.assertEqual(datos["pruebas"]["estado"], "verde")
        self.assertEqual(datos["pruebas"]["texto"], "2/2 en verde")

    def test_una_sola_en_rojo_pone_la_entrega_en_rojo(self):
        datos = revision.resumen(entrega(pruebas=(0, 1, 0)))
        self.assertEqual(datos["pruebas"]["estado"], "rojo")
        self.assertEqual(datos["pruebas"]["texto"], "1/3 en rojo")

    def test_una_prueba_que_no_termino_no_cuenta_como_verde(self):
        self.assertEqual(revision.estado_prueba(None), "sin-terminar")
        self.assertEqual(revision.resumen(entrega(pruebas=(None,)))["pruebas"]["estado"], "rojo")

    def test_sin_pruebas_no_dice_nada_de_pruebas(self):
        self.assertIsNone(revision.resumen(entrega())["pruebas"])

    def test_el_diff_resumido_y_sus_barras_proporcionales(self):
        archivos = [{"ruta": "a.py", "mas": 30, "menos": 10},
                    {"ruta": "b.py", "mas": 5, "menos": 5},
                    {"ruta": "logo.png", "mas": None, "menos": None}]
        diff = revision.resumen(entrega(archivos=archivos))["diff"]
        self.assertEqual(diff["texto"], "+35 −15 · 3 archivos")
        self.assertAlmostEqual(diff["proporcion_mas"], 35 / 50)
        por_ruta = {a["ruta"]: a for a in diff["archivos"]}
        # El que más cambió llena su barra; los demás se miden contra él.
        self.assertEqual(por_ruta["a.py"]["proporcion"], 1.0)
        self.assertEqual(por_ruta["b.py"]["proporcion"], 0.25)
        self.assertEqual(por_ruta["a.py"]["proporcion_mas"], 0.75)
        self.assertTrue(por_ruta["logo.png"]["binario"])
        self.assertEqual(por_ruta["logo.png"]["proporcion"], 0.0)

    def test_un_solo_archivo_y_un_solo_commit_en_singular(self):
        datos = revision.resumen(entrega(archivos=[{"ruta": "a", "mas": 1, "menos": 0}]))
        self.assertEqual(datos["diff"]["texto"], "+1 −0 · 1 archivo")
        self.assertEqual(datos["commits_texto"], "1 commit")
        self.assertEqual(revision.resumen(entrega(commits=3))["commits_texto"], "3 commits")

    def test_los_commits_con_su_hash_corto(self):
        datos = revision.resumen(entrega(commits=2))
        self.assertEqual(datos["commits"][1], {"hash": "0" * 39 + "1", "corto": "0000000",
                                               "asunto": "commit 1"})
        self.assertEqual(datos["rama"], "cotejo/cotejo-aaa111")

    def test_lo_que_dice_volver_a_comprobar(self):
        self.assertEqual(revision.texto_comprobacion(None), "")
        self.assertEqual(revision.texto_comprobacion({"corriendo": True}), "Comprobando…")
        self.assertEqual(revision.texto_comprobacion(
            {"sigue_igual": True, "pruebas": [{"ahora": 0}]}), "Sigue igual: todo en verde")
        self.assertEqual(revision.texto_comprobacion(
            {"sigue_igual": False, "pruebas": [{"ahora": 0}, {"ahora": 2}]}),
            "Cambió: 1 en rojo")
        self.assertIn("sin --prueba", revision.texto_comprobacion(
            revision.recomprobar({"operacion": "entregar"})))


DIFF = """diff --git a/a.txt b/a.txt
index 1111111..2222222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,3 @@
 uno
-dos
+DOS
+tres
diff --git a/nuevo con espacio.txt b/nuevo con espacio.txt
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/nuevo con espacio.txt
@@ -0,0 +1 @@
+hola
\\ No newline at end of file
diff --git a/borrado.txt b/borrado.txt
deleted file mode 100644
--- a/borrado.txt
+++ /dev/null
@@ -1 +0,0 @@
-adiós
diff --git a/viejo.txt b/movido.txt
similarity index 100%
rename from viejo.txt
rename to movido.txt
diff --git a/logo.png b/logo.png
index 4444444..5555555 100644
Binary files a/logo.png and b/logo.png differ
"""


class PartirElDiff(unittest.TestCase):
    def setUp(self):
        self.archivos = {a["ruta"]: a for a in revision.partir_diff(DIFF)}

    def test_un_archivo_por_cada_diff_git(self):
        self.assertEqual(set(self.archivos), {"a.txt", "nuevo con espacio.txt", "borrado.txt",
                                              "movido.txt", "logo.png"})

    def test_cada_linea_con_su_tipo_y_sin_el_signo(self):
        self.assertEqual(self.archivos["a.txt"]["lineas"], [
            ("hunk", "@@ -1,2 +1,3 @@"), ("contexto", "uno"), ("menos", "dos"),
            ("mas", "DOS"), ("mas", "tres")])

    def test_la_cabecera_no_se_cuela_como_lineas(self):
        # `--- a/…` y `+++ b/…` empiezan como una línea quitada y una añadida.
        for archivo in self.archivos.values():
            for _tipo, texto in archivo["lineas"]:
                self.assertFalse(texto.startswith(("-- a/", "++ b/", "++ /dev/null")))

    def test_nuevo_borrado_renombrado_y_binario(self):
        self.assertEqual(self.archivos["nuevo con espacio.txt"]["lineas"][1:], [("mas", "hola")])
        self.assertEqual(self.archivos["borrado.txt"]["lineas"][1:], [("menos", "adiós")])
        self.assertEqual(self.archivos["movido.txt"]["lineas"], [])
        self.assertTrue(self.archivos["logo.png"]["binario"])
        self.assertFalse(self.archivos["a.txt"]["binario"])

    def test_recortar_un_archivo_enorme(self):
        lineas = [("mas", str(i)) for i in range(1000)]
        pintadas, fuera = revision.recortar(lineas, 400)
        self.assertEqual((len(pintadas), fuera), (400, 600))
        self.assertEqual(revision.recortar(lineas[:3], 400), (lineas[:3], 0))


class RepoConRama:
    """Un repo con `main` y la rama de una tarea en su worktree, como lo deja `despachar`."""

    def __init__(self, tmp, tarea_id="cotejo-aaa111"):
        self.repo = Path(tmp) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("uno\ndos\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.tarea_id = tarea_id
        plan = worktrees.planear(tarea_id, self.repo)
        self.worktree = Path(worktrees.crear(tarea_id, plan)["ruta"])
        self.rama = plan["rama"]

    def trabajar(self, archivo="a.txt", texto="uno\nDOS\ntres\n", mensaje="cambia a"):
        (self.worktree / archivo).write_text(texto, encoding="utf-8")
        git(self.worktree, "add", "-A")
        git(self.worktree, "commit", "-q", "-m", mensaje)

    def entregar(self, pruebas=()):
        """La anotación que dejaría `cotejo entregar` desde el worktree."""
        return {"operacion": "entregar", "id": self.tarea_id, "evidencia": "hecho",
                **evidencia.reunir(self.worktree, pruebas)}


@unittest.skipUnless(HAY_GIT, "sin git")
class ConGit(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.tmp = Path(temporal.name)
        for parche in (mock.patch.object(worktrees, "BASE", self.tmp / "wt"),
                       mock.patch.object(worktrees, "REGISTRO", self.tmp / "registro"),
                       # Sin la config de git de quien corre las pruebas: ni su difftool ni
                       # su nombre deciden nada aquí.
                       mock.patch.dict(os.environ, {
                           "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"),
                           "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_AUTHOR_NAME": "Prueba", "GIT_AUTHOR_EMAIL": "p@p",
                           "GIT_COMMITTER_NAME": "Prueba", "GIT_COMMITTER_EMAIL": "p@p"})):
            parche.start()
            self.addCleanup(parche.stop)
        (self.tmp / "gitconfig").write_text("[commit]\n\tgpgsign = false\n", encoding="utf-8")
        self.r = RepoConRama(self.tmp)


class ElDiffDeVerdad(ConGit):
    def test_el_diff_de_la_entrega_entre_sus_dos_commits(self):
        self.r.trabajar()
        anotada = self.r.entregar()
        datos = revision.resumen(anotada)
        partes = revision.diff(revision.carpeta_git(self.r.tarea_id, anotada),
                               datos["desde"], datos["head"])
        self.assertEqual([p["ruta"] for p in partes], ["a.txt"])
        self.assertIn(("mas", "tres"), partes[0]["lineas"])
        self.assertIn(("menos", "dos"), partes[0]["lineas"])

    def test_lo_que_vino_despues_de_la_entrega_no_entra_en_su_diff(self):
        self.r.trabajar()
        anotada = self.r.entregar()
        self.r.trabajar("b.txt", "después\n", "después de entregar")
        datos = revision.resumen(anotada)
        partes = revision.diff(self.r.worktree, datos["desde"], datos["head"])
        self.assertEqual([p["ruta"] for p in partes], ["a.txt"])

    def test_sin_commits_anotados_no_hay_diff(self):
        self.assertIsNone(revision.diff(self.r.worktree, None, "HEAD"))
        self.assertIsNone(revision.diff(None, "a", "b"))

    def test_la_carpeta_es_el_worktree_y_si_no_esta_el_repo_anotado(self):
        anotada = self.r.entregar()
        self.assertEqual(revision.carpeta_git(self.r.tarea_id, anotada), str(self.r.worktree))
        self.assertEqual(revision.carpeta_git("otra-tarea", anotada), str(self.r.worktree))
        self.assertIsNone(revision.carpeta_git("otra-tarea", {"git": {"repo": "/no/existe"}}))


class VolverAComprobar(ConGit):
    def test_vuelve_a_correr_en_el_worktree_y_dice_si_cambio(self):
        bandera = self.r.worktree / "rompe"
        prueba = py("import os,sys; sys.exit(1 if os.path.exists('rompe') else 0)")
        anotada = self.r.entregar([prueba])
        self.assertEqual(anotada["pruebas"][0]["codigo"], 0)
        resultado = revision.recomprobar(anotada, str(self.r.worktree))
        self.assertTrue(resultado["sigue_igual"])
        bandera.write_text("x", encoding="utf-8")
        resultado = revision.recomprobar(anotada, str(self.r.worktree))
        self.assertFalse(resultado["sigue_igual"])
        self.assertEqual((resultado["pruebas"][0]["antes"], resultado["pruebas"][0]["ahora"]),
                         (0, 1))
        self.assertEqual(revision.texto_comprobacion(resultado), "Cambió: 1 en rojo")

    def test_una_tarea_que_nunca_se_entrego(self):
        resultado = revision.recomprobar(None)
        self.assertIsNone(resultado["sigue_igual"])
        self.assertIn("nunca se entregó", resultado["salida"])


class AbrirEnHerramienta(ConGit):
    def test_el_argv_es_un_difftool_de_carpeta_sin_preguntas(self):
        self.assertEqual(revision.argv_difftool("/r", "a", "b"),
                         ["git", "-C", "/r", "difftool", "--dir-diff", "--no-prompt", "a", "b"])

    def test_sin_herramienta_en_git_lo_dice_y_no_lanza_nada(self):
        with mock.patch.object(revision, "_lanzar") as lanzar:
            resultado = revision.abrir_en_herramienta(str(self.r.worktree), "a", "b")
        self.assertFalse(resultado["abierto"])
        self.assertIn("diff.tool", resultado["motivo"])
        lanzar.assert_not_called()

    def test_con_la_herramienta_de_la_persona_lanza_difftool_sin_esperar(self):
        git(self.r.repo, "config", "diff.tool", "meld")
        self.assertEqual(revision.herramienta(self.r.worktree), "meld")
        with mock.patch.object(revision, "_lanzar") as lanzar:
            resultado = revision.abrir_en_herramienta(str(self.r.worktree), "a", "b")
        self.assertEqual(resultado, {"abierto": True, "herramienta": "meld"})
        argv = lanzar.call_args.args[0]
        self.assertEqual(argv, revision.argv_difftool(str(self.r.worktree), "a", "b"))


class AprobarOfreceIntegrar(ConGit):
    """Lo que hace Aprobar: calcular si se puede ofrecer integrar, y solo integrar si se confirma."""

    def test_con_trabajo_en_su_rama_se_ofrece_integrar_en_la_rama_del_repo(self):
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertTrue(plan["ofrecer"], plan)
        self.assertEqual((plan["rama"], plan["destino"], plan["repo"]),
                         (self.r.rama, "main", str(self.r.repo)))
        self.assertNotIn("aviso", plan)

    def test_calcular_el_plan_no_toca_el_repo(self):
        self.r.trabajar()
        antes = git(self.r.repo, "rev-parse", "main")
        revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertEqual(git(self.r.repo, "rev-parse", "main"), antes)

    def test_integrar_hace_un_merge_y_no_borra_la_rama(self):
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        resultado = revision.integrar(plan)
        self.assertTrue(resultado["integrada"], resultado)
        self.assertEqual((self.r.repo / "a.txt").read_text(encoding="utf-8"), "uno\nDOS\ntres\n")
        self.assertIn(self.r.rama, git(self.r.repo, "branch", "--format=%(refname:short)"))
        # --no-ff: queda un commit de merge con dos padres.
        self.assertEqual(len(git(self.r.repo, "rev-list", "--parents", "-1", "HEAD").split()), 3)
        # Y ya no se vuelve a ofrecer.
        otra = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(otra["ofrecer"])
        self.assertIn("ya está integrada", otra["motivo"])

    def test_integrar_sin_nombre_ni_correo_en_git_usa_los_de_cotejo(self):
        # Quien no programa no tiene identidad de git: el merge no puede morir por eso.
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        sin_identidad = {clave: "" for clave in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                                                  "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}
        with mock.patch.dict(os.environ, {"EMAIL": ""}):
            for clave in (*sin_identidad, "EMAIL"):
                os.environ.pop(clave, None)
            resultado = revision.integrar(plan)
        self.assertTrue(resultado["integrada"], resultado)
        self.assertEqual(git(self.r.repo, "log", "-1", "--format=%cn <%ce>"),
                         "Cotejo <cotejo@localhost>")
        self.assertEqual(subprocess.run(["git", "-C", str(self.r.repo), "config", "--local",
                                         "user.email"], capture_output=True).returncode, 1)

    def test_se_ofrece_aunque_el_worktree_ya_se_haya_retirado(self):
        # El board aprueba (y retira el worktree) antes de que la persona conteste; el plan se
        # calculó antes, y con él basta para integrar.
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertTrue(worktrees.retirar(self.r.tarea_id)["retirado"])
        self.assertTrue(revision.integrar(plan)["integrada"])

    def test_sin_trabajo_en_la_rama_no_hay_nada_que_integrar(self):
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(plan["ofrecer"])
        self.assertIn("ya está integrada", plan["motivo"])

    def test_con_el_repo_sucio_no_se_ofrece_y_se_dice_por_que(self):
        self.r.trabajar()
        (self.r.repo / "a.txt").write_text("a medias\n", encoding="utf-8")
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(plan["ofrecer"])
        self.assertIn("sin commitear", plan["motivo"])
        self.assertEqual(plan["repo"], str(self.r.repo))  # el board sí avisa: hay repo

    def test_una_tarea_sin_rama_ni_repo_no_ofrece_nada_ni_avisa(self):
        plan = revision.plan_integracion("cotejo-zzz999", {"operacion": "entregar"})
        self.assertFalse(plan["ofrecer"])
        self.assertNotIn("repo", plan)

    def test_si_la_rama_avanzo_despues_de_la_entrega_se_avisa(self):
        self.r.trabajar()
        anotada = self.r.entregar()
        self.r.trabajar("b.txt", "después\n", "después")
        plan = revision.plan_integracion(self.r.tarea_id, anotada)
        self.assertTrue(plan["ofrecer"])
        self.assertIn("avanzó", plan["aviso"])

    def test_un_conflicto_se_aborta_y_el_repo_queda_como_estaba(self):
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        (self.r.repo / "a.txt").write_text("otra cosa\n", encoding="utf-8")
        git(self.r.repo, "commit", "-q", "-am", "choca")
        antes = git(self.r.repo, "rev-parse", "HEAD")
        resultado = revision.integrar(plan)
        self.assertFalse(resultado["integrada"])
        self.assertIn("lo dejé como estaba", resultado["motivo"])
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.r.repo, "status", "--porcelain"), "")

    def test_si_el_repo_cambio_de_rama_mientras_tanto_no_integra(self):
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        git(self.r.repo, "switch", "-q", "-c", "otra")
        resultado = revision.integrar(plan)
        self.assertFalse(resultado["integrada"])
        self.assertIn("ya no está en main", resultado["motivo"])

    def test_integrar_un_plan_que_no_se_ofrecio_no_hace_nada(self):
        self.assertFalse(revision.integrar({"ofrecer": False, "motivo": "x"})["integrada"])
        self.assertFalse(revision.integrar(None)["integrada"])


class SinVerbosNuevos(unittest.TestCase):
    def test_la_cli_no_gana_verbos_para_finalizar_ni_integrar(self):
        from tareas import cli
        verbos = set()
        for accion in cli.analizador()._subparsers._group_actions:
            verbos |= set(accion.choices)
        for prohibido in ("aprobar", "integrar", "finalizar", "merge", "revision", "revisar-diff"):
            self.assertNotIn(prohibido, verbos)


# --- los widgets, con un Board falso ---------------------------------------------------------

try:
    from gi.repository import Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def hijos(widget):
    hijo = widget.get_first_child()
    while hijo is not None:
        yield hijo
        yield from hijos(hijo)
        hijo = hijo.get_next_sibling()


def board_falso(anotacion):
    falso = types.SimpleNamespace(app=types.SimpleNamespace(bitacora={"cotejo-aaa111": anotacion}),
                                  comprobaciones={}, movidas=[], revisadas=[], comprobadas=[],
                                  integrando=set())
    for nombre in ("entrega_de", "revision_en_carta", "tooltip_aprobar"):
        setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
    falso.con_icono = app.Board.con_icono
    falso.barra_diff = app.Board.barra_diff
    falso.mover = lambda proyecto, tarea, destino: falso.movidas.append(destino)
    falso.ver_revision = lambda proyecto, tarea: falso.revisadas.append(tarea.id)
    falso.volver_a_comprobar = lambda tarea: falso.comprobadas.append(tarea.id)
    return falso


def tarea_por_validar():
    return modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="01-Proyectos/Uno.md",
                        estado="por-validar", agente="opus")


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class LaCartaDeVerdad(unittest.TestCase):
    def botones(self, caja):
        return {next(h.get_label() for h in hijos(b) if isinstance(h, Gtk.Label)): b
                for b in hijos(caja) if isinstance(b, Gtk.Button)}

    def textos(self, caja):
        return [h.get_label() for h in hijos(caja) if isinstance(h, Gtk.Label)]

    def test_enseña_pruebas_diff_y_commits_y_los_tres_botones(self):
        anotacion = entrega(pruebas=(0, 1), archivos=[{"ruta": "a", "mas": 3, "menos": 1}],
                            commits=2)
        falso = board_falso(anotacion)
        caja = falso.revision_en_carta(None, tarea_por_validar())
        textos = self.textos(caja)
        self.assertIn("1/2 en rojo", textos)
        self.assertIn("+3 −1 · 1 archivo", textos)
        self.assertIn("2 commits", textos)
        self.assertEqual(set(self.botones(caja)), {"Comprobar", "Revisar", "Aprobar"})

    def test_aprobar_mueve_a_hecha_y_los_otros_no_mueven_nada(self):
        falso = board_falso(entrega(pruebas=(0,)))
        botones = self.botones(falso.revision_en_carta(None, tarea_por_validar()))
        botones["Comprobar"].emit("clicked")
        botones["Revisar"].emit("clicked")
        self.assertEqual(falso.movidas, [])
        self.assertEqual((falso.comprobadas, falso.revisadas), (["cotejo-aaa111"],) * 2)
        botones["Aprobar"].emit("clicked")
        self.assertEqual(falso.movidas, [modelo.HECHA])

    def test_sin_evidencia_estructurada_no_hay_revisar_pero_si_aprobar(self):
        falso = board_falso({"operacion": "entregar", "evidencia": "hecho"})
        botones = self.botones(falso.revision_en_carta(None, tarea_por_validar()))
        self.assertEqual(set(botones), {"Comprobar", "Aprobar"})

    def test_mientras_comprueba_el_boton_se_apaga_y_lo_dice(self):
        falso = board_falso(entrega(pruebas=(0,)))
        falso.comprobaciones["cotejo-aaa111"] = {"corriendo": True}
        caja = falso.revision_en_carta(None, tarea_por_validar())
        self.assertFalse(self.botones(caja)["Comprobar"].get_sensitive())
        self.assertIn("Comprobando…", self.textos(caja))

    def test_las_lineas_del_diff_llevan_su_clase_y_se_recortan(self):
        parte = {"ruta": "a", "binario": False,
                 "lineas": [("hunk", "@@"), ("mas", "x"), ("menos", "y"), ("contexto", "z")]
                 + [("mas", str(i)) for i in range(revision.LINEAS_MAX)]}
        caja = app.Board.lineas_del_diff(parte)
        filas = [h for h in hijos(caja) if "diff-linea" in h.get_css_classes()]
        self.assertEqual([f.get_css_classes()[-1] for f in filas[:4]],
                         ["hunk", "mas", "menos", "contexto"])
        self.assertIn(f"… {4} líneas más: ábrelo en la herramienta", self.textos(caja))


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class AprobarEnElBoard(unittest.TestCase):
    """Aprobar finaliza y **ofrece** integrar: sin el «sí» de la persona no se integra nada."""

    def falso(self):
        falso = types.SimpleNamespace(avisos=[], ofrecidos=[])
        falso.aviso = falso.avisos.append
        return falso

    def test_contestar_ahora_no_no_integra(self):
        falso = self.falso()
        with mock.patch.object(revision, "integrar") as integrar:
            app.Board.al_responder_integrar(falso, None, "ahora-no", {"rama": "r", "destino": "m"})
        integrar.assert_not_called()

    def test_contestar_integrar_integra_y_lo_dice(self):
        falso = self.falso()
        plan = {"rama": "cotejo/x", "destino": "main"}
        with mock.patch.object(revision, "integrar", return_value={"integrada": True}) as integrar:
            app.Board.al_responder_integrar(falso, None, "integrar", plan)
        integrar.assert_called_once_with(plan)
        self.assertEqual(falso.avisos, ["cotejo/x integrada en main"])

    def test_si_no_se_puede_ofrecer_se_avisa_solo_cuando_hay_repo(self):
        falso = self.falso()
        app.Board.ofrecer_integrar(falso, None, {"ofrecer": False, "motivo": "sin rama"})
        self.assertEqual(falso.avisos, [])
        app.Board.ofrecer_integrar(falso, None, {"ofrecer": False, "repo": "/r",
                                                 "motivo": "/r tiene cambios sin commitear"})
        self.assertEqual(len(falso.avisos), 1)
        self.assertIn("sin commitear", falso.avisos[0])

    def test_aprobar_calcula_el_plan_antes_y_ofrece_despues_sin_integrar(self):
        orden = []
        tarea = tarea_por_validar()
        falso = types.SimpleNamespace(
            fuente=types.SimpleNamespace(marcar=lambda t, hecha: orden.append("marcar") or t),
            finalizadas=types.SimpleNamespace(anotar=lambda t: None),
            retirar_worktree=lambda t, d: orden.append("retirar"),
            app=types.SimpleNamespace(refrescar=lambda: orden.append("refrescar")),
            comprobaciones={"cotejo-aaa111": {"corriendo": False}},
            ofrecer_integrar=lambda t, plan: orden.append(("ofrecer", plan["ofrecer"])),
            aviso=lambda texto: None)
        plan = {"ofrecer": True, "rama": "cotejo/x", "destino": "main", "repo": "/r"}
        with mock.patch.object(revision, "plan_integracion",
                               side_effect=lambda *a: orden.append("plan") or plan), \
                mock.patch.object(revision, "integrar") as integrar, \
                mock.patch.object(app.vista_revision.bitacora, "anotar"), \
                mock.patch.object(app.vista_revision.bitacora, "ultima_entrega", return_value={}):
            app.Board.escribir_movimiento(falso, None, tarea, modelo.HECHA)
        self.assertEqual(orden, ["plan", "marcar", "retirar", "refrescar", ("ofrecer", True)])
        integrar.assert_not_called()
        self.assertNotIn("cotejo-aaa111", falso.comprobaciones)

    def test_mover_a_otra_columna_no_ofrece_integrar(self):
        tarea = modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="x", estado="en-curso")
        ofrecidos = []
        falso = types.SimpleNamespace(
            fuente=types.SimpleNamespace(poner_estado=lambda t, d: t),
            finalizadas=None, retirar_worktree=lambda t, d: None,
            app=types.SimpleNamespace(refrescar=lambda: None), comprobaciones={},
            ofrecer_integrar=lambda t, plan: ofrecidos.append(plan))
        with mock.patch.object(revision, "plan_integracion") as plan, \
                mock.patch.object(app.vista_revision.bitacora, "anotar"):
            app.Board.escribir_movimiento(falso, None, tarea, "por-validar")
        plan.assert_not_called()
        self.assertEqual(ofrecidos, [])


if __name__ == "__main__":
    unittest.main()
