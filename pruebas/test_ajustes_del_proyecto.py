"""Claude Code no carga los ajustes del proyecto que haya en el worktree (cotejo-0hgn6x).

El agente del board retoma una tarea con un Claude nuevo en el mismo worktree, y Claude carga
`.claude/settings.json` y `.claude/settings.local.json` de donde arranca, también si aparecen a
media sesión. Un hook que dejara ahí otro agente (Codex u OpenCode no pasan por el sandbox de
Claude) o el mismo con el sandbox apagado correría fuera del sandbox, y un `allowWrite` o un
`env` lo cambiarían. `denyWrite` no sirve para un archivo que no existe (cotejo-dgb7l2), así que
el armado le pasa `--setting-sources user`: solo los ajustes de la persona y los de `--settings`.

Aquí se mira el argv. La prueba con Claude de verdad (haiku, un prompt mínimo, todo en una
carpeta temporal) solo corre si se pide con `COTEJO_PRUEBA_CLAUDE=1` y hay `claude`: la suite
nunca lanza un agente real.
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

from enrutador import armado, clientes, config as cfg, sandbox
from tareas import preparacion

BANDERA = list(clientes.SOLO_AJUSTES_DE_LA_PERSONA)


def config(encima=None):
    return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), encima or {})


def tramo(argv, bandera):
    """Las posiciones donde aparece `bandera` (una lista seguida) dentro de `argv`."""
    return [i for i in range(len(argv)) if argv[i:i + len(bandera)] == bandera]


class Argv(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        entorno = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                               "COTEJO_CONFIG": str(self.tmp / "c.json")})
        entorno.start()
        self.addCleanup(entorno.stop)

    def test_claude_solo_carga_los_ajustes_de_la_persona(self):
        argv = armado.comando(config(), clientes.de("claude"), "haiku", None, "P", ["/w"],
                              ["main"])
        donde = tramo(argv, BANDERA)
        self.assertEqual(len(donde), 1, argv)
        # Antes de `--disallowedTools`, que se come lo que venga detrás, y del prompt.
        self.assertLess(donde[0], argv.index("--disallowedTools"))
        self.assertEqual(argv[-2:], ["--", "P"])

    def test_tambien_con_el_sandbox(self):
        ajustes = sandbox.ajustes_claude(["/w"])
        argv, _ = clientes.de("claude").terminal_libre(["/w"], "main", sandbox=ajustes)
        self.assertEqual(len(tramo(argv, BANDERA)), 1)
        self.assertIn("--settings", argv)   # lo que pasa Cotejo sigue cargando

    def test_va_detras_de_lo_que_pida_la_config(self):
        # Lo de la persona va antes; la de Cotejo queda la última y es la que vale.
        argv = armado.comando(config({"lanzar": {"argumentos_extra": {"claude": [
            "--setting-sources", "user,project,local"]}}}), clientes.de("claude"), "haiku",
            None, "P", ["/w"], ["main"])
        valores = [argv[i + 1] for i, a in enumerate(argv) if a == "--setting-sources"]
        self.assertEqual(valores[-1], "user")

    def test_los_demas_clientes_no_la_llevan(self):
        for nombre in ("codex", "opencode", "gemini", "antigravity"):
            with self.subTest(nombre):
                argv, _ = clientes.de(nombre).terminal_libre(["/w"], "main")
                self.assertNotIn("--setting-sources", argv)

    def test_la_forma_de_la_bandera(self):
        # `claude --help` (2.1.304): «--setting-sources <sources>  Comma-separated list of
        # setting sources to load (user, project, local)»; si se repite, vale la última.
        self.assertEqual(BANDERA, ["--setting-sources", "user"])

@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLAUDE") == "1" and shutil.which("claude"),
                     "prueba con Claude de verdad: COTEJO_PRUEBA_CLAUDE=1 y claude instalado")
class ConClaudeDeVerdad(unittest.TestCase):
    """Un worktree con un `.claude/settings.json` y un `.claude/settings.local.json` que dejan
    un hook y una variable, y Claude (haiku) lanzado con el argv y el entorno del armado, con
    el sandbox si esta máquina lo tiene. Sin la bandera, el hook corre (la prueba muerde)."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-0hgn6x-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        entorno = mock.patch.dict(os.environ, {
            "COTEJO_ESTADO": str(self.base / "estado"),
            "COTEJO_CONFIG": str(self.base / "config" / "cotejo" / "config.json"),
            "XDG_CONFIG_HOME": str(self.base / "config")})
        entorno.start()
        self.addCleanup(entorno.stop)
        parche = mock.patch.object(preparacion, "CARPETA", self.base / "estado" / "prep")
        parche.start()
        self.addCleanup(parche.stop)
        self.repo, self.wt, self.marcas = (self.base / "repo", self.base / "wt",
                                           self.base / "marcas")
        self.marcas.mkdir()
        git = ["git", "-c", "user.name=p", "-c", "user.email=p@p"]
        subprocess.run(git + ["init", "-q", "-b", "main", str(self.repo)], check=True)
        (self.repo / "CLAUDE.md").write_text("La palabra clave de este repo es PIMIENTO.\n")
        subprocess.run(git + ["-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(git + ["-C", str(self.repo), "commit", "-qm", "inicio"], check=True)
        subprocess.run(git + ["-C", str(self.repo), "worktree", "add", "-q", "-b",
                              "cotejo/x", str(self.wt)], check=True)
        (self.wt / ".claude").mkdir()
        for nombre, archivo in (("local", "settings.local.json"), ("proyecto", "settings.json")):
            orden = f"touch {self.marcas}/{nombre}"
            (self.wt / ".claude" / archivo).write_text(json.dumps({
                "hooks": {ev: [{"hooks": [{"type": "command", "command": f"{orden}-{ev}"}]}]
                          for ev in ("SessionStart", "UserPromptSubmit", "PreToolUse")},
                "env": {f"MARCA_{nombre.upper()}": "si"}}))

    def lanzar(self, sin_bandera=False):
        cliente = clientes.de("claude")
        worktree = {"repo": str(self.repo), "ruta": str(self.wt)}
        carpetas = armado.carpetas_de_escritura(str(self.wt), worktree)
        ramas = armado.ramas_protegidas(str(self.wt), worktree)
        hay, _ = sandbox.disponible()
        encerrado = ({"activo": True, **sandbox.del_lanzamiento(
            carpetas, repo=str(self.repo), propio=str(self.wt), token=None,
            vedadas=armado.vedados())} if hay else {"activo": False, "entorno": {}})
        prompt = ("Responde en una línea: la palabra clave del CLAUDE.md y lo que imprime "
                  "`echo L=$MARCA_LOCAL P=$MARCA_PROYECTO` (córrelo con Bash una vez).")
        argv = armado.comando(config(), cliente, "haiku", None, prompt, carpetas, ramas,
                              sandbox=encerrado.get("ajustes"))
        if sin_bandera:
            i = tramo(argv, BANDERA)[0]
            argv = argv[:i] + argv[i + len(BANDERA):]
        hecho = subprocess.run(argv, cwd=self.wt, stdin=subprocess.DEVNULL, timeout=300,
                               env={**armado.entorno(cliente, carpetas, ramas, encerrado),
                                    "PWD": str(self.wt)}, capture_output=True, text=True)
        final = ""
        for linea in hecho.stdout.splitlines():
            try:
                dato = json.loads(linea)
            except ValueError:
                continue
            if dato.get("type") == "result":
                final = dato.get("result") or ""
        return hecho, final

    def test_los_ajustes_del_worktree_no_se_cargan(self):
        hecho, final = self.lanzar()
        self.assertEqual(hecho.returncode, 0, hecho.stderr[-2000:])
        self.assertEqual(sorted(p.name for p in self.marcas.iterdir()), [])
        self.assertNotIn("=si", final)
        self.assertIn("PIMIENTO", final)    # el CLAUDE.md del repo sí

    def test_sin_la_bandera_si_se_cargaban(self):
        hecho, final = self.lanzar(sin_bandera=True)
        self.assertEqual(hecho.returncode, 0, hecho.stderr[-2000:])
        marcas = {p.name for p in self.marcas.iterdir()}
        self.assertIn("local-SessionStart", marcas)
        self.assertIn("proyecto-SessionStart", marcas)


if __name__ == "__main__":
    unittest.main()
