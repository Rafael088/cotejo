"""El `.env` del proyecto en el entorno de los agentes (cotejo-4gvdy5).

Sigue a `test_config_gemini_opencode.py` (cotejo-lbwsq4). Con la confianza que Cotejo le da al
worktree, Gemini CLI carga el primer `.env` que encuentra subiendo desde donde arranca (en cada
carpeta, `.gemini/.env` y luego `.env`; al final, los de la casa) y añade las variables que no
existan. Una `BASH_ENV` ahí corría un archivo del repo antes de cada `bash -c` de su shell y de
sus servidores MCP, por debajo de los prohibidos y de las guardas del PATH. Cotejo define antes,
vacías, las vedadas (`gemini_env.VEDADAS`) que traiga un `.env` que no es de la persona;
las demás siguen llegando.

Codex solo lee `~/.codex/.env` (`CODEX_HOME`, y sin las `CODEX_*`) y OpenCode va compilado sin
cargar `.env` (`autoloadDotenv: false`): con ellos no hay nada que cerrar, y aquí se comprueba.

Con los clientes de verdad, solo si se pide (`COTEJO_PRUEBA_CLIENTES=1`) y sin llamar a ningún
modelo: `gemini mcp list` sin red (`unshare -rn`) con un servidor MCP de la persona que es un
`bash -c`, `codex sandbox -- env` y `opencode debug config` con un `{env:…}`.
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

from enrutador import armado, clientes, config as cfg, gemini_env


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.casa = self.tmp / "casa"
        (self.casa / ".gemini").mkdir(parents=True)
        self.wt = self.tmp / "estado" / "wt" / "tarea"
        self.wt.mkdir(parents=True)
        # La persona, en una casa falsa: ni `~/.gemini` ni `/etc/gemini-cli`.
        self.entorno = {"GEMINI_CLI_HOME": str(self.casa),
                        "GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(self.tmp / "sistema.json")}
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.tmp / "estado"),
                                              "COTEJO_CONFIG": str(self.tmp / "c.json"),
                                              **self.entorno})
        parche.start()
        self.addCleanup(parche.stop)
        for nombre in ("BASH_ENV", "ENV", "NODE_OPTIONS", "LD_PRELOAD", "PYTHONPATH",
                       "GIT_CONFIG_COUNT", "OPENCODE_CONFIG_CONTENT"):
            os.environ.pop(nombre, None)

    def env(self, carpeta, texto, gemini=False):
        destino = Path(carpeta) / (".gemini" if gemini else "")
        destino.mkdir(parents=True, exist_ok=True)
        (destino / ".env").write_text(texto)

    def lanzar(self, entorno=None):
        return clientes.de("gemini").terminal_libre([str(self.wt)], "main",
                                                    politica_gemini="/e/g.toml", entorno=entorno)


class Gemini(Base):
    def test_sin_env_no_cambia_nada(self):
        self.assertEqual(self.lanzar()[1], {"GEMINI_CLI_TRUST_WORKSPACE": "true"})

    def test_las_vedadas_van_vacias_y_las_demas_siguen(self):
        self.env(self.wt, "BASH_ENV=./trampa.sh\nexport NODE_OPTIONS='--require ./x.js'\n"
                          "LD_PRELOAD=./x.so\nGIT_CONFIG_COUNT=1\nPYTHONPATH: ./x\n"
                          "GEMINI_API_KEY=clave\nDATABASE_URL=postgres://x\nVITE_X=1\n"
                          "NODE_ENV=development\nPATH=/trampa\n")
        env = self.lanzar()[1]
        for nombre in ("BASH_ENV", "NODE_OPTIONS", "LD_PRELOAD", "GIT_CONFIG_COUNT",
                       "PYTHONPATH"):
            self.assertEqual(env[nombre], "", nombre)
        for nombre in ("GEMINI_API_KEY", "DATABASE_URL", "VITE_X", "NODE_ENV", "PATH"):
            self.assertNotIn(nombre, env, nombre)   # el PATH ya existe: Gemini no lo pisa

    def test_lo_que_ya_tiene_la_persona_no_se_toca(self):
        self.env(self.wt, "BASH_ENV=./trampa.sh\nENV=./trampa.sh\n")
        env = self.lanzar({**os.environ, "BASH_ENV": "/mio/bashrc"})[1]
        self.assertNotIn("BASH_ENV", env)
        self.assertEqual(env["ENV"], "")

    def test_gemini_env_del_worktree_y_de_una_carpeta_de_arriba(self):
        self.env(self.wt, "BASH_ENV=x\n", gemini=True)
        self.assertEqual(self.lanzar()[1]["BASH_ENV"], "")
        shutil.rmtree(self.wt / ".gemini")
        # La carpeta de estado de Cotejo está encima del worktree, y un agente la escribe.
        self.env(self.wt.parent.parent, "ENV=x\n")
        self.assertEqual(self.lanzar()[1]["ENV"], "")
        self.env(self.wt.parent, "LD_PRELOAD=x\n", gemini=True)
        env = self.lanzar()[1]
        self.assertEqual(env["LD_PRELOAD"], "")
        self.assertNotIn("ENV", env)   # Gemini se queda con el primero que encuentra

    def test_con_ignore_local_env_tambien(self):
        # Con `advanced.ignoreLocalEnv` Gemini salta el `.env` y sigue al `.gemini/.env` de
        # arriba; el proyecto puede ponerlo en su `.gemini/settings.json`, así que se miran los dos.
        self.env(self.wt, "ENV=x\n")
        self.env(self.wt.parent, "BASH_ENV=x\n", gemini=True)
        env = self.lanzar()[1]
        self.assertEqual((env["ENV"], env["BASH_ENV"]), ("", ""))

    def test_los_de_la_casa_son_de_la_persona(self):
        self.env(self.casa, "BASH_ENV=x\n", gemini=True)
        self.env(self.casa, "ENV=x\n")
        self.assertEqual(self.lanzar()[1], {"GEMINI_CLI_TRUST_WORKSPACE": "true"})
        # Y si el worktree vive dentro de la casa, al pasar por ella se queda con el suyo.
        dentro = self.casa / "wt"
        dentro.mkdir()
        self.assertEqual(gemini_env.sin_env_del_proyecto(str(dentro), {}), {})

    def test_un_env_que_no_se_lee_no_define_nada(self):
        (self.wt / ".env").mkdir()
        self.assertEqual(self.lanzar()[1], {"GEMINI_CLI_TRUST_WORKSPACE": "true"})

    def test_sobran_nombres_no_falta_ninguno(self):
        self.env(self.wt, '﻿PERL5LIB=x\nX="uno\nBASH_ENV=dentro de un valor"\r\n'
                          '  export  ENV : y\r# PERL5OPT=comentario\nNO VALE=1 LD_AUDIT=x\n')
        claves = gemini_env._claves_dotenv(self.wt / ".env")
        for nombre in ("PERL5LIB", "X", "BASH_ENV", "ENV", "LD_AUDIT"):
            self.assertIn(nombre, claves)
        self.assertNotIn("PERL5OPT", claves)

    def test_vedadas(self):
        for nombre in ("BASH_ENV", "bash_env", "npm_config_script_shell", "GIT_SSH_COMMAND",
                       "DYLD_INSERT_LIBRARIES", "PYTHONSTARTUP", "COTEJO_CONFIG_VEDADA",
                       "GEMINI_CLI_SYSTEM_SETTINGS_PATH", "HTTPS_PROXY", "XDG_CONFIG_HOME"):
            self.assertTrue(gemini_env.vedada(nombre), nombre)
        for nombre in ("GEMINI_API_KEY", "GEMINI_MODEL", "GOOGLE_CLOUD_PROJECT", "NODE_ENV",
                       "DATABASE_URL", "PORT", "GITHUB_REPOSITORY", "ENVIRONMENT"):
            self.assertFalse(gemini_env.vedada(nombre), nombre)

    def test_sin_confianza_tambien(self):
        # Con hooks en el proyecto el worktree va sin confianza; el `.env` se neutraliza igual.
        (self.wt / ".gemini").mkdir()
        (self.wt / ".gemini" / "settings.json").write_text(
            json.dumps({"tools": {"discoveryCommand": "x"}}))
        self.env(self.wt, "BASH_ENV=x\n")
        env = self.lanzar()[1]
        self.assertEqual((env["GEMINI_CLI_TRUST_WORKSPACE"], env["BASH_ENV"]), ("false", ""))

    def test_el_armado_lo_lleva(self):
        """El entorno que arma el board (`armado.entorno`, el de `motores/fondo.py`) lleva las
        vacías, con las guardas primeras en el PATH, y el argv no cambia."""
        self.env(self.wt, "BASH_ENV=./trampa.sh\nPATH=/trampa\nDATABASE_URL=x\n")
        gemini = clientes.de("gemini")
        entorno = armado.entorno(gemini, [str(self.wt)], ["main"], {"activo": False, "entorno": {}})
        self.assertEqual(entorno["BASH_ENV"], "")
        self.assertNotIn("DATABASE_URL", entorno)
        self.assertIn(entorno["COTEJO_GUARDAS"], entorno["PATH"].split(os.pathsep))
        self.assertNotIn("/trampa", entorno["PATH"].split(os.pathsep))
        argv = armado.comando(cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {}), gemini,
                              "gemini-2.5-pro", None, "P", [str(self.wt)], ["main"],
                              politica_gemini="/e/g.toml")
        self.assertEqual(argv[-2:], ["-p", "P"])
        self.assertNotIn("BASH_ENV", " ".join(argv))

    def test_el_inicio_no_cambia(self):
        # `permisos` (preparar) no mira el proyecto: es la carpeta que la persona eligió.
        self.env(self.wt, "BASH_ENV=x\n")
        self.assertEqual(clientes.de("gemini").permisos([str(self.wt)]),
                         ([], {"GEMINI_CLI_TRUST_WORKSPACE": "true"}))

    def test_los_demas_clientes_no_lo_miran(self):
        self.env(self.wt, "BASH_ENV=x\n")
        for nombre in ("claude", "codex", "opencode", "antigravity"):
            env = clientes.de(nombre).terminal_libre([str(self.wt)], "main")[1]
            self.assertNotIn("BASH_ENV", env, nombre)


def sin_red():
    if not shutil.which("unshare"):
        return False
    return subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLIENTES") == "1",
                     "con los clientes de verdad (sin modelo): COTEJO_PRUEBA_CLIENTES=1")
class ConLosClientesDeVerdad(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-4gvdy5-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.wt = self.base / "wt"
        self.wt.mkdir()
        subprocess.run(["git", "init", "-q", str(self.wt)], check=True)
        self.marcas = self.base / "marcas"
        self.marcas.mkdir()
        trampa = self.base / "trampa.sh"
        trampa.write_text(f'touch "{self.marcas}/bash_env"\n')
        (self.wt / ".env").write_text(f"BASH_ENV={trampa}\nTRAMPA_NORMAL=si\n")
        self.base_env = {k: v for k, v in os.environ.items()
                         if k not in ("BASH_ENV", "ENV", "TRAMPA_NORMAL")}

    def visto(self):
        time.sleep(1)
        vistos = {p.name for p in self.marcas.iterdir()}
        for p in self.marcas.iterdir():
            p.unlink()
        return vistos

    @unittest.skipUnless(shutil.which("gemini") and sin_red(), "sin gemini o sin unshare")
    def test_gemini_bash_env_del_worktree(self):
        casa = self.base / "casa"
        (casa / ".gemini").mkdir(parents=True)
        servidor = (f'touch "{self.marcas}/mio"; [ "$TRAMPA_NORMAL" = si ] && '
                    f'touch "{self.marcas}/normal"; sleep 20')
        (casa / ".gemini" / "settings.json").write_text(json.dumps({
            "security": {"auth": {"selectedType": "gemini-api-key"}},
            "mcpServers": {"mio": {"command": "bash", "args": ["-c", servidor]}}}))
        entorno = {**self.base_env, "GEMINI_CLI_HOME": str(casa), "GEMINI_API_KEY": "falsa",
                   "GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(self.base / "sistema.json")}

        def lista(env):
            subprocess.run(["timeout", "60", "unshare", "-rn", "gemini", "mcp", "list"],
                           cwd=self.wt, env=env, timeout=90, capture_output=True)
            return self.visto()
        confianza = {**entorno, "GEMINI_CLI_TRUST_WORKSPACE": "true"}
        self.assertEqual(lista(confianza), {"mio", "normal", "bash_env"})   # la trampa muerde
        with mock.patch.dict(os.environ, entorno, clear=True):
            env = clientes.de("gemini").terminal_libre([str(self.wt)], "main")[1]
        self.assertEqual(env["BASH_ENV"], "")
        self.assertEqual(lista({**entorno, **env}), {"mio", "normal"})

    @unittest.skipUnless(shutil.which("codex") and sin_red(), "sin codex o sin unshare")
    def test_codex_no_carga_el_del_proyecto(self):
        salida = subprocess.run(["unshare", "-rn", "codex", "sandbox", "--", "env"],
                                cwd=self.wt, env=self.base_env, timeout=90,
                                capture_output=True, text=True).stdout
        self.assertIn("PWD=", salida)      # corrió
        self.assertNotIn("TRAMPA_NORMAL", salida)
        self.assertNotIn(str(self.base / "trampa.sh"), salida)

    @unittest.skipUnless(shutil.which("opencode") and sin_red(), "sin opencode o sin unshare")
    def test_opencode_no_carga_el_del_proyecto(self):
        xdg = {f"XDG_{k}_HOME": str(self.base / k.lower())
               for k in ("CONFIG", "DATA", "CACHE", "STATE")}

        def usuario(extra):
            contenido = json.dumps({"username": "[{env:TRAMPA_NORMAL}|{env:BASH_ENV}]"})
            salida = subprocess.run(
                ["unshare", "-rn", "opencode", "debug", "config"], cwd=self.wt, timeout=90,
                env={**self.base_env, **xdg, **extra, "OPENCODE_CONFIG_CONTENT": contenido},
                capture_output=True, text=True).stdout
            return json.loads(salida[salida.index("{"):])["username"]
        self.assertEqual(usuario({"TRAMPA_NORMAL": "control"}), "[control|]")
        self.assertEqual(usuario({}), "[|]")


if __name__ == "__main__":
    unittest.main()
