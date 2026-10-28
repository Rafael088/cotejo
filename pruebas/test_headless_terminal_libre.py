"""`despachar --motor headless` con la terminal libre del board (cotejo-6a7np9, dec-kiik).

El motor headless usa el mismo armado que el agente del board (`enrutador/armado.py`): terminal
libre con los prohibidos de fábrica para los cuatro clientes, las guardas del PATH y, en Claude,
el sandbox. Nunca se lanza un cliente de verdad: `subprocess.Popen` va simulado y se mira el
argv, el entorno y la carpeta. Las guardas sí se ejercitan de verdad con un repo y un remoto
desnudo temporales.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import armado, clientes, config as cfg, despacho_board, guardas, motor, sandbox
from enrutador.motores import claude_cli
from tareas import preparacion

HAY_GIT = shutil.which("git") is not None


def git(carpeta, *args, entorno=None, check=True):
    return subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=Prueba",
                           "-c", "user.email=p@p", *args], capture_output=True, text=True,
                          check=check, env=entorno)


def config(encima=None):
    return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), encima or {})


class Entorno(unittest.TestCase):
    """Un repo con remoto desnudo y un worktree de tarea, con el estado de Cotejo temporal."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patch = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                             "COTEJO_CONFIG": str(self.tmp / "c" / "config.json")})
        patch.start()
        self.addCleanup(patch.stop)
        # Se calcula al importar: sin esto, las guardas se escribirían en el estado de verdad.
        parche = mock.patch.object(preparacion, "CARPETA", self.tmp / "estado" / "preparaciones")
        parche.start()
        self.addCleanup(parche.stop)
        self.remoto = self.tmp / "remoto.git"
        self.repo = self.tmp / "repo"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remoto))
        git(self.tmp, "init", "-q", "-b", "main", str(self.repo))
        (self.repo / "a.txt").write_text("a")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "inicial")
        git(self.repo, "remote", "add", "origin", str(self.remoto))
        git(self.repo, "push", "-q", "-u", "origin", "main")
        self.wt = self.tmp / "wt" / "t1"
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/t1", str(self.wt))
        self.worktree = {"repo": str(self.repo), "ruta": str(self.wt), "rama": "cotejo/t1"}

    def encargo(self, cliente="claude", worktree=True, **extra):
        return motor.Encargo(
            prompt="Haz la tarea", modelo="haiku", modelo_id="", directorio=self.wt,
            tarea_id="t1", proyecto="P", cliente=cliente, origen=self.repo,
            worktree=self.worktree if worktree else None, **extra)

    def motor(self, encima=None):
        instancia = claude_cli.ClaudeCLI({})
        instancia.config = config({"lanzar": {"sandbox": False}} if encima is None else encima)
        return instancia

    def argv_cliente(self, nombre):
        if nombre != "antigravity":
            return self.motor().argv(self.encargo(nombre))
        cotejo = mock.Mock()
        cotejo.carpeta_de_la_tarea.return_value = self.repo / ".cotejo"
        with mock.patch.object(sandbox, "disponible_bwrap", return_value=(True, "")), \
                mock.patch.object(claude_cli.f, "Cotejo", return_value=cotejo):
            return self.motor({"lanzar": {"sandbox": {}}}).argv(self.encargo(nombre))


@unittest.skipUnless(HAY_GIT, "sin git")
class ArgumentosDeLosCuatroClientes(Entorno):
    def test_cada_cliente_lleva_su_terminal_libre_y_el_prompt_al_final(self):
        for nombre in clientes.CLIENTES:
            with self.subTest(nombre):
                cliente = clientes.de(nombre)
                argv = self.argv_cliente(nombre)
                propios = cliente.terminal_libre(
                    armado.carpetas_de_escritura(self.wt, self.worktree), ["main"],
                    guardas.politica_gemini(), entorno={})[0]
                if nombre == "codex" and os.name != "nt":
                    # Codex lleva su perfil de permisos, no `--sandbox` (test_codex_perfil.py).
                    self.assertIn(f'default_permissions="{clientes.PERFIL_CODEX}"', argv)
                    self.assertNotIn("--sandbox", argv)
                elif propios:
                    self.assertIn(" ".join(propios), " ".join(argv))
                self.assertIn(armado.NOTA_TERMINAL, argv[-1])
                self.assertTrue(argv[-1].startswith("Haz la tarea"))

    def test_claude_niega_los_prohibidos_y_deja_el_resto_del_bash(self):
        argv = self.motor().argv(self.encargo("claude"))
        self.assertIn("acceptEdits", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Bash")
        negados = argv[argv.index("--disallowedTools") + 1:-2]
        for esperado in ("Bash(sudo *)", "Bash(git push *--force*)", "Bash(git push * main)"):
            self.assertIn(esperado, negados)

    def test_las_ramas_protegidas_incluyen_la_por_defecto_del_repo(self):
        git(self.repo, "remote", "set-head", "origin", "main")
        self.assertIn("main", armado.ramas_protegidas(self.repo, self.worktree))

    def test_es_el_mismo_armado_que_el_del_board(self):
        elegida = mock.Mock(nivel=mock.Mock(modelo="haiku", modelo_id="", argumentos=()))
        cliente = clientes.de("claude")
        carpetas = armado.carpetas_de_escritura(self.wt, self.worktree)
        delboard = despacho_board.comando(config(), cliente, elegida, "P", carpetas, ["main"])
        directo = armado.comando(config(), cliente, "haiku", "", "P", carpetas, ["main"])
        self.assertEqual(delboard, directo)

    def test_la_carpeta_del_worktree_y_el_git_del_repo_son_de_escritura(self):
        carpetas = armado.carpetas_de_escritura(self.wt, self.worktree)
        self.assertIn(str(self.wt), carpetas)
        self.assertIn(str(self.repo / ".git"), carpetas)

    def test_sin_carpeta_el_argv_queda_como_siempre(self):
        sin = motor.Encargo(prompt="P", modelo="haiku", cliente="claude")
        argv = self.motor().argv(sin)
        self.assertNotIn("--disallowedTools", argv)
        self.assertEqual(argv[-1], "P")

    def test_el_argv_de_ensayo_no_escribe_las_guardas(self):
        self.motor().argv(self.encargo("gemini"))
        self.assertFalse((guardas.carpeta() / "git").exists())


@unittest.skipUnless(HAY_GIT, "sin git")
class ConSandbox(Entorno):
    def argv(self, disponible, encima=None):
        cotejo = mock.Mock()
        cotejo.carpeta_de_la_tarea.return_value = self.repo / ".cotejo"
        # La nota cambia según haya Firefox en la máquina: se fija para no depender de ella.
        with mock.patch.object(sandbox, "disponible", return_value=disponible), \
                mock.patch.object(armado.navegador, "disponible_para_el_agente",
                                  return_value=True), \
                mock.patch.object(claude_cli.f, "Cotejo", return_value=cotejo):
            return self.motor(encima).argv(self.encargo("claude"))

    def test_claude_lleva_su_sandbox_y_la_nota_lo_dice(self):
        argv = self.argv((True, ""), {})
        self.assertIn("--settings", argv)
        self.assertIn(armado.NOTA_SANDBOX, argv[-1])

    def test_sin_sandbox_en_la_maquina_sigue_con_los_prohibidos(self):
        argv = self.argv((False, "falta bwrap"), {})
        self.assertNotIn("--settings", argv)
        self.assertIn("--disallowedTools", argv)
        self.assertNotIn(armado.NOTA_SANDBOX, argv[-1])

    def test_los_otros_clientes_no_llevan_el_de_claude(self):
        with mock.patch.object(sandbox, "disponible", return_value=(True, "")):
            for nombre in ("codex", "opencode", "gemini", "antigravity"):
                self.assertNotIn("--settings", self.argv_cliente(nombre))


@unittest.skipUnless(HAY_GIT and os.name != "nt", "sin git o en Windows")
class EjecutarConGuardas(Entorno):
    def lanzar(self, cliente="claude"):
        proceso = mock.Mock(pid=4242, returncode=0)
        proceso.communicate.return_value = ("", "")
        real = shutil.which
        falso = mock.Mock(PIPE=subprocess.PIPE, TimeoutExpired=subprocess.TimeoutExpired)
        falso.Popen.return_value = proceso
        popen = falso.Popen
        with mock.patch.object(claude_cli, "subprocess", falso), \
                mock.patch("shutil.which", side_effect=lambda p, **k: real(p, **k)
                           or "/usr/bin/" + p):
            resultado = self.motor().ejecutar(self.encargo(cliente))
        return resultado, popen

    def test_corre_en_el_worktree_con_las_guardas_primeras_en_el_path(self):
        resultado, popen = self.lanzar()
        self.assertTrue(resultado.ok)
        llamada = popen.call_args
        self.assertEqual(Path(llamada.kwargs["cwd"]), self.wt)
        entorno = llamada.kwargs["env"]
        self.assertEqual(entorno["PWD"], str(self.wt))
        self.assertEqual(entorno["COTEJO_GUARDAS"], str(guardas.carpeta()))
        partes = entorno["PATH"].split(os.pathsep)
        self.assertIn(str(guardas.carpeta()), partes[:2])   # tras el lanzador de `cotejo`
        self.assertEqual(entorno["COTEJO_RAMAS_PROTEGIDAS"].split(",")[0], "main")

    def test_opencode_recibe_su_permiso_por_entorno(self):
        _, popen = self.lanzar("opencode")
        permiso = json.loads(popen.call_args.kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        reglas = permiso["permission"]["bash"]
        self.assertEqual(reglas["*"], "allow")
        self.assertEqual(reglas["sudo *"], "deny")

    def test_las_guardas_rechazan_los_prohibidos_y_dejan_lo_demas(self):
        _, popen = self.lanzar()
        entorno = popen.call_args.kwargs["env"]
        def correr(*orden):
            return subprocess.run(orden, cwd=self.wt, env=entorno, capture_output=True, text=True)
        for orden in (("git", "push", "--force", "origin", "cotejo/t1"),
                      ("git", "push", "origin", "main"),
                      ("git", "push", "origin", "HEAD:main"),
                      ("sudo", "true")):
            with self.subTest(orden):
                hecho = correr(*orden)
                self.assertNotEqual(hecho.returncode, 0)
                self.assertIn("Cotejo", hecho.stderr)
        git(self.wt, "commit", "-q", "--allow-empty", "-m", "x")
        self.assertEqual(correr("git", "push", "origin", "cotejo/t1").returncode, 0)
        self.assertEqual(correr("git", "status").returncode, 0)


if __name__ == "__main__":
    unittest.main()
