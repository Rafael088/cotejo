"""El sandbox de Claude Code para el agente que lanza el board (cotejo-amui0f, dec-kiik):
`enrutador/sandbox.py`, cómo lo pide `clientes.Cliente.terminal_libre` y cómo lo arma
`despacho_board`.

Aquí no se lanza ningún Claude: se prueban los ajustes que se le pasan (`--settings`), lo que se
saca del repo de la tarea (remotos, worktrees, el `.git`) con repos de verdad en una carpeta
temporal, y qué pasa cuando el sandbox no está. Que el sandbox para de verdad un borrado fuera
del worktree se probó a mano con Claude (la evidencia de la tarea).
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

from enrutador import clientes, config as cfg, despacho_board, sandbox

HAY_GIT = shutil.which("git") is not None
CARPETAS = ["/w/tarea", "/r/repo/.git", "/c/cotejo", "/e/estado"]


def git(carpeta, *args):
    return subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=P", "-c", "user.email=p@p",
                           *args], capture_output=True, text=True, check=True)


def ajustes_de(argv):
    """La clave `sandbox` que lleva un argv de Claude en `--settings`, o None."""
    if "--settings" not in argv:
        return None
    return json.loads(argv[argv.index("--settings") + 1])["sandbox"]


class Ajustes(unittest.TestCase):
    def test_encerrado_sin_preguntar_y_sin_salida(self):
        caja = sandbox.ajustes_claude(["/w", "/w", "/e"], ["/r/.git/hooks"], ["github.com"])
        s = caja["sandbox"]
        self.assertTrue(s["enabled"])
        self.assertTrue(s["autoAllowBashIfSandboxed"])    # sin nadie que conteste
        self.assertFalse(s["allowUnsandboxedCommands"])   # dangerouslyDisableSandbox no vale
        self.assertFalse(s["failIfUnavailable"])          # nunca deja al agente sin Bash
        self.assertEqual(s["filesystem"]["allowWrite"], ["/w", "/e"])
        self.assertEqual(s["filesystem"]["denyWrite"], ["/r/.git/hooks"])
        self.assertEqual(s["network"]["allowedDomains"], ["github.com"])

    def test_claude_lo_pide_con_settings_y_los_prohibidos_siguen(self):
        caja = sandbox.ajustes_claude(CARPETAS)
        argv, _ = clientes.de("claude").terminal_libre(CARPETAS, ["main"], sandbox=caja)
        self.assertEqual(ajustes_de(argv), caja["sandbox"])
        self.assertIn("--disallowedTools", argv)
        self.assertIn("Bash(sudo *)", argv)
        # `--disallowedTools` va el último: lo que viene detrás es suyo hasta el `--`.
        self.assertLess(argv.index("--settings"), argv.index("--disallowedTools"))

    def test_sin_sandbox_claude_queda_como_antes(self):
        argv, _ = clientes.de("claude").terminal_libre(CARPETAS, ["main"])
        self.assertNotIn("--settings", argv)

    def test_los_demas_clientes_no_lo_llevan(self):
        caja = sandbox.ajustes_claude(CARPETAS)
        for nombre in ("codex", "opencode", "gemini"):
            with self.subTest(nombre):
                argv, _ = clientes.de(nombre).terminal_libre(CARPETAS, ["main"], "/g.toml",
                                                             entorno={}, sandbox=caja)
                self.assertNotIn("--settings", argv)

    def test_el_comando_del_board_lo_lleva_y_el_prompt_va_al_final(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})
        elegida = mock.Mock(nivel=mock.Mock(modelo="haiku", modelo_id="", argumentos=()))
        caja = sandbox.ajustes_claude(CARPETAS)
        argv = despacho_board.comando(config, clientes.de("claude"), elegida, "P", CARPETAS,
                                      ["main"], sandbox=caja)
        self.assertEqual(ajustes_de(argv), caja["sandbox"])
        self.assertEqual(argv[-2:], ["--", "P"])


class Remotos(unittest.TestCase):
    def test_lee_las_formas_de_un_remoto(self):
        casos = {
            "https://github.com/Rafael088/cotejo.git": ("red", "github.com", False),
            "http://Git.Ejemplo.org:8080/x.git": ("red", "git.ejemplo.org", False),
            "ssh://git@gitlab.com:22/a/b.git": ("red", "gitlab.com", True),
            "git@github.com:Rafael088/cotejo.git": ("red", "github.com", True),
            "file:///srv/git/x.git": ("carpeta", "/srv/git/x.git", False),
            "/srv/git/x.git": ("carpeta", "/srv/git/x.git", False),
        }
        for url, esperado in casos.items():
            with self.subTest(url):
                self.assertEqual(sandbox.leer_remoto(url), esperado)
        self.assertEqual(sandbox.leer_remoto("../x.git", "/r/repo"),
                         ("carpeta", os.path.abspath("/r/x.git"), False))
        self.assertIsNone(sandbox.leer_remoto(""))


@unittest.skipUnless(HAY_GIT, "sin git")
class DelLanzamiento(unittest.TestCase):
    """Lo que sale de un repo de verdad: un remoto desnudo local, otro en GitHub, otro por SSH,
    y dos worktrees de dos tareas."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        base = Path(temporal.name)
        self.remoto = base / "remoto.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remoto)], check=True)
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "base")
        git(self.repo, "remote", "add", "origin", str(self.remoto))
        self.mio = base / "wt" / "cotejo-mia"
        self.otro = base / "wt" / "cotejo-otra"
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/cotejo-mia", str(self.mio))
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/cotejo-otra", str(self.otro))
        self.escritura = [str(self.mio), str(self.repo / ".git"), "/c/cotejo", "/e/estado"]

    def armar(self, **kwargs):
        kwargs.setdefault("token", lambda entorno: "")
        return sandbox.del_lanzamiento(self.escritura, repo=self.repo, propio=self.mio,
                                       **kwargs)

    def test_escribe_en_lo_suyo_y_en_el_remoto_local(self):
        hecho = self.armar(carpeta_tarea="/r/repo/.cotejo")
        fs = hecho["ajustes"]["sandbox"]["filesystem"]
        for carpeta in [*self.escritura, "/r/repo/.cotejo", str(self.remoto)]:
            self.assertIn(carpeta, fs["allowWrite"])
        self.assertEqual(hecho["entorno"], {"COTEJO_SANDBOX": "1"})   # sin GitHub, sin token
        self.assertEqual(hecho["ajustes"]["sandbox"]["network"]["allowedDomains"], [])

    def test_no_escribe_en_los_hooks_el_config_ni_otros_worktrees(self):
        fs = self.armar()["ajustes"]["sandbox"]["filesystem"]
        self.assertIn(str(self.repo / ".git" / "hooks"), fs["denyWrite"])
        self.assertIn(str(self.repo / ".git" / "config"), fs["denyWrite"])
        vedadas = [os.path.realpath(v) for v in fs["denyWrite"]]
        self.assertIn(os.path.realpath(self.otro), vedadas)
        self.assertNotIn(os.path.realpath(self.mio), vedadas)
        self.assertNotIn(os.path.realpath(self.repo), vedadas)

    def test_github_abre_su_servidor_y_su_api_y_pasa_el_token(self):
        git(self.repo, "remote", "add", "gh", "https://github.com/alguien/x.git")
        hecho = self.armar(token=lambda entorno: "gho_falso")
        self.assertEqual(hecho["ajustes"]["sandbox"]["network"]["allowedDomains"],
                         ["github.com", "api.github.com"])
        self.assertEqual(hecho["entorno"], {"COTEJO_SANDBOX": "1", "GH_TOKEN": "gho_falso"})
        self.assertEqual(hecho["avisos"], [])

    def test_un_remoto_por_ssh_se_avisa(self):
        git(self.repo, "remote", "add", "otro", "git@gitlab.com:a/b.git")
        hecho = self.armar()
        self.assertIn("gitlab.com", hecho["ajustes"]["sandbox"]["network"]["allowedDomains"])
        self.assertEqual(len(hecho["avisos"]), 1)
        self.assertIn("SSH", hecho["avisos"][0])

    def test_la_config_suma_dominios_y_carpetas(self):
        hecho = self.armar(ajustes={"dominios": ["pypi.org"], "escritura": ["~/.cache/pip"]})
        s = hecho["ajustes"]["sandbox"]
        self.assertIn("pypi.org", s["network"]["allowedDomains"])
        self.assertIn(str(Path("~/.cache/pip").expanduser()), s["filesystem"]["allowWrite"])


class SinUpstream(unittest.TestCase):
    """Dentro del sandbox `.git/config` no se escribe: `git push -u` pierde el `-u`."""

    def test_quita_el_u_y_nada_mas(self):
        from enrutador.guarda_git import sin_upstream
        casos = [(["push", "-u", "origin", "HEAD"], ["push", "origin", "HEAD"], True),
                 (["-C", "x", "push", "-uq", "origin", "b"],
                  ["-C", "x", "push", "-q", "origin", "b"], True),
                 (["push", "--set-upstream", "origin", "b"], ["push", "origin", "b"], True),
                 (["push", "-o", "u", "origin"], ["push", "-o", "u", "origin"], False),
                 (["push", "-ou", "origin"], ["push", "-ou", "origin"], False),
                 (["push", "origin", "--", "-u"], ["push", "origin", "--", "-u"], False),
                 (["status", "-u"], ["status", "-u"], False)]
        for args, esperado, quitado in casos:
            with self.subTest(args):
                self.assertEqual(sin_upstream(args), (esperado, quitado))

    @unittest.skipUnless(HAY_GIT and os.name != "nt", "sin git o en Windows")
    def test_la_guarda_empuja_sin_u_dentro_del_sandbox(self):
        from enrutador import guardas
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            subprocess.run(["git", "init", "-q", "--bare", str(base / "r.git")], check=True)
            repo = base / "repo"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            git(repo, "commit", "-q", "--allow-empty", "-m", "x")
            git(repo, "remote", "add", "origin", str(base / "r.git"))
            git(repo, "checkout", "-q", "-b", "cotejo/x")
            entorno = {**os.environ, **guardas.entorno({"COTEJO_SANDBOX": "1"}, ["main"],
                                                       destino=base / "g")}
            hecho = subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin",
                                    "cotejo/x"], capture_output=True, text=True, env=entorno)
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            self.assertIn("sin «-u»", hecho.stderr)
            config = subprocess.run(["git", "-C", str(repo), "config", "--get",
                                     "branch.cotejo/x.remote"], capture_output=True, text=True)
            self.assertEqual(config.stdout.strip(), "")   # no tocó .git/config


class Token(unittest.TestCase):
    def test_no_lo_pide_si_ya_hay_uno(self):
        correr = mock.Mock()
        self.assertEqual(sandbox.token_de_gh({"GH_TOKEN": "x"}, correr), "")
        correr.assert_not_called()

    def test_sin_sesion_no_hay_token(self):
        fallo = mock.Mock(return_value=mock.Mock(returncode=1, stdout=""))
        with mock.patch.object(shutil, "which", return_value="/usr/bin/gh"):
            self.assertEqual(sandbox.token_de_gh({}, fallo), "")
        bien = mock.Mock(return_value=mock.Mock(returncode=0, stdout="gho_x\n"))
        with mock.patch.object(shutil, "which", return_value="/usr/bin/gh"):
            self.assertEqual(sandbox.token_de_gh({}, bien), "gho_x")


class Disponible(unittest.TestCase):
    """Sin sandbox el agente sigue trabajando: solo no se pide, y se dice por qué."""

    def test_linux_sin_bwrap_ni_socat(self):
        hay, motivo = sandbox.disponible("linux", lambda d: None, lambda b: True)
        self.assertFalse(hay)
        self.assertIn("bwrap", motivo)
        self.assertIn("socat", motivo)

    def test_linux_con_bwrap_que_no_arranca(self):
        hay, motivo = sandbox.disponible("linux", lambda d: f"/usr/bin/{d}", lambda b: False)
        self.assertFalse(hay)
        self.assertIn("espacio de nombres", motivo)

    def test_linux_con_todo(self):
        self.assertEqual(sandbox.disponible("linux", lambda d: f"/usr/bin/{d}", lambda b: True),
                         (True, ""))

    def test_windows_no(self):
        self.assertFalse(sandbox.disponible("windows")[0])


class SandboxDe(unittest.TestCase):
    def setUp(self):
        self.cotejo = mock.Mock()
        self.cotejo.carpeta_de_la_tarea.return_value = None
        self.config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})

    def de(self, cliente="claude", config=None):
        return despacho_board.sandbox_de(config or self.config, clientes.de(cliente),
                                         self.cotejo, {"id": "cotejo-x"}, Path("/w/tarea"))

    def test_solo_claude(self):
        for nombre in ("codex", "opencode", "gemini"):
            with self.subTest(nombre):
                hecho = self.de(nombre)
                self.assertFalse(hecho["activo"])
                self.assertIsNone(hecho["ajustes"])

    def test_sin_sandbox_en_la_maquina_trabaja_sin_el_y_dice_por_que(self):
        with mock.patch.object(sandbox, "disponible", return_value=(False, "falta bwrap")):
            hecho = self.de()
        self.assertEqual((hecho["activo"], hecho["motivo"], hecho["ajustes"]),
                         (False, "falta bwrap", None))

    def test_apagado_en_la_config(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {"lanzar": {"sandbox": False}})
        with mock.patch.object(sandbox, "disponible", return_value=(True, "")):
            hecho = self.de(config=config)
        self.assertFalse(hecho["activo"])
        self.assertIn("lanzar.sandbox", hecho["motivo"])

    def test_disponible_lo_lleva_con_la_carpeta_de_la_tarea(self):
        self.cotejo.carpeta_de_la_tarea.return_value = Path("/r/repo/.cotejo")
        with mock.patch.object(sandbox, "disponible", return_value=(True, "")):
            hecho = self.de()
        self.assertTrue(hecho["activo"])
        self.assertIn("/r/repo/.cotejo",
                      hecho["ajustes"]["sandbox"]["filesystem"]["allowWrite"])


@unittest.skipUnless(HAY_GIT, "sin git")
class LanzarEncerrado(unittest.TestCase):
    """El board de verdad con el cliente falso: el argv lleva el sandbox con su worktree, el
    encargo lo dice y el registro lo guarda; sin sandbox, el registro dice por qué."""

    def correr(self, disponible, comprobar):
        from test_despacho_board import ConClienteFalso, esperar

        class Caso(ConClienteFalso):
            def runTest(self):
                terminado = []
                with mock.patch.object(sandbox, "disponible", return_value=disponible):
                    self.lanzar("cotejo-asig", al_terminar=terminado.append)
                self.assertTrue(esperar(lambda: terminado))
                comprobar(self, json.loads(self.argv_falso.read_text())["argv"],
                          despacho_board.lanzados.leer("cotejo-asig"))

        resultado = unittest.TestResult()
        Caso().run(resultado)
        self.assertEqual(resultado.errors + resultado.failures, [])

    def test_con_sandbox(self):
        def comprobar(caso, argv, registro):
            s = ajustes_de(argv)
            caso.assertIsNotNone(s)
            caso.assertIn(registro["worktree"]["ruta"], s["filesystem"]["allowWrite"])
            caso.assertIn(str(Path(registro["worktree"]["repo"]) / ".git" / "hooks"),
                          s["filesystem"]["denyWrite"])
            caso.assertEqual(registro["sandbox"], {"activo": True, "motivo": "", "avisos": []})
            caso.assertIn("sandbox", argv[-1])
            caso.assertIn("Bash(sudo *)", argv)   # los prohibidos siguen debajo
        self.correr((True, ""), comprobar)

    def test_sin_sandbox(self):
        def comprobar(caso, argv, registro):
            caso.assertNotIn("--settings", argv)
            caso.assertEqual(registro["sandbox"]["activo"], False)
            caso.assertEqual(registro["sandbox"]["motivo"], "falta bwrap")
            caso.assertNotIn("sistema de ficheros de solo lectura", argv[-1])
            caso.assertIn("Bash(sudo *)", argv)
        self.correr((False, "falta bwrap"), comprobar)


if __name__ == "__main__":
    unittest.main()
