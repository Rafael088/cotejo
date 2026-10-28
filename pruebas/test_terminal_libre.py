"""Terminal libre con prohibidos de fábrica para el agente que lanza el board (cotejo-7yfw1e,
dec-kiik): `clientes.Cliente.terminal_libre`, `clientes.prohibidos`, las guardas del PATH
(`enrutador/guardas.py`, `enrutador/guarda_git.py`) y cómo los usa `despacho_board`.

Nunca se lanza un agente de verdad. Las guardas sí se prueban de verdad: un repo con un remoto
desnudo en una carpeta temporal y el `git` de la guarda delante.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import (clientes, config as cfg, despacho_board, guardas, motor, preparar,
                       sandbox)
from enrutador.motores import agente

HAY_GIT = shutil.which("git") is not None
CARPETAS = ["/w/tarea", "/r/repo/.git", "/c/cotejo", "/e/estado"]

# Lo que el agente tiene que poder hacer (pruebas, builds, su rama) y lo que no.
PERMITIDOS = ["python3 -m unittest discover pruebas", "npm test", "make", "pytest -q",
              "git status", "git commit -m 'x'", "git push origin cotejo/cotejo-abc",
              "git push -u origin cotejo/cotejo-abc", "rm -rf build", "rm nuevo.txt",
              "rm -rf dist/ build/", "cotejo entregar cotejo-abc --evidencia 'x'",
              "git push origin cotejo/main-fix"]
PROHIBIDOS = ["sudo true", "sudo", "su", "su - root", "doas ls", "pkexec true",
              "git push --force origin cotejo/x", "git push origin cotejo/x --force",
              "git push --force-with-lease", "git push -f", "git push origin -f x",
              "git push origin +cotejo/x", "git push --mirror", "git push --all origin",
              "git push origin main", "git push -u origin main", "git push origin HEAD:main",
              "git push origin cotejo/x:main", "git push origin :main",
              "git push origin HEAD:refs/heads/main", "git push origin --delete main",
              "git push origin trunk",
              "rm -rf /home/alguien/fuera", "rm /etc/hosts", "rm -rf ../fuera", "rm ~/x",
              "rm -rf $HOME/x", "rmdir ../vacia", "unlink /tmp/x", "rm -rf a/../../b"]


def casa(patron, comando):
    """Cómo casan Claude Code y OpenCode un patrón de `prohibidos`: `*` es cualquier cosa."""
    return re.fullmatch(".*".join(re.escape(p) for p in patron.split("*")), comando) is not None


def git(carpeta, *args, entorno=None, check=True):
    return subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=Prueba",
                           "-c", "user.email=p@p", *args], capture_output=True, text=True,
                          check=check, env=entorno)


class Prohibidos(unittest.TestCase):
    def test_main_siempre_y_la_rama_por_defecto_sin_repetir(self):
        self.assertEqual(clientes.ramas_protegidas(), ["main"])
        self.assertEqual(clientes.ramas_protegidas("trunk"), ["main", "trunk"])
        self.assertEqual(clientes.ramas_protegidas(["main", "", None]), ["main"])

    def test_los_patrones_paran_lo_prohibido_y_dejan_las_pruebas(self):
        patrones = clientes.prohibidos("trunk")
        for comando in PROHIBIDOS:
            with self.subTest(comando):
                self.assertTrue(any(casa(p, comando) for p in patrones), comando)
        for comando in PERMITIDOS:
            with self.subTest(comando):
                self.assertFalse([p for p in patrones if casa(p, comando)], comando)

    def test_las_regex_de_gemini_dicen_lo_mismo_sobre_el_json_de_los_argumentos(self):
        reglas = [clientes._regex_gemini(p) for p in clientes.prohibidos("trunk")]
        for comando, prohibido in ([(c, True) for c in PROHIBIDOS] +
                                   [(c, False) for c in PERMITIDOS]):
            # Gemini prueba la regex justo detrás de `"command":"` en el JSON estable.
            json_args = json.dumps({"command": comando, "description": "main --force"})
            despues = json_args.split('"command": "', 1)[1]
            with self.subTest(comando):
                self.assertEqual(any(re.match(r, despues) for r in reglas), prohibido)
                for regla in reglas:   # nada que JavaScript con `u` no entienda
                    self.assertNotIn("\\ ", regla)


class TerminalLibre(unittest.TestCase):
    def test_claude_todo_el_bash_menos_los_prohibidos(self):
        argv, entorno = clientes.de("claude").terminal_libre(CARPETAS, "trunk")
        self.assertEqual(entorno, {})
        self.assertEqual(argv[:7], ["--permission-mode", "acceptEdits", "--allowedTools", "Bash",
                                    "--setting-sources", "user", "--disallowedTools"])
        negados = argv[7:]
        self.assertEqual(negados, [f"Bash({p})" for p in clientes.prohibidos("trunk")])
        for esperado in ("Bash(sudo *)", "Bash(su *)", "Bash(git push *--force*)",
                         "Bash(git push * main)", "Bash(git push *:main)",
                         "Bash(git push * trunk)", "Bash(rm * /*)", "Bash(rm *..*)"):
            self.assertIn(esperado, negados)
        self.assertNotIn("bypassPermissions", argv)

    def test_codex_su_sandbox_de_escritura_y_nada_mas(self):
        argv, entorno = clientes.de("codex").terminal_libre(CARPETAS, "trunk")
        # Lo de `permisos` y, detrás, el worktree como proyecto sin confianza (cotejo-j42qfc).
        self.assertEqual(argv, clientes.de("codex").permisos(CARPETAS)[0] +
                         clientes._codex_sin_confianza(CARPETAS[0]))
        self.assertEqual(argv[:2], ["--sandbox", "workspace-write"])
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        self.assertNotIn("danger-full-access", argv)
        self.assertEqual(entorno, {})

    def test_opencode_todo_permitido_y_los_prohibidos_al_final(self):
        previo = json.dumps({"model": "x/y", "permission": {
            "bash": {"*": "ask", "terraform *": "deny"}, "external_directory": "ask"}})
        argv, entorno = clientes.de("opencode").terminal_libre(
            CARPETAS, "trunk", entorno={"OPENCODE_CONFIG_CONTENT": previo})
        self.assertEqual(argv, [])
        datos = json.loads(entorno["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(datos["model"], "x/y")
        bash = list(datos["permission"]["bash"].items())
        self.assertEqual(bash[0], ("*", "allow"))
        self.assertEqual(bash[1], ("terraform *", "deny"))     # lo que negó la persona, sigue
        self.assertEqual([k for k, v in bash[2:]], clientes.prohibidos("trunk"))
        self.assertTrue(all(v == "deny" for _, v in bash[2:]))
        externo = datos["permission"]["external_directory"]
        self.assertEqual(externo["/w/tarea/*"], "allow")
        self.assertEqual(externo["*"], "ask")                  # fuera de sus carpetas, no

    def test_gemini_auto_edit_con_la_politica(self):
        argv, entorno = clientes.de("gemini").terminal_libre(CARPETAS, "trunk",
                                                             politica_gemini="/e/g.toml")
        self.assertEqual(argv, ["--approval-mode", "auto_edit", "--policy", "/e/g.toml"])
        self.assertEqual(entorno, {"GEMINI_CLI_TRUST_WORKSPACE": "true"})
        self.assertNotIn("yolo", argv)

    def test_la_politica_de_gemini_es_toml_y_niega_con_mas_prioridad(self):
        reglas = tomllib.loads(clientes.politica_gemini_toml("trunk"))["rule"]
        self.assertEqual(reglas[0], {"toolName": "run_shell_command", "decision": "allow",
                                     "priority": 100, "allowRedirection": True})
        negadas = reglas[1:]
        self.assertEqual(len(negadas), len(clientes.prohibidos("trunk")))
        for regla in negadas:
            self.assertEqual((regla["decision"], regla["priority"]), ("deny", 900))
            self.assertTrue(regla["denyMessage"])


class ComandoDelBoard(unittest.TestCase):
    def config(self, encima=None):
        return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), encima or {})

    def elegida(self, modelo="sonnet"):
        nivel = mock.Mock(modelo=modelo, modelo_id="", argumentos=())
        return mock.Mock(nivel=nivel)

    def test_cada_cliente_lleva_su_terminal_libre(self):
        hay_bwrap, _ = sandbox.disponible_bwrap()
        for nombre in clientes.CLIENTES:
            with self.subTest(nombre):
                cliente = clientes.de(nombre)
                propios = cliente.terminal_libre(CARPETAS, ["main", "trunk"], "/e/g.toml",
                                                 entorno={})[0]
                if nombre == "antigravity" and not hay_bwrap:
                    # Sin jaula no se lanza: su terminal libre va dentro de bubblewrap
                    # (cotejo-b1iwpj), no suelta con --dangerously-skip-permissions.
                    with self.assertRaises(sandbox.SandboxNoDisponible):
                        despacho_board.comando(self.config(), cliente, self.elegida(), "P",
                                               CARPETAS, ["main", "trunk"], "/e/g.toml")
                    continue
                ajustes = (sandbox.ajustes_claude(CARPETAS)
                           if nombre == "antigravity" else None)
                argv = despacho_board.comando(self.config(), cliente, self.elegida(), "P",
                                              CARPETAS, ["main", "trunk"], "/e/g.toml",
                                              sandbox=ajustes)
                if nombre == "antigravity":
                    self.assertEqual(Path(argv[0]).name, "bwrap")
                    argv = argv[argv.index("--") + 1:]
                if propios:
                    texto = " ".join(argv)
                    self.assertIn(" ".join(propios), texto)
                self.assertEqual(argv[-1], "P")
        claude = despacho_board.comando(self.config(), clientes.de("claude"), self.elegida(),
                                        "P", CARPETAS)
        self.assertIn("stream-json", claude)
        self.assertEqual(claude[-2:], ["--", "P"])   # `--disallowedTools` no se come el prompt
        # Ya no queda el permiso estrecho de antes (solo cotejo y git).
        self.assertNotIn("Bash(git:*)", claude)

    def test_una_config_propia_no_se_lleva_los_prohibidos(self):
        config = self.config({"lanzar": {"argumentos_extra": {"claude": ["--verbose"]}}})
        argv = despacho_board.comando(config, clientes.de("claude"), self.elegida(), "P",
                                      CARPETAS)
        self.assertIn("--disallowedTools", argv)
        self.assertIn("Bash(sudo *)", argv)


class LoDemasNoCambia(unittest.TestCase):
    """El agente de `cotejo despachar --motor agente` y el de preparar no comparten este armado:
    el primero no lanza nada (lo hace el agente con el que hablas, con sus permisos) y el
    segundo solo necesita `cotejo` para preparar un proyecto."""

    def test_el_motor_agente_no_lanza_nada_y_devuelve_el_encargo(self):
        encargo = motor.Encargo(prompt="Haz la tarea", modelo="sonnet", modelo_id="",
                                directorio=Path("."), tarea_id="cotejo-x", proyecto="P",
                                cliente="claude")
        with mock.patch("subprocess.Popen") as popen, mock.patch("subprocess.run") as run:
            resultado = agente.Agente({}).ejecutar(encargo)
        self.assertFalse(resultado.ejecutado)
        self.assertEqual(resultado.salida, "Haz la tarea")
        popen.assert_not_called()
        run.assert_not_called()

    def test_preparar_sigue_con_solo_cotejo(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})
        argv = preparar.comando(config, clientes.de("claude"), "", "P")
        self.assertEqual(argv, ["claude", "-p", "--allowedTools", "Bash(cotejo:*)", "--", "P"])


@unittest.skipUnless(HAY_GIT and os.name != "nt", "sin git o en Windows")
class GuardasDeVerdad(unittest.TestCase):
    """El `git` de la guarda contra un repo con remoto desnudo, como lo vería el agente."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        base = Path(temporal.name)
        self.remoto = base / "remoto.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "trunk", str(self.remoto)],
                       check=True)
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "trunk")
        (self.repo / "LEEME").write_text("hola\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "branch", "main")
        git(self.repo, "remote", "add", "origin", str(self.remoto))
        git(self.repo, "push", "-q", "origin", "trunk", "main")
        git(self.repo, "remote", "set-head", "origin", "trunk")
        self.wt = base / "wt"
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/cotejo-abc", str(self.wt))
        git(self.wt, "commit", "-q", "--allow-empty", "-m", "trabajo")
        self.guardas = base / "guardas"
        # Ramas protegidas por el board: solo main; trunk la descubre la guarda en origin/HEAD.
        self.entorno = {**os.environ, **guardas.entorno({}, ["main"], destino=self.guardas)}

    def correr(self, *args):
        return subprocess.run(["git", "-C", str(self.wt), "-c", "user.name=P",
                               "-c", "user.email=p@p", *args],
                              capture_output=True, text=True, env=self.entorno)

    def remoto_de(self, rama):
        return subprocess.run(["git", "-C", str(self.remoto), "rev-parse", "-q", "--verify",
                               rama], capture_output=True, text=True).stdout.strip()

    def test_el_git_del_agente_es_la_guarda(self):
        self.assertEqual(shutil.which("git", path=self.entorno["PATH"]),
                         str(self.guardas / "git"))
        self.assertTrue(Path(self.entorno["COTEJO_GIT_REAL"]).is_file())
        self.assertEqual(self.correr("status", "--short").returncode, 0)

    def test_su_rama_se_empuja_y_lo_prohibido_no(self):
        hecho = self.correr("push", "-q", "origin", "cotejo/cotejo-abc")
        self.assertEqual(hecho.returncode, 0, hecho.stderr)
        antes = {r: self.remoto_de(r) for r in ("trunk", "main")}
        git(self.wt, "commit", "-q", "--amend", "--allow-empty", "-m", "reescrito")
        for args in (["push", "--force", "origin", "cotejo/cotejo-abc"],
                     ["push", "-uf", "origin", "cotejo/cotejo-abc"],
                     ["push", "--force-with-lease"], ["push", "origin", "+cotejo/cotejo-abc"],
                     ["push", "--mirror", "origin"], ["push", "--all"],
                     ["push", "origin", "main"], ["push", "origin", "HEAD:main"],
                     ["push", "origin", "HEAD:refs/heads/trunk"], ["push", "origin", "trunk"],
                     ["push", "origin", "--delete", "main"], ["push", "origin", ":trunk"]):
            with self.subTest(args):
                hecho = self.correr(*args)
                self.assertEqual(hecho.returncode, 1, hecho.stderr)
                self.assertIn("prohibidos de fábrica", hecho.stderr)
        self.assertEqual({r: self.remoto_de(r) for r in ("trunk", "main")}, antes)

    def test_un_push_a_secas_hacia_main_se_rechaza(self):
        git(self.wt, "branch", "--set-upstream-to=origin/main")
        hecho = self.correr("-c", "push.default=upstream", "push")
        self.assertEqual(hecho.returncode, 1, hecho.stderr)
        self.assertIn("«main»", hecho.stderr)

    def test_sudo_y_su_se_niegan(self):
        for orden in ("sudo", "su", "doas", "pkexec"):
            with self.subTest(orden):
                hecho = subprocess.run([orden, "true"], capture_output=True, text=True,
                                       env=self.entorno)
                self.assertEqual(hecho.returncode, 126)
                self.assertIn("prohibido", hecho.stderr)

    def test_la_politica_de_gemini_queda_escrita(self):
        self.assertTrue(tomllib.loads((self.guardas / "gemini.toml").read_text())["rule"])


class GuardaSinRepo(unittest.TestCase):
    def test_lee_los_argumentos_como_git(self):
        from enrutador import guarda_git
        self.assertEqual(guarda_git.partir(["-C", "x", "-c", "a=b", "push", "-f"]),
                         (["-C", "x", "-c", "a=b"], "push", ["-f"]))
        self.assertEqual(guarda_git.leer_push(["-o", "ci.skip", "origin", "x"])[:2],
                         ("origin", ["x"]))
        self.assertTrue(guarda_git.leer_push(["-uf", "origin", "x"])[2])
        self.assertFalse(guarda_git.leer_push(["-u", "origin", "feat-fix"])[2])
        self.assertEqual(guarda_git.motivo(["status"], "git"), "")


@unittest.skipUnless(HAY_GIT, "sin git")
class LanzarConGuardas(unittest.TestCase):
    def test_el_board_lanza_con_las_guardas_en_el_path(self):
        from test_despacho_board import ConClienteFalso, esperar

        class Caso(ConClienteFalso):
            def runTest(self):
                terminado = []
                self.lanzar("cotejo-asig", al_terminar=terminado.append)
                self.assertTrue(esperar(lambda: terminado))
                lanzado = json.loads(self.argv_falso.read_text())
                # OpenCode trabaja donde dice PWD: tiene que ser el worktree, como el cwd.
                self.assertEqual(lanzado["pwd"], lanzado["cwd"])
                camino = lanzado["path"].split(os.pathsep)
                self.assertTrue(camino[0].endswith(os.path.join("agente", "bin")))
                self.assertTrue(camino[1].endswith(os.path.join("agente", "guardas")))
                argv = lanzado["argv"]
                self.assertIn("--disallowedTools", argv)
                self.assertIn("Bash(git push * main)", argv)
                self.assertEqual(argv[-2], "--")

        resultado = unittest.TestResult()
        Caso().run(resultado)
        self.assertEqual(resultado.errors + resultado.failures, [])


if __name__ == "__main__":
    unittest.main()
