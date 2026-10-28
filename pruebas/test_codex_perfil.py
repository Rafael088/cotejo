"""Codex entrega y commitea desde el board (cotejo-srkywv).

Con `--sandbox workspace-write --add-dir …` el agente Codex que lanza el board no podía terminar
ninguna tarea: su sandbox deja el `.git` de cada carpeta que escribe —y la carpeta a la que apunta
el `gitdir:` de un worktree— en solo lectura, así que `git commit` fallaba con `index.lock`; la
carpeta del archivo de la tarea (el `.cotejo/` del repo) no estaba entre las suyas, así que
`cotejo entregar` y `cotejo bloquear` fallaban; y sin red su seccomp niega hasta los sockets
locales, así que ni Firefox arranca ni se abre un puerto.

Ahora va con un perfil de permisos (`clientes._codex_perfil`) armado con las mismas carpetas que
el sandbox de Claude (`sandbox.del_lanzamiento`). Aquí se mira el argv; con
`COTEJO_PRUEBA_CLIENTES=1` se corre `codex sandbox` de verdad (sin modelo) en un repo temporal:
commitea en su worktree, escribe la carpeta de la tarea y no toca hooks, config ni el otro
worktree. La suite nunca lanza un agente real.
"""

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import armado, clientes, config as cfg, sandbox

HAY_GIT = shutil.which("git") is not None


def config(encima=None):
    return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), encima or {})


def git(carpeta, *args):
    return subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=P", "-c", "user.email=p@p",
                           *args], capture_output=True, text=True, check=True)


def perfil(argv):
    """El perfil que lleva un argv de Codex, leído como lo lee Codex (TOML)."""
    clave = f"permissions.{clientes.PERFIL_CODEX}="
    valor = next(a for a in argv if a.startswith(clave))[len(clave):]
    return tomllib.loads("p = " + valor)["p"]


class Perfil(unittest.TestCase):
    CAJA = sandbox.ajustes_claude(["/w/t", "/r/.git", "/e", "/r/.cotejo"],
                                  ["/r/.git/hooks", "/r/.git/config", "/e/wt/otra"])

    def argv(self, caja=CAJA, trabajo="/w/t"):
        return clientes.de("codex").terminal_libre([trabajo, "/r/.git", "/e"], "main",
                                                  sandbox=caja)[0]

    def test_sin_sandbox_y_con_su_perfil(self):
        argv = self.argv()
        self.assertNotIn("--sandbox", argv)
        self.assertNotIn("--add-dir", argv)
        self.assertIn(f'default_permissions="{clientes.PERFIL_CODEX}"', argv)
        self.assertIn("--skip-git-repo-check", argv)
        self.assertEqual(argv[argv.index("--enable") + 1], "network_proxy")

    def test_escribe_donde_claude_y_lo_vedado_solo_se_lee(self):
        datos = perfil(self.argv())
        self.assertEqual(datos["extends"], ":workspace")
        self.assertEqual(datos["filesystem"], {
            "/w/t": "write", "/r/.git": "write", "/e": "write", "/r/.cotejo": "write",
            "/r/.git/hooks": "read", "/r/.git/config": "read", "/e/wt/otra": "read"})

    def test_la_red_solo_lo_local(self):
        red = perfil(self.argv())["network"]
        self.assertTrue(red["enabled"])
        self.assertEqual(red["domains"], {"localhost": "allow", "127.0.0.1": "allow"})

    def test_el_gitdir_del_worktree_se_escribe(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "wt").mkdir()
        (tmp / "wt" / ".git").write_text("gitdir: ../repo/.git/worktrees/wt\n")
        datos = perfil(self.argv(trabajo=str(tmp / "wt")))
        self.assertEqual(datos["filesystem"][str(tmp / "repo/.git/worktrees/wt")], "write")
        self.assertIsNone(clientes._gitdir_de(tmp))          # sin .git
        self.assertIsNone(clientes._gitdir_de(None))

    def test_rutas_raras_siguen_siendo_toml(self):
        caja = sandbox.ajustes_claude(['/w/con "comillas" y \\ barra', "/w/ñandú"])
        self.assertIn('/w/con "comillas" y \\ barra', perfil(self.argv(caja))["filesystem"])

    def test_sin_sandbox_queda_como_antes(self):
        argv = self.argv(caja=None)
        self.assertEqual(argv[:2], ["--sandbox", "workspace-write"])

    def test_sigue_sin_confianza(self):
        self.assertIn(clientes._codex_sin_confianza("/w/t")[1], self.argv())


class SandboxDe(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        entorno = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                               "COTEJO_CONFIG": str(self.tmp / "c" / "c.json")})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.cotejo = mock.Mock()
        self.cotejo.carpeta_de_la_tarea.return_value = Path("/r/repo/.cotejo")

    def de(self, encima=None):
        return armado.sandbox_de(config(encima), clientes.de("codex"), self.cotejo, "cotejo-x",
                                 self.tmp / "wt")

    def test_lleva_la_carpeta_de_la_tarea_y_sin_token(self):
        with mock.patch.object(sandbox, "token_de_gh", side_effect=AssertionError("sin red")):
            hecho = self.de()
        self.assertTrue(hecho["activo"])
        self.assertEqual(hecho["cliente"], "codex")
        self.assertIn("/r/repo/.cotejo", hecho["ajustes"]["sandbox"]["filesystem"]["allowWrite"])
        self.assertNotIn("GH_TOKEN", hecho["entorno"])

    def test_la_config_de_cotejo_no(self):
        escribe = self.de()["ajustes"]["sandbox"]["filesystem"]["allowWrite"]
        self.assertNotIn(str(self.tmp / "c"), escribe)

    def test_apagar_el_de_claude_no_le_quita_el_perfil(self):
        self.assertTrue(self.de({"lanzar": {"sandbox": False}})["activo"])

    def test_en_windows_como_antes(self):
        with mock.patch.object(armado.os, "name", "nt"):
            self.assertFalse(self.de()["activo"])

    def test_el_comando_lo_lleva(self):
        encerrado = self.de()
        argv = armado.comando(config(), clientes.de("codex"), "gpt", "", "P",
                              [str(self.tmp / "wt")], ["main"], sandbox=encerrado["ajustes"])
        self.assertIn("/r/repo/.cotejo", perfil(argv)["filesystem"])
        self.assertEqual(argv[-1], "P")


class Nota(unittest.TestCase):
    def test_dice_que_commitee_y_como_capturar(self):
        with mock.patch.object(armado.navegador, "disponible_para_el_agente", return_value=True):
            nota = armado.nota({"activo": True, "cliente": "codex"})
        self.assertIn("commits", nota)
        self.assertIn("firefox --headless", nota)
        self.assertIn("--noproxy", nota)
        self.assertIn("no puedes empujar", nota)

    def test_sin_firefox_no_le_pide_capturas(self):
        with mock.patch.object(armado.navegador, "disponible_para_el_agente", return_value=False):
            nota = armado.nota({"activo": True, "cliente": "codex"})
        self.assertIn("no podrás sacarle capturas", nota)
        self.assertNotIn("firefox --headless", nota)


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLIENTES") == "1",
                     "con los clientes de verdad (sin modelo): COTEJO_PRUEBA_CLIENTES=1")
@unittest.skipUnless(HAY_GIT and shutil.which("codex"), "sin git o sin codex")
class ConCodexDeVerdad(unittest.TestCase):
    """`codex sandbox` con el perfil del board en un repo temporal: no llama a ningún modelo."""

    def setUp(self):
        # Bajo la casa y no en /tmp: `:workspace` deja escribir en /tmp, y taparía lo vedado.
        base = Path.home() / ".cache"
        base.mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="cotejo-codex-perfil-", dir=base))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        entorno = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                               "COTEJO_CONFIG": str(self.tmp / "c" / "c.json")})
        entorno.start()
        self.addCleanup(entorno.stop)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / ".cotejo").mkdir()
        (self.repo / ".cotejo" / "tareas.md").write_text("- [ ] x\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "inicio")
        wt = self.tmp / "estado" / "wt"
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/a", str(wt / "a"))
        git(self.repo, "worktree", "add", "-q", "-b", "cotejo/b", str(wt / "b"))
        self.wt, self.otro = wt / "a", wt / "b"

    def correr(self, guion):
        cotejo = mock.Mock()
        cotejo.carpeta_de_la_tarea.return_value = self.repo / ".cotejo"
        worktree = {"repo": str(self.repo), "ruta": str(self.wt)}
        encerrado = armado.sandbox_de(config(), clientes.de("codex"), cotejo, "x", self.wt,
                                      worktree)
        carpetas = armado.carpetas_de_escritura(self.wt, worktree)
        argv = clientes.de("codex").terminal_libre(carpetas, "main",
                                                  sandbox=encerrado["ajustes"])[0]
        # `codex sandbox` elige el perfil con -P y no conoce --skip-git-repo-check.
        limpias, saltar = [], False
        for i, a in enumerate(argv):
            if saltar:
                saltar = False
                continue
            if a == "--skip-git-repo-check":
                continue
            if a == "-c" and argv[i + 1].startswith("default_permissions="):
                saltar = True
                continue
            limpias.append(a)
        return subprocess.run(["codex", "sandbox", "-P", clientes.PERFIL_CODEX, *limpias,
                               "-C", str(self.wt), "--", "bash", "-c", guion],
                              cwd=self.wt, capture_output=True, text=True, timeout=120)

    def test_commitea_y_escribe_la_tarea_y_nada_mas(self):
        git_repo = self.repo / ".git"
        hecho = self.correr(
            "git -c user.name=P -c user.email=p@p commit -q --allow-empty -m hecho && echo C;"
            f" echo y >> {self.repo}/.cotejo/tareas.md && echo T;"
            f" touch {git_repo}/hooks/pre-commit && echo HOOK;"
            f" echo x >> {git_repo}/config && echo CONFIG;"
            f" touch {self.otro}/z && echo OTRO;"
            f" touch {self.repo}/z && echo REPO")
        lineas = hecho.stdout.split()
        self.assertEqual(lineas, ["C", "T"], hecho.stdout + hecho.stderr)
        self.assertIn("hecho", git(self.wt, "log", "--oneline", "-1").stdout)

    @unittest.skipUnless(shutil.which("firefox"), "sin firefox")
    def test_firefox_saca_la_captura(self):
        (self.wt / "i.html").write_text("<h1>hola</h1>")
        hecho = self.correr(armado.navegador.COMO_CAPTURAR.replace(
            "<url o file:///ruta>", (self.wt / "i.html").as_uri()))
        self.assertTrue((self.wt / "captura.png").exists(), hecho.stdout + hecho.stderr)


if __name__ == "__main__":
    unittest.main()
