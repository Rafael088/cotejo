"""Lo que el proyecto le haría arrancar a Gemini CLI y a OpenCode, fuera (cotejo-lbwsq4).

Sigue a `test_mcp_del_proyecto.py` (cotejo-j42qfc), que cerró los servidores MCP del proyecto en
Claude, Codex y OpenCode:

- **Gemini CLI**: Cotejo le da la confianza al worktree (`GEMINI_CLI_TRUST_WORKSPACE=true`,
  sin ella no corre sin interfaz) y con ella leía el `.gemini/settings.json` del proyecto: sus
  servidores MCP arrancaban, y sus hooks y su `tools.discoveryCommand` corrían sin que nadie lo
  pidiera. Los servidores van fuera con `--allowed-mcp-server-names` (los de la persona sí);
  hooks y comandos no tienen bandera que los apague, y con ellos el worktree va sin confianza.
- **OpenCode**: importa los plugins y herramientas en JavaScript del proyecto
  (`.opencode/plugin(s)`, `.opencode/tool(s)`, `plugin` en su `opencode.json`). Con ellos va
  `OPENCODE_DISABLE_PROJECT_CONFIG`; los de la persona siguen.

Aquí se mira el argv y el entorno. Con los clientes de verdad, solo si se pide
(`COTEJO_PRUEBA_CLIENTES=1`): `opencode mcp list` y `gemini mcp list`, que no llaman a ningún
modelo, y una sesión de Gemini **sin red** (`unshare -rn`, sin prompt, con una clave falsa), que
no puede llegar a ninguno. Todo con casas falsas en carpetas temporales.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import armado, clientes, config as cfg

BANDERA = "--allowed-mcp-server-names"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.wt = self.tmp / "wt"
        self.wt.mkdir()
        self.casa = self.tmp / "casa"
        (self.casa / ".gemini").mkdir(parents=True)
        # La persona, en una casa falsa: nada de `~/.gemini` ni de `/etc/gemini-cli`.
        self.entorno = {"GEMINI_CLI_HOME": str(self.casa),
                        "GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(self.tmp / "sistema.json")}
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                              "COTEJO_CONFIG": str(self.tmp / "c.json"),
                                              **self.entorno})
        parche.start()
        self.addCleanup(parche.stop)
        os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
        os.environ.pop("GEMINI_CLI_SYSTEM_DEFAULTS_PATH", None)


class Gemini(Base):
    def proyecto(self, ajustes):
        (self.wt / ".gemini").mkdir(exist_ok=True)
        texto = ajustes if isinstance(ajustes, str) else json.dumps(ajustes)
        (self.wt / ".gemini" / "settings.json").write_text(texto)

    def persona(self, ajustes, ruta=None):
        Path(ruta or self.casa / ".gemini" / "settings.json").write_text(json.dumps(ajustes))

    def lanzar(self):
        return clientes.de("gemini").terminal_libre([str(self.wt)], "main",
                                                    politica_gemini="/e/g.toml")

    def permitidos(self, argv):
        self.assertEqual(argv.count(BANDERA), 1)
        return argv[argv.index(BANDERA) + 1].split(",")

    def test_sin_config_del_proyecto_no_cambia_nada(self):
        argv, entorno = self.lanzar()
        self.assertEqual(argv, ["--approval-mode", "auto_edit", "--policy", "/e/g.toml"])
        self.assertEqual(entorno, {"GEMINI_CLI_TRUST_WORKSPACE": "true"})
        self.proyecto({"ui": {"theme": "x"}})         # ajustes sin nada que arranque
        self.assertEqual(self.lanzar(), (argv, entorno))

    def test_los_del_proyecto_fuera_y_los_de_la_persona_siguen(self):
        self.persona({"mcpServers": {"mio": {"command": "mio"}, "otro": {"url": "http://x"}}})
        self.persona({"mcpServers": {"admin": {"command": "a"}}}, self.tmp / "sistema.json")
        ext = self.casa / ".gemini" / "extensions" / "ext"
        ext.mkdir(parents=True)
        (ext / "gemini-extension.json").write_text(json.dumps(
            {"name": "ext", "mcpServers": {"de-extension": {"command": "e"}}}))
        self.proyecto('{\n // del proyecto\n "mcpServers": {"trampa": {"command": "sh"},},\n}')
        argv, entorno = self.lanzar()
        self.assertEqual(sorted(self.permitidos(argv)), ["admin", "de-extension", "mio", "otro"])
        self.assertEqual(entorno["GEMINI_CLI_TRUST_WORKSPACE"], "true")
        self.assertEqual(argv[:4], ["--approval-mode", "auto_edit", "--policy", "/e/g.toml"])

    def test_uno_que_el_proyecto_redefine_ya_no_es_el_suyo(self):
        self.persona({"mcpServers": {"mio": {"command": "mio"}, "github": {"command": "g"}}})
        self.proyecto({"mcpServers": {"github": {"command": "sh"}}})
        self.assertEqual(self.permitidos(self.lanzar()[0]), ["mio"])

    def test_sin_servidores_de_la_persona_ninguno(self):
        self.proyecto({"mcpServers": {"trampa": {}, clientes.NINGUN_SERVIDOR_GEMINI: {}}})
        lista = self.permitidos(self.lanzar()[0])
        self.assertEqual(len(lista), 1)
        self.assertNotIn(lista[0], {"", "trampa", clientes.NINGUN_SERVIDOR_GEMINI})

    def test_respeta_sus_permitidos_y_excluidos(self):
        self.persona({"mcpServers": {"a": {}, "b": {}, "c": {}},
                      "mcp": {"allowed": ["a", "b"], "excluded": ["b"]}})
        self.proyecto({"mcpServers": {"trampa": {}}})
        self.assertEqual(self.permitidos(self.lanzar()[0]), ["a"])

    def test_el_server_command_del_proyecto_es_un_servidor_mas(self):
        self.persona({"mcpServers": {"mio": {}}})
        self.proyecto({"mcp": {"serverCommand": "sh -c 'touch x'"}})
        self.assertEqual(self.permitidos(self.lanzar()[0]), ["mio"])

    def test_hooks_y_comandos_dejan_el_worktree_sin_confianza(self):
        casos = {
            "hooks": {"hooks": {"SessionStart": [{"hooks": [{"type": "command",
                                                            "command": "touch x"}]}]}},
            "descubrir": {"tools": {"discoveryCommand": "touch x"}},
            "llamar": {"tools": {"callCommand": "touch x"}},
            "políticas": {"policyPaths": ["p.toml"]},
            "de administrador": {"adminPolicyPaths": ["p.toml"]},
            "roto": "{ esto no es json",
        }
        for nombre, ajustes in casos.items():
            with self.subTest(nombre):
                self.proyecto(ajustes)
                argv, entorno = self.lanzar()
                self.assertEqual(entorno["GEMINI_CLI_TRUST_WORKSPACE"], "false")
                self.assertNotIn(BANDERA, argv)

    def test_hooks_vacios_no_cuentan(self):
        self.proyecto({"hooks": {"SessionStart": []}, "tools": {"discoveryCommand": ""}})
        self.assertEqual(self.lanzar()[1]["GEMINI_CLI_TRUST_WORKSPACE"], "true")

    def test_el_armado_lo_lleva(self):
        self.proyecto({"mcpServers": {"trampa": {}}})
        argv = armado.comando(cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {}), clientes.de("gemini"), "gemini-2.5-pro", None,
                              "P", [str(self.wt)], ["main"], politica_gemini="/e/g.toml")
        self.assertIn(BANDERA, argv)
        self.assertEqual(argv[-2:], ["-p", "P"])
        self.proyecto({"tools": {"discoveryCommand": "x"}})
        entorno = armado.entorno(clientes.de("gemini"), [str(self.wt)], ["main"],
                                 {"activo": False, "entorno": {}})
        self.assertEqual(entorno["GEMINI_CLI_TRUST_WORKSPACE"], "false")

    def test_el_inicio_no_cambia(self):
        # `permisos` (preparar) no mira el proyecto: es la carpeta que la persona eligió.
        self.proyecto({"tools": {"discoveryCommand": "x"}})
        self.assertEqual(clientes.de("gemini").permisos([str(self.wt)]),
                         ([], {"GEMINI_CLI_TRUST_WORKSPACE": "true"}))


class OpenCode(Base):
    def entorno_de(self):
        return clientes.de("opencode").terminal_libre([str(self.wt)], "main")[1]

    def test_sin_codigo_del_proyecto_no_cambia_nada(self):
        (self.wt / ".opencode" / "agents").mkdir(parents=True)     # markdown: no es código
        (self.wt / ".opencode" / "agents" / "a.md").write_text("x")
        (self.wt / ".opencode" / "plugins").mkdir()                # vacía
        (self.wt / "opencode.json").write_text(json.dumps({"plugin": []}))
        self.assertNotIn("OPENCODE_DISABLE_PROJECT_CONFIG", self.entorno_de())

    def test_con_plugins_o_herramientas_sin_la_config_del_proyecto(self):
        for carpeta in clientes.CODIGO_OPENCODE_DEL_PROYECTO:
            with self.subTest(carpeta):
                ruta = self.wt / carpeta / "sub"
                ruta.mkdir(parents=True)
                (ruta / "x.js").write_text("export default {}")
                entorno = self.entorno_de()
                self.assertEqual(entorno["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
                self.assertEqual(json.loads(entorno["OPENCODE_CONFIG_CONTENT"])
                                 ["permission"]["bash"]["sudo *"], "deny")   # los prohibidos, sí
                shutil.rmtree(self.wt / ".opencode")

    def test_un_plugin_en_su_config(self):
        (self.wt / ".opencode").mkdir()
        (self.wt / ".opencode" / "opencode.jsonc").write_text(
            '{\n  // un plugin de npm\n  "plugin": ["paquete-raro"],\n}')
        self.assertEqual(self.entorno_de()["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")

    def test_los_de_la_persona_siguen_en_su_config(self):
        propio = {"plugin": ["mio"], "mcp": {"mio": {"type": "local", "command": ["m"]}}}
        (self.wt / ".opencode" / "plugin").mkdir(parents=True)
        (self.wt / ".opencode" / "plugin" / "t.js").write_text("")
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_CONTENT": json.dumps(propio)}):
            datos = json.loads(self.entorno_de()["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(datos["plugin"], ["mio"])
        self.assertEqual(datos["mcp"], propio["mcp"])


def repo_con_worktree(base):
    repo, wt = base / "repo", base / "wt"
    git = ["git", "-c", "user.name=p", "-c", "user.email=p@p"]
    subprocess.run(git + ["init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "LEEME").write_text("x\n")
    subprocess.run(git + ["-C", str(repo), "add", "-A"], check=True)
    subprocess.run(git + ["-C", str(repo), "commit", "-qm", "inicio"], check=True)
    subprocess.run(git + ["-C", str(repo), "worktree", "add", "-q", "-b", "cotejo/x", str(wt)],
                   check=True)
    return repo, wt


def marca(nombre):
    """Un comando que deja `$MARCAS/<nombre>` si corre."""
    return ["sh", "-c", f'touch "$MARCAS/{nombre}"; sleep 30']


def plugin(nombre):
    """Un plugin de OpenCode que deja `$MARCAS/<nombre>` si se importa."""
    return ('import fs from "node:fs";\n'
            f'fs.writeFileSync(process.env.MARCAS + "/{nombre}", "x");\n'
            f'export const P_{nombre} = async () => ({{}});\n')


def sin_red():
    """¿Se puede abrir un proceso sin red (`unshare -rn`) y con terminal (`script`)?"""
    if not (shutil.which("unshare") and shutil.which("script")):
        return False
    return subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLIENTES") == "1",
                     "con los clientes de verdad (sin modelo): COTEJO_PRUEBA_CLIENTES=1")
class ConLosClientesDeVerdad(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-lbwsq4-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.repo, self.wt = repo_con_worktree(self.base)
        self.ronda = 0

    def marcas(self):
        self.ronda += 1
        carpeta = self.base / f"marcas-{self.ronda}"
        carpeta.mkdir()
        return carpeta

    # --- OpenCode -------------------------------------------------------------------------

    @unittest.skipUnless(shutil.which("opencode"), "sin opencode")
    def test_opencode_plugins(self):
        xdg = {f"XDG_{k}_HOME": str(self.base / k.lower())
               for k in ("CONFIG", "DATA", "CACHE", "STATE")}
        (self.base / "config" / "opencode" / "plugin").mkdir(parents=True)
        (self.base / "config" / "opencode" / "plugin" / "mio.js").write_text(plugin("mio"))
        (self.wt / ".opencode" / "plugins").mkdir(parents=True)
        (self.wt / ".opencode" / "plugins" / "trampa.js").write_text(plugin("trampa"))
        base = {k: v for k, v in os.environ.items() if k != "OPENCODE_CONFIG_CONTENT"}
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
            cotejo = clientes.de("opencode").terminal_libre([str(self.wt)], "main")[1]

        def lista(env):
            marcas = self.marcas()
            subprocess.run(["opencode", "mcp", "list"], cwd=self.wt, timeout=120,
                           env={**base, **xdg, **env, "MARCAS": str(marcas)},
                           capture_output=True, text=True)
            time.sleep(1)
            return {p.name for p in marcas.iterdir()}
        self.assertEqual(lista({}), {"mio", "trampa"})        # sin lo de Cotejo, arrancaba
        self.assertEqual(lista(cotejo), {"mio"})

    # --- Gemini CLI -----------------------------------------------------------------------

    def gemini_casa(self, proyecto):
        casa = self.base / "casa"
        (casa / ".gemini").mkdir(parents=True, exist_ok=True)
        (casa / ".gemini" / "settings.json").write_text(json.dumps({
            "security": {"auth": {"selectedType": "gemini-api-key"}},
            "mcpServers": {"mio": {"command": marca("mio")[0], "args": marca("mio")[1:]}}}))
        (self.wt / ".gemini").mkdir(exist_ok=True)
        (self.wt / ".gemini" / "settings.json").write_text(json.dumps(proyecto))
        return {**os.environ, "GEMINI_CLI_HOME": str(casa), "GEMINI_API_KEY": "falsa",
                "GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(self.base / "sistema.json")}

    def cotejo_gemini(self, entorno):
        with mock.patch.dict(os.environ, entorno):
            return clientes.de("gemini").terminal_libre([str(self.wt)], "main")

    @unittest.skipUnless(shutil.which("gemini"), "sin gemini")
    def test_gemini_mcp_list_carga_los_del_proyecto(self):
        """La trampa muerde: con la confianza que da Cotejo, `gemini mcp list` arranca el
        servidor del `.gemini/settings.json` del worktree (y el de la persona)."""
        entorno = self.gemini_casa({"mcpServers": {"trampa": {
            "command": marca("trampa")[0], "args": marca("trampa")[1:]}}})
        marcas = self.marcas()
        subprocess.run(["gemini", "mcp", "list"], cwd=self.wt, timeout=120, capture_output=True,
                       env={**entorno, "GEMINI_CLI_TRUST_WORKSPACE": "true",
                            "MARCAS": str(marcas)})
        time.sleep(1)
        self.assertEqual({p.name for p in marcas.iterdir()}, {"mio", "trampa"})

    def gemini_sesion(self, argv, env):
        """Gemini interactivo sin prompt y sin red, 25 s: lo que arranca solo al abrir."""
        marcas = self.marcas()
        orden = " ".join(["gemini", *[f"'{a}'" for a in argv]])
        subprocess.run(["timeout", "25", "unshare", "-rn", "script", "-qfc", orden, "/dev/null"],
                       cwd=self.wt, env={**env, "MARCAS": str(marcas)}, timeout=60,
                       stdin=subprocess.DEVNULL, capture_output=True)
        time.sleep(1)
        return {p.name for p in marcas.iterdir()}

    @unittest.skipUnless(shutil.which("gemini") and sin_red(), "sin gemini o sin unshare")
    def test_gemini_sesion_sin_los_del_proyecto(self):
        entorno = self.gemini_casa({"mcpServers": {"trampa": {
            "command": marca("trampa")[0], "args": marca("trampa")[1:]}}})
        confianza = {**entorno, "GEMINI_CLI_TRUST_WORKSPACE": "true"}
        self.assertEqual(self.gemini_sesion([], confianza), {"mio", "trampa"})
        argv, env = self.cotejo_gemini(entorno)
        self.assertEqual(self.gemini_sesion(argv, {**entorno, **env}), {"mio"})

    @unittest.skipUnless(shutil.which("gemini") and sin_red(), "sin gemini o sin unshare")
    def test_gemini_sesion_hooks_sin_confianza(self):
        entorno = self.gemini_casa({"hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "command": 'touch "$MARCAS/hook"'}]}]}})
        confianza = {**entorno, "GEMINI_CLI_TRUST_WORKSPACE": "true"}
        self.assertIn("hook", self.gemini_sesion(["--allowed-mcp-server-names", "mio"],
                                                 confianza))   # ninguna bandera lo para
        argv, env = self.cotejo_gemini(entorno)
        self.assertEqual(env["GEMINI_CLI_TRUST_WORKSPACE"], "false")
        self.assertNotIn("hook", self.gemini_sesion(argv, {**entorno, **env}))


if __name__ == "__main__":
    unittest.main()
