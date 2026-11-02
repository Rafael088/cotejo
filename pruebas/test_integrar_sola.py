"""Aprobar integra sola en los proyectos creados desde el Inicio (cotejo-00fwc2).

Un proyecto del Inicio lleva `origen: inicio` en `.cotejo/proyecto.md` (`tareas/origen.py`), y lo
pone `cotejo init` solo cuando corre con `COTEJO_ORIGEN=inicio`, que es lo que lleva el agente que
lo prepara. Ahí aprobar mete la rama en la principal sin preguntar y la borra; si choca o hay
cambios sin guardar, no deja nada a medias, lo dice sin nombrar ramas y ofrece un agente o
reintentar. Un proyecto sin marca sigue con `ofrecer_integrar`.

Todo contra repos de git temporales con HOME y config de git aislados: nada depende de lo que
tenga instalado o configurado la máquina. Las del board usan un Board falso y necesitan GTK.
"""

import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI
from test_revision import HAY_GIT, RepoConRama, git
from tareas import almacen, inicio, juntar, modelo, origen, revision, worktrees

DEL_INICIO = {origen.VARIABLE: origen.INICIO}


class LaMarca(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)

    def test_sin_proyecto_md_no_es_del_inicio(self):
        self.assertFalse(origen.es_del_inicio(self.raiz))

    def test_solo_se_marca_con_la_variable_del_inicio(self):
        almacen.Almacen(self.raiz).crear("proyecto", "Mi app")
        self.assertFalse(origen.marcar_si_viene_del_inicio(self.raiz, {}))
        self.assertFalse(origen.es_del_inicio(self.raiz))
        self.assertTrue(origen.marcar_si_viene_del_inicio(self.raiz, DEL_INICIO))
        self.assertTrue(origen.es_del_inicio(self.raiz))
        # Idempotente.
        self.assertFalse(origen.marcar_si_viene_del_inicio(self.raiz, DEL_INICIO))

    def test_no_pisa_otro_origen_puesto_a_mano(self):
        alm = almacen.Almacen(self.raiz)
        entrada = alm.crear("proyecto", "Mi app")
        alm.reescribir(almacen.ID_PROYECTO, entrada.version, campos={"origen": "a-mano"})
        self.assertFalse(origen.marcar_si_viene_del_inicio(self.raiz, DEL_INICIO))
        self.assertFalse(origen.es_del_inicio(self.raiz))

    def test_el_agente_del_inicio_corre_con_la_variable(self):
        self.assertEqual(inicio.ENTORNO.get(origen.VARIABLE), origen.INICIO)


@unittest.skipUnless(HAY_GIT, "sin git")
class InitMarca(PruebaDeCLI):
    def correr_init(self, destino, extra):
        home = self.vault / "home"
        home.mkdir(exist_ok=True)
        (home / "gitconfig").write_text("[commit]\n\tgpgsign = false\n", encoding="utf-8")
        entorno = {"HOME": str(home), "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
                   "GIT_CONFIG_NOSYSTEM": "1", **extra}
        with mock.patch.dict(os.environ, entorno):
            if origen.VARIABLE not in extra:
                os.environ.pop(origen.VARIABLE, None)
            return self.correr("init", "--repo", str(destino))

    def test_init_desde_el_inicio_deja_la_marca_en_el_commit_inicial(self):
        destino = self.vault / "mi-app"
        codigo, datos = self.correr_init(destino, DEL_INICIO)
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["del_inicio"])
        self.assertTrue(origen.es_del_inicio(destino))
        en_commit = subprocess.run(["git", "-C", str(destino), "show", "HEAD:.cotejo/proyecto.md"],
                                   capture_output=True, text=True).stdout
        self.assertIn("origen: inicio", en_commit)

    def test_init_de_quien_programa_no_marca_nada(self):
        destino = self.vault / "lo-mio"
        codigo, datos = self.correr_init(destino, {})
        self.assertEqual(codigo, 0, datos)
        self.assertFalse(datos["del_inicio"])
        self.assertFalse(origen.es_del_inicio(destino))


@unittest.skipUnless(HAY_GIT, "sin git")
class ConRepo(unittest.TestCase):
    """Un repo con la rama de una tarea; `del_inicio` lo marca como creado desde el Inicio."""

    del_inicio = True

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.tmp = Path(temporal.name)
        (self.tmp / "home").mkdir()
        (self.tmp / "gitconfig").write_text("[commit]\n\tgpgsign = false\n", encoding="utf-8")
        for parche in (mock.patch.object(worktrees, "BASE", self.tmp / "wt"),
                       mock.patch.object(worktrees, "REGISTRO", self.tmp / "registro"),
                       mock.patch.dict(os.environ, {
                           "HOME": str(self.tmp / "home"),
                           "GIT_CONFIG_GLOBAL": str(self.tmp / "gitconfig"),
                           "GIT_CONFIG_NOSYSTEM": "1",
                           "GIT_AUTHOR_NAME": "Prueba", "GIT_AUTHOR_EMAIL": "p@p",
                           "GIT_COMMITTER_NAME": "Prueba", "GIT_COMMITTER_EMAIL": "p@p"})):
            parche.start()
            self.addCleanup(parche.stop)
        self.r = RepoConRama(self.tmp)
        almacen.Almacen(self.r.repo).crear("proyecto", "Mi app")
        if self.del_inicio:
            origen.marcar_si_viene_del_inicio(self.r.repo, DEL_INICIO)
        (self.r.repo / ".cotejo" / "tareas.md").write_text("# Tareas\n", encoding="utf-8")
        git(self.r.repo, "add", ".cotejo")
        git(self.r.repo, "commit", "-q", "-m", "cotejo")
        # Como de verdad: `.cotejo/` está cambiado en el árbol principal (mover una tarea
        # reescribe `tareas.md`) y eso no puede impedir integrar.
        (self.r.repo / ".cotejo" / "tareas.md").write_text("# Tareas\n- [x] hecha\n",
                                                           encoding="utf-8")

    def aprobar(self):
        """Lo que hace el board al aprobar: el plan antes, retirar el worktree, integrar."""
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        worktrees.retirar(self.r.tarea_id)
        return plan, revision.integrar_sola(plan)

    def ramas(self):
        return git(self.r.repo, "branch", "--format=%(refname:short)").split()


class IntegraSola(ConRepo):
    def test_limpio_integra_borra_rama_y_worktree_y_lo_dice_sin_ramas(self):
        self.r.trabajar()
        plan, resultado = self.aprobar()
        self.assertTrue(plan["del_inicio"])
        self.assertTrue(resultado["integrada"], resultado)
        self.assertTrue(resultado["rama_borrada"])
        self.assertEqual((self.r.repo / "a.txt").read_text(encoding="utf-8"), "uno\nDOS\ntres\n")
        self.assertNotIn(self.r.rama, self.ramas())
        self.assertFalse(self.r.worktree.exists())
        # Un merge de verdad, sin reescribir: dos padres.
        self.assertEqual(len(git(self.r.repo, "rev-list", "--parents", "-1", "HEAD").split()), 3)
        aviso = revision.aviso_inicio(resultado)
        self.assertEqual(aviso, {"texto": "Aprobada. Ya está en tu app.", "agente": False,
                                 "reintentar": False})
        self.assertNotIn("cotejo/", aviso["texto"])

    def test_conflicto_aborta_avisa_en_llano_y_ofrece_agente(self):
        self.r.trabajar()
        (self.r.repo / "a.txt").write_text("otra cosa\n", encoding="utf-8")
        git(self.r.repo, "commit", "-q", "-am", "choca")
        antes = git(self.r.repo, "rev-parse", "HEAD")
        plan, resultado = self.aprobar()
        self.assertFalse(resultado["integrada"])
        self.assertEqual(resultado["causa"], "conflicto")
        self.assertEqual(resultado["archivos"], ["a.txt"])
        # Nada a medias: mismo HEAD, sin merge en marcha, sin cambios fuera de `.cotejo/`.
        self.assertEqual(git(self.r.repo, "rev-parse", "HEAD"), antes)
        self.assertEqual(git(self.r.repo, "status", "--porcelain", "--", ".",
                             ":(exclude).cotejo"), "")
        self.assertIn(self.r.rama, self.ramas())  # se queda para el agente que lo resuelva
        aviso = revision.aviso_inicio(resultado)
        self.assertTrue(aviso["agente"])
        self.assertIn("a.txt", aviso["texto"])
        self.assertIn("tu app sigue como estaba", aviso["texto"])
        self.assertNotIn(self.r.rama, aviso["texto"])
        tarea = revision.texto_tarea_conflicto("Cambia a", plan, resultado["archivos"])
        self.assertNotIn("\n", tarea)
        self.assertIn(f"git merge {self.r.rama}", tarea)

    def test_arbol_sucio_no_integra_y_ofrece_reintentar(self):
        self.r.trabajar()
        (self.r.repo / "a.txt").write_text("a medias\n", encoding="utf-8")
        plan, resultado = self.aprobar()
        self.assertFalse(resultado["integrada"])
        self.assertEqual(resultado["causa"], "sucio")
        self.assertEqual(resultado["sucios"], ["a.txt"])
        self.assertEqual((self.r.repo / "a.txt").read_text(encoding="utf-8"), "a medias\n")
        self.assertIn(self.r.rama, self.ramas())
        aviso = revision.aviso_inicio(resultado)
        self.assertEqual((aviso["agente"], aviso["reintentar"]), (False, True))
        self.assertIn("cambios sin guardar", aviso["texto"])
        # Guardados los cambios, reintentar con un plan nuevo integra.
        git(self.r.repo, "checkout", "--", "a.txt")
        nuevo = revision.plan_integracion(self.r.tarea_id, {"git": {"rama": plan["rama"],
                                                                    "repo": plan["repo"]}})
        self.assertTrue(revision.integrar_sola(nuevo)["integrada"])

    def test_cotejo_incompatible_se_guarda_y_ofrece_resolver_el_conflicto(self):
        (self.r.worktree / ".cotejo").mkdir(exist_ok=True)
        self.r.trabajar(".cotejo/tareas.md", "# Tareas\n- [ ] del agente\n", "toca cotejo")
        _plan, resultado = self.aprobar()
        self.assertFalse(resultado["integrada"])
        self.assertEqual(resultado["causa"], "conflicto")
        self.assertEqual(resultado["archivos"], [".cotejo/tareas.md"])
        self.assertEqual((self.r.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8"),
                         "# Tareas\n- [x] hecha\n")
        self.assertEqual(git(self.r.repo, "show", "HEAD:.cotejo/tareas.md"),
                         "# Tareas\n- [x] hecha")
        self.assertTrue(revision.aviso_inicio(resultado)["agente"])
        self.assertFalse(revision.aviso_inicio(resultado)["reintentar"])

    def test_ya_integrada_solo_borra_la_rama(self):
        _plan, resultado = self.aprobar()
        self.assertTrue(resultado["integrada"])
        self.assertTrue(resultado.get("ya_estaba"))
        self.assertNotIn(self.r.rama, self.ramas())


class SinMarcaSigueComoAntes(ConRepo):
    del_inicio = False

    def test_sin_marca_se_ofrece_y_cotejo_tampoco_cuenta_como_sucio(self):
        self.r.trabajar()
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(plan["del_inicio"])
        # `.cotejo/` cambiado no impide ofrecerla (decisión del dueño, también aquí)...
        self.assertTrue(plan["ofrecer"], plan)
        self.assertTrue(revision.integrar(plan)["integrada"])
        # ... y la rama no se borra: en los de quien programa, eso es suyo.
        self.assertIn(self.r.rama, self.ramas())

    def test_sin_marca_un_cambio_fuera_de_cotejo_sigue_impidiendo(self):
        self.r.trabajar()
        (self.r.repo / "a.txt").write_text("a medias\n", encoding="utf-8")
        plan = revision.plan_integracion(self.r.tarea_id, self.r.entregar())
        self.assertFalse(plan["ofrecer"])
        self.assertIn("sin commitear", plan["motivo"])


class LaTareaDeJuntar(ConRepo):
    """Tras un choque, la tarea de juntar lleva apuntada la rama original (`juntar.py`) y, al
    aprobarla e integrarla limpia, la original se borra con `branch -d`."""

    def setUp(self):
        super().setUp()
        parche = mock.patch.object(juntar, "CARPETA", self.tmp / "juntar")
        parche.start()
        self.addCleanup(parche.stop)

    def chocar(self):
        self.r.trabajar()
        (self.r.repo / "a.txt").write_text("otra cosa\n", encoding="utf-8")
        git(self.r.repo, "commit", "-q", "-am", "choca")
        plan, resultado = self.aprobar()
        self.assertEqual(resultado["causa"], "conflicto")
        return plan

    def tarea_de_juntar(self, plan, resolver=True):
        """La tarea que crearía «Que lo resuelva un agente», con su agente haciendo el trabajo."""
        juntar.anotar("cotejo-jjj111", plan["rama"], plan["repo"])
        self.assertEqual(juntar.de_tarea("cotejo-jjj111")["rama"], self.r.rama)
        otra = RepoConRama.__new__(RepoConRama)
        otra.repo, otra.tarea_id = self.r.repo, "cotejo-jjj111"
        wt = worktrees.planear("cotejo-jjj111", self.r.repo)
        otra.worktree = Path(worktrees.crear("cotejo-jjj111", wt)["ruta"])
        otra.rama = wt["rama"]
        if resolver:
            subprocess.run(["git", "-C", str(otra.worktree), "merge", "-q", self.r.rama],
                           capture_output=True)
            otra.trabajar("a.txt", "otra cosa\nDOS\n", "junta los dos")
        else:
            otra.trabajar("b.txt", "nada que ver\n", "no junta")
        plan_j = revision.plan_integracion("cotejo-jjj111", otra.entregar())
        worktrees.retirar("cotejo-jjj111")
        return revision.integrar_sola(plan_j, "cotejo-jjj111")

    def test_al_integrar_la_de_juntar_se_borra_tambien_la_original(self):
        resultado = self.tarea_de_juntar(self.chocar())
        self.assertTrue(resultado["integrada"], resultado)
        self.assertEqual(resultado["original"], {"rama": self.r.rama, "borrada": True})
        self.assertNotIn(self.r.rama, self.ramas())
        self.assertIsNone(juntar.de_tarea("cotejo-jjj111"))
        self.assertEqual(revision.aviso_inicio(resultado)["texto"], "Aprobada. Ya está en tu app.")

    def test_si_la_original_no_quedo_integrada_no_se_fuerza_y_se_dice(self):
        resultado = self.tarea_de_juntar(self.chocar(), resolver=False)
        self.assertTrue(resultado["integrada"], resultado)
        self.assertFalse(resultado["original"]["borrada"])
        self.assertIn(self.r.rama, self.ramas())
        texto = revision.aviso_inicio(resultado)["texto"]
        self.assertIn("no lo borré", texto)
        self.assertNotIn(self.r.rama, texto)

    def test_una_tarea_cualquiera_no_es_de_juntar(self):
        self.assertIsNone(juntar.borrar_original("cotejo-zzz999"))


# --- el board, con un Board falso -----------------------------------------------------------

try:
    from gi.repository import Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class AprobarEnElBoard(unittest.TestCase):
    def tarea(self, **extra):
        return modelo.Tarea("Cambia a", id="cotejo-aaa111", donde="x",
                            estado=extra.pop("estado", "por-validar"), **extra)

    def escribir(self, plan):
        llamadas = []
        falso = types.SimpleNamespace(
            fuente=types.SimpleNamespace(
                marcar=lambda t, hecha: t,
                poner_estado=lambda t, estado: modelo.Tarea(
                    t.texto, id=t.id, donde=t.donde, estado=estado)),
            finalizadas=types.SimpleNamespace(anotar=lambda t: None),
            retirar_worktree=lambda t, d: None,
            app=types.SimpleNamespace(refrescar=lambda: None), comprobaciones={},
            ofrecer_integrar=lambda t, p: llamadas.append("ofrecer"),
            integrar_sola=lambda pr, t, p: llamadas.append(("sola", t)),
            aviso=lambda *a, **k: None)
        with mock.patch.object(revision, "plan_integracion", return_value=plan), \
                mock.patch.object(app.vista_revision.bitacora, "anotar"), \
                mock.patch.object(app.vista_revision.bitacora, "ultima_entrega", return_value={}):
            app.Board.escribir_movimiento(falso, None, self.tarea(), modelo.HECHA)
        return llamadas

    def test_del_inicio_integra_sola_y_sin_marca_ofrece(self):
        llamadas = self.escribir({"del_inicio": True, "repo": "/r"})
        self.assertEqual(llamadas[0][0], "sola")
        self.assertEqual(llamadas[0][1].estado, modelo.POR_INTEGRAR)
        self.assertFalse(llamadas[0][1].hecha)
        self.assertEqual(self.escribir({"del_inicio": False, "repo": "/r"}), ["ofrecer"])

    def falso(self, en_fondo=None):
        """Un Board falso con el ejecutor inyectado: por defecto corre todo seguido, sin hilos
        ni tiempo real; `en_fondo` deja guardar el trabajo para terminarlo cuando se quiera."""
        falso = types.SimpleNamespace(avisos=[], choques=[], integrando=set(), pintadas=0)
        falso.aviso = lambda texto, **k: falso.avisos.append((texto, k.get("boton", "")))
        falso.ofrecer_agente_para_choque = lambda *a: falso.choques.append(a)
        falso.pintar = lambda: setattr(falso, "pintadas", falso.pintadas + 1)
        falso.fuente = types.SimpleNamespace(marcar=lambda t, hecha: modelo.Tarea(
            t.texto, id=t.id, donde=t.donde, estado=t.estado, hecha=hecha))
        falso.finalizadas = types.SimpleNamespace(anotar=lambda t: None)
        falso.app = types.SimpleNamespace(refrescar=lambda: None)
        falso.foco_tras_pintar = None
        falso.en_fondo = en_fondo or (lambda trabajo, al_terminar: al_terminar(trabajo()))
        falso.al_integrar_sola = lambda *a: app.Board.al_integrar_sola(falso, *a)
        return falso

    def test_mientras_integra_dice_integrando_y_no_se_repite(self):
        pendientes = []
        falso = self.falso(en_fondo=lambda trabajo, al_terminar: pendientes.append(
            (trabajo, al_terminar)))
        with mock.patch.object(revision, "integrar_sola",
                               return_value={"integrada": True}) as sola:
            app.Board.integrar_sola(falso, None, self.tarea(), {"repo": "/r"})
            self.assertEqual(falso.integrando, {"cotejo-aaa111"})
            # Aprobar o integrar otra vez la misma tarea mientras tanto no hace nada.
            app.Board.integrar_sola(falso, None, self.tarea(), {"repo": "/r"})
            self.assertEqual(len(pendientes), 1)
            self.assertEqual(app.Board.escribir_movimiento(falso, None, self.tarea(),
                                                           modelo.HECHA), False)
            self.assertEqual(falso.avisos, [("Todavía la estoy metiendo en tu app", "")])
            trabajo, al_terminar = pendientes.pop()
            with mock.patch.object(app.vista_revision.bitacora, "anotar"):
                al_terminar(trabajo())
        sola.assert_called_once_with({"repo": "/r"}, "cotejo-aaa111")
        self.assertEqual(falso.integrando, set())
        self.assertEqual(falso.avisos[-1], ("Aprobada. Ya está en tu app.", ""))

    def test_limpio_lo_dice_y_nada_mas(self):
        falso = self.falso()
        with mock.patch.object(revision, "integrar_sola", return_value={"integrada": True}), \
                mock.patch.object(app.vista_revision.bitacora, "anotar") as anotar:
            app.Board.integrar_sola(falso, None, self.tarea(), {"repo": "/r"})
        self.assertEqual(falso.avisos, [("Aprobada. Ya está en tu app.", "")])
        anotar.assert_called_once()

    def test_conflicto_ofrece_el_agente(self):
        falso = self.falso()
        with mock.patch.object(revision, "integrar_sola",
                               return_value={"integrada": False, "causa": "conflicto",
                                             "archivos": ["a.txt"]}):
            app.Board.integrar_sola(falso, None, self.tarea(), {"repo": "/r"})
        self.assertEqual(len(falso.choques), 1)
        self.assertEqual(falso.avisos, [])

    def test_sucio_avisa_con_reintentar(self):
        falso = self.falso()
        with mock.patch.object(revision, "integrar_sola",
                               return_value={"integrada": False, "causa": "sucio",
                                             "sucios": ["a.txt"]}):
            app.Board.integrar_sola(falso, None, self.tarea(), {"repo": "/r"})
        self.assertEqual(falso.avisos[0][1], "Reintentar")

    def test_si_no_entra_no_cierra_la_tarea(self):
        falso = self.falso()
        falso.fuente.marcar = mock.Mock()
        with mock.patch.object(revision, "integrar_sola",
                               return_value={"integrada": False, "causa": "sucio",
                                             "sucios": ["a.txt"]}):
            app.Board.integrar_sola(falso, None,
                                    self.tarea(estado=modelo.POR_INTEGRAR), {"repo": "/r"})
        falso.fuente.marcar.assert_not_called()

    def test_sin_repo_no_dice_nada(self):
        falso = self.falso()
        with mock.patch.object(revision, "integrar_sola") as sola:
            app.Board.integrar_sola(falso, None, self.tarea(), {"ofrecer": False})
        sola.assert_not_called()
        self.assertEqual(falso.avisos, [])

    def test_que_lo_resuelva_un_agente_crea_asigna_y_mueve_a_haciendo(self):
        creadas, movidas = [], []

        def crear(proyecto, texto):
            creadas.append(texto)
            return modelo.Tarea(texto, id="cotejo-nnn111", donde="x", estado="pendiente")

        falso = types.SimpleNamespace(
            fuente=types.SimpleNamespace(
                crear=crear, poner_agente=lambda t, a: modelo.Tarea(
                    t.texto, id=t.id, donde="x", estado="pendiente", agente=a)),
            alias_persona=("persona",), aviso=lambda *a, **k: None,
            app=types.SimpleNamespace(refrescar=lambda: None),
            mover=lambda p, t, d: movidas.append((t.agente, d)))
        proyecto = types.SimpleNamespace(tareas=[])
        plan = {"rama": "cotejo/cotejo-aaa111", "destino": "main", "repo": "/r"}
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        with mock.patch.object(app.vista_revision.bitacora, "anotar"), \
                mock.patch.object(juntar, "CARPETA", Path(temporal.name)):
            app.Board.resolver_con_agente(falso, proyecto, self.tarea(agente="opus"), plan,
                                          ["a.txt"])
            # La rama va en el registro, no solo en el texto.
            self.assertEqual(juntar.de_tarea("cotejo-nnn111"),
                             {"rama": "cotejo/cotejo-aaa111", "repo": "/r"})
        self.assertEqual(len(creadas), 1)
        self.assertIn("git merge cotejo/cotejo-aaa111", creadas[0])
        self.assertEqual(movidas, [("opus", "en-curso")])

    def test_el_tooltip_de_aprobar_segun_el_proyecto(self):
        falso = types.SimpleNamespace(entrega_de=lambda t: {})
        with mock.patch.object(revision, "es_del_inicio", return_value=True):
            self.assertEqual(app.Board.tooltip_aprobar(falso, self.tarea()),
                             "La das por buena y la mete en tu app")
        with mock.patch.object(revision, "es_del_inicio", return_value=False):
            self.assertEqual(app.Board.tooltip_aprobar(falso, self.tarea()),
                             "La das por buena; si tiene rama, te ofrece integrarla")


if __name__ == "__main__":
    unittest.main()
