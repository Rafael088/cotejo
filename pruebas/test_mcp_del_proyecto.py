"""Los servidores MCP que trae el proyecto no arrancan en el agente del board (cotejo-j42qfc).

Un servidor MCP es un programa que el cliente arranca él mismo, fuera de cualquier sandbox del
agente. Si el worktree trae uno —porque lo dejó otro agente que tuvo la tarea antes, o el mismo
con el sandbox apagado— el agente siguiente lo arrancaría sin preguntar. Los de la persona, en
cambio, tienen que seguir: el dueño no quiere perderlos.

- **Claude Code** lee el `.mcp.json` del proyecto y, sin interfaz, arranca sus servidores sin
  preguntar. `--setting-sources user` (cotejo-0hgn6x) ya lo deja fuera: es una de las tres
  formas que da https://code.claude.com/docs/en/mcp, y la única que conserva los de la persona
  sin copiarlos (`--strict-mcp-config` solo deja los de `--mcp-config`).
- **Codex** carga el `.codex/config.toml` de un proyecto de confianza, y un worktree hereda la
  del repo: va como proyecto sin confianza.
- **OpenCode** funde el `opencode.json[c]` del proyecto con la de la persona: los servidores que
  defina el proyecto van apagados en `OPENCODE_CONFIG_CONTENT`, que pesa más.

Aquí se mira el argv y el entorno. Las pruebas con los clientes de verdad solo corren si se
piden: `COTEJO_PRUEBA_CLAUDE=1` lanza Claude (haiku, un prompt mínimo) y
`COTEJO_PRUEBA_CLIENTES=1` pregunta a `codex mcp list` y `opencode mcp list`, que no llaman a
ningún modelo. Todo en carpetas temporales; la suite nunca lanza un agente real.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import tomllib
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
    return [i for i in range(len(argv)) if argv[i:i + len(bandera)] == bandera]


def config_opencode(entorno):
    return json.loads(entorno["OPENCODE_CONFIG_CONTENT"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        entorno = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                               "COTEJO_CONFIG": str(self.tmp / "c.json")})
        entorno.start()
        self.addCleanup(entorno.stop)
        os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
        self.wt = self.tmp / "wt"
        self.wt.mkdir()


class Claude(Base):
    def test_sin_los_del_proyecto_y_con_los_de_la_persona(self):
        argv = armado.comando(config(), clientes.de("claude"), "haiku", None, "P",
                              [str(self.wt)], ["main"])
        self.assertEqual(len(tramo(argv, BANDERA)), 1)
        # Ni `--strict-mcp-config` ni `--mcp-config`: se llevarían los de la persona.
        self.assertNotIn("--strict-mcp-config", argv)
        self.assertNotIn("--mcp-config", argv)


class Codex(Base):
    def test_el_worktree_va_sin_confianza(self):
        argv, entorno = clientes.de("codex").terminal_libre([str(self.wt), "/otra"], "main")
        i = argv.index("-c")
        tabla = tomllib.loads(argv[i + 1])
        self.assertEqual(tabla, {"projects": {str(self.wt): {"trust_level": "untrusted"}}})
        self.assertEqual(argv[:2], ["--sandbox", "workspace-write"])   # su sandbox sigue
        self.assertEqual(entorno, {})

    def test_tambien_en_el_armado(self):
        argv = armado.comando(config(), clientes.de("codex"), "gpt", None, "P",
                              [str(self.wt)], ["main"])
        self.assertIn(clientes._codex_sin_confianza(str(self.wt))[1], argv)
        self.assertEqual(argv[-1], "P")

    def test_una_ruta_rara_sigue_siendo_toml(self):
        rara = str(self.tmp / 'año "x" \\ y')
        valor = clientes._codex_sin_confianza(rara)[1]
        self.assertEqual(tomllib.loads(valor)["projects"][rara]["trust_level"], "untrusted")

    def test_relativa_va_absoluta(self):
        valor = clientes._codex_sin_confianza("wt")[1]
        self.assertIn(os.path.abspath("wt"), tomllib.loads(valor)["projects"])

    def test_sin_carpeta_nada(self):
        self.assertEqual(clientes._codex_sin_confianza(None), [])


class OpenCode(Base):
    def entorno(self, carpetas=None):
        return clientes.de("opencode").terminal_libre(carpetas or [str(self.wt)], "main")[1]

    def test_sin_config_del_proyecto_no_cambia_nada(self):
        datos = config_opencode(self.entorno())
        self.assertNotIn("mcp", datos)
        self.assertEqual(datos["permission"]["bash"]["*"], "allow")

    def test_los_del_proyecto_van_apagados(self):
        (self.wt / "opencode.json").write_text(json.dumps({"mcp": {"trampa": {
            "type": "local", "command": ["sh", "-c", "touch x"]}}}))
        (self.wt / ".opencode").mkdir()
        (self.wt / ".opencode" / "opencode.jsonc").write_text(
            '{\n  // un comentario, "con comillas"\n  "mcp": {"otra": {"type": "remote",'
            ' "url": "http://a/*b*/"}, /* otro */ },\n}\n')
        entorno = self.entorno()
        datos = config_opencode(entorno)
        self.assertEqual(datos["mcp"], {"trampa": {"enabled": False},
                                        "otra": {"enabled": False}})
        self.assertNotIn("OPENCODE_DISABLE_PROJECT_CONFIG", entorno)
        # Los prohibidos siguen.
        self.assertEqual(datos["permission"]["bash"]["sudo *"], "deny")

    def test_los_de_la_persona_siguen(self):
        propio = {"mio": {"type": "local", "command": ["mio"]}}
        (self.wt / "opencode.json").write_text(json.dumps({"mcp": {"trampa": {}}}))
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_CONTENT": json.dumps(
                {"mcp": propio})}):
            datos = config_opencode(self.entorno())
        self.assertEqual(datos["mcp"]["mio"], propio["mio"])
        self.assertEqual(datos["mcp"]["trampa"], {"enabled": False})

    def test_una_config_que_no_se_entiende_apaga_la_del_proyecto(self):
        (self.wt / "opencode.json").write_text("{ esto no es json")
        self.assertEqual(self.entorno()["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")

    def test_el_entorno_del_armado_lo_lleva(self):
        (self.wt / "opencode.json").write_text(json.dumps({"mcp": {"trampa": {}}}))
        entorno = armado.entorno(clientes.de("opencode"), [str(self.wt)], ["main"],
                                 {"activo": False, "entorno": {}})
        self.assertEqual(config_opencode(entorno)["mcp"]["trampa"], {"enabled": False})


class LosDemas(Base):
    def test_gemini_y_antigravity_no_cambian(self):
        for nombre in ("gemini", "antigravity"):
            with self.subTest(nombre):
                argv, _ = clientes.de(nombre).terminal_libre([str(self.wt)], "main")
                self.assertNotIn("-c", argv)
                self.assertNotIn("--strict-mcp-config", argv)


def repo_con_worktree(base):
    repo, wt = base / "repo", base / "wt"
    git = ["git", "-c", "user.name=p", "-c", "user.email=p@p"]
    subprocess.run(git + ["init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "CLAUDE.md").write_text("La palabra clave de este repo es PIMIENTO.\n")
    subprocess.run(git + ["-C", str(repo), "add", "-A"], check=True)
    subprocess.run(git + ["-C", str(repo), "commit", "-qm", "inicio"], check=True)
    subprocess.run(git + ["-C", str(repo), "worktree", "add", "-q", "-b", "cotejo/x", str(wt)],
                   check=True)
    return repo, wt


def trampa(marca):
    """Un servidor MCP de mentira: si arranca, deja `marca` en disco."""
    return ["sh", "-c", f"touch '{marca}'; sleep 5"]


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLAUDE") == "1" and shutil.which("claude"),
                     "prueba con Claude de verdad: COTEJO_PRUEBA_CLAUDE=1 y claude instalado")
class ConClaudeDeVerdad(unittest.TestCase):
    """Un worktree con un `.mcp.json` cuyo servidor deja una marca si arranca, y Claude (haiku)
    lanzado con el argv y el entorno del armado. Sin la bandera, arranca (la prueba muerde); con
    ella, no, y los servidores de la persona son los mismos en las dos."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-j42qfc-"))
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
        self.repo, self.wt = repo_con_worktree(self.base)
        self.marca = self.base / "marca"
        (self.wt / ".mcp.json").write_text(json.dumps({"mcpServers": {"trampa": {
            "command": trampa(self.marca)[0], "args": trampa(self.marca)[1:]}}}))

    def lanzar(self, sin_bandera=False):
        cliente = clientes.de("claude")
        worktree = {"repo": str(self.repo), "ruta": str(self.wt)}
        carpetas = armado.carpetas_de_escritura(str(self.wt), worktree)
        ramas = armado.ramas_protegidas(str(self.wt), worktree)
        hay, _ = sandbox.disponible()
        encerrado = ({"activo": True, **sandbox.del_lanzamiento(
            carpetas, repo=str(self.repo), propio=str(self.wt), token=None,
            vedadas=armado.vedados())} if hay else {"activo": False, "entorno": {}})
        argv = armado.comando(config(), cliente, "haiku", None,
                              "Responde solo con la palabra clave del CLAUDE.md.", carpetas,
                              ramas, sandbox=encerrado.get("ajustes"))
        if sin_bandera:
            i = tramo(argv, BANDERA)[0]
            argv = argv[:i] + argv[i + len(BANDERA):]
        hecho = subprocess.run(argv, cwd=self.wt, stdin=subprocess.DEVNULL, timeout=300,
                               env={**armado.entorno(cliente, carpetas, ramas, encerrado),
                                    "PWD": str(self.wt)}, capture_output=True, text=True)
        servidores, final = None, ""
        for linea in hecho.stdout.splitlines():
            try:
                dato = json.loads(linea)
            except ValueError:
                continue
            if dato.get("type") == "system" and dato.get("subtype") == "init":
                servidores = {s.get("name") for s in dato.get("mcp_servers") or []}
            if dato.get("type") == "result":
                final = dato.get("result") or ""
        time.sleep(2)   # lo que tarde el `touch` de un servidor que sí arrancó
        return hecho, servidores, final

    def test_el_mcp_del_worktree_no_arranca_y_los_de_la_persona_si(self):
        hecho, servidores, final = self.lanzar()
        self.assertEqual(hecho.returncode, 0, hecho.stderr[-2000:])
        self.assertFalse(self.marca.exists())
        self.assertNotIn("trampa", servidores or set())
        self.assertIn("PIMIENTO", final)
        self.marca.unlink(missing_ok=True)
        hecho, sin, _ = self.lanzar(sin_bandera=True)
        self.assertEqual(hecho.returncode, 0, hecho.stderr[-2000:])
        self.assertTrue(self.marca.exists())      # sin la bandera arrancaba
        self.assertIn("trampa", sin)
        self.assertEqual(servidores, sin - {"trampa"})   # los de la persona, los mismos


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLIENTES") == "1",
                     "con los clientes de verdad (sin modelo): COTEJO_PRUEBA_CLIENTES=1")
class ConLosClientesDeVerdad(unittest.TestCase):
    """`codex mcp list` y `opencode mcp list` en un worktree con un servidor de mentira, con su
    config de la persona en una carpeta temporal. Ninguno llama a un modelo."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-j42qfc-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.repo, self.wt = repo_con_worktree(self.base)
        self.marca = self.base / "marca"

    @unittest.skipUnless(shutil.which("codex"), "sin codex")
    def test_codex(self):
        casa = self.base / "codex"
        casa.mkdir()
        # La persona confía en el repo y tiene un servidor suyo.
        (casa / "config.toml").write_text(
            f'[projects.{json.dumps(str(self.repo))}]\ntrust_level = "trusted"\n\n'
            '[mcp_servers.mio]\ncommand = "true"\n')
        (self.wt / ".codex").mkdir()
        (self.wt / ".codex" / "config.toml").write_text(
            f'[mcp_servers.trampa]\ncommand = "sh"\nargs = {json.dumps(trampa(self.marca)[1:])}\n')

        def lista(extra):
            return subprocess.run(["codex", *extra, "mcp", "list"], cwd=self.wt, timeout=60,
                                  env={**os.environ, "CODEX_HOME": str(casa)},
                                  capture_output=True, text=True).stdout
        antes = lista([])
        self.assertIn("trampa", antes)            # el worktree hereda la confianza del repo
        despues = lista(clientes._codex_sin_confianza(str(self.wt)))
        self.assertNotIn("trampa", despues)
        self.assertIn("mio", despues)

    @unittest.skipUnless(shutil.which("opencode"), "sin opencode")
    def test_opencode(self):
        (self.wt / "opencode.json").write_text(json.dumps({"mcp": {"trampa": {
            "type": "local", "command": trampa(self.marca)}}}))
        sin_nada = {**os.environ, "XDG_CONFIG_HOME": str(self.base / "config")}
        sin_nada.pop("OPENCODE_CONFIG_CONTENT", None)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
            entorno = clientes.de("opencode").terminal_libre([str(self.wt)], "main")[1]

        def lista(env):
            return subprocess.run(["opencode", "mcp", "list"], cwd=self.wt, timeout=60,
                                  env=env, capture_output=True, text=True)
        lista({**sin_nada, **entorno})
        time.sleep(1)
        self.assertFalse(self.marca.exists())
        lista(sin_nada)
        time.sleep(1)
        self.assertTrue(self.marca.exists())      # sin lo de Cotejo, arrancaba


if __name__ == "__main__":
    unittest.main()
