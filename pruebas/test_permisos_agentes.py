"""El agente del inicio puede escribir donde hace falta, y solo ahí (v1.3.0, cotejo-p0fybl).

En la revisión del dueño, `codex exec` corría en un sandbox de solo lectura y `cotejo init`
fallaba con `Errno 30`; OpenCode rechazaba `external_directory` al tocar la config de Cotejo, y
Gemini sin interfaz ni arranca en una carpeta que no es de confianza ni corre comandos que
pedirían confirmación. Aquí se comprueba, sin lanzar ningún cliente de verdad ni gastar:

- qué argv y qué entorno recibe cada uno de los cuatro (`Cliente.permisos`, `preparar.comando`,
  `preparar.entorno_del_agente`);
- que las carpetas son exactamente la del proyecto (o la de arriba si aún no existe), su `.git`,
  la de la config de Cotejo y la de estado (`preparar.carpetas_de_escritura`);
- y, con el prompt de inicio, que un «cliente» falso con el nombre de cada uno —lanzado por
  `preparar.lanzar` como el de verdad— recibe esos permisos y su `cotejo init` funciona.
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from apoyo import RAIZ  # noqa: F401
from enrutador import clientes, config as cfg, mismo_cotejo, preparar, procesos
from tareas import inicio, preparacion

CLIENTES = ("claude", "codex", "opencode", "gemini")

# Hace lo que haría el agente en el primer paso del prompt de inicio: `cotejo init --repo` con
# el `cotejo` del PATH (el del board), y apunta qué argv y qué entorno recibió.
CLIENTE = textwrap.dedent('''
    import json, os, re, subprocess, sys
    prompt = sys.argv[-1]
    carpeta = re.search(r"^Carpeta del proyecto: (.+)$", prompt, re.M).group(1)
    init = subprocess.run(["cotejo", "init", "--repo", carpeta], capture_output=True,
                          text=True, timeout=60)
    visto = os.path.join(os.path.dirname(carpeta), "visto.json")
    with open(visto, "w") as f:
        json.dump({"argv": sys.argv[1:], "codigo": init.returncode,
                   "salida": init.stdout + init.stderr,
                   "entorno": {k: os.environ.get(k) for k in (
                       "COTEJO_FUENTE", "OPENCODE_CONFIG_CONTENT",
                       "GEMINI_CLI_TRUST_WORKSPACE")}}, f)
    sys.exit(init.returncode)
''')


class Base(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.estado = self.base / "estado"
        self.config_json = self.base / "config" / "cotejo" / "config.json"
        self.proyectos = self.base / "proyectos"
        self.proyectos.mkdir()
        self.carpeta = self.proyectos / "turnos"
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.estado),
                                              "COTEJO_CONFIG": str(self.config_json)})
        parche.start()
        self.addCleanup(parche.stop)
        os.environ.pop("OPENCODE_CONFIG_CONTENT", None)
        parche = mock.patch.object(preparacion, "CARPETA", self.estado / "preparaciones")
        parche.start()
        self.addCleanup(parche.stop)


class Carpetas(Base):

    def test_proyecto_que_no_existe_la_de_arriba_la_config_y_el_estado(self):
        carpetas = preparar.carpetas_de_escritura(str(self.carpeta))
        self.assertEqual(carpetas, [str(self.proyectos), str(self.config_json.parent),
                                    str(self.estado)])
        # La de la config se crea: un permiso sobre algo que no existe no sirve.
        self.assertTrue(self.config_json.parent.is_dir())
        # Nada del home ni de la raíz: solo lo de esta prueba.
        self.assertTrue(all(c.startswith(str(self.base)) for c in carpetas))

    def test_proyecto_con_git_tambien_su_git(self):
        (self.carpeta / ".git").mkdir(parents=True)
        self.assertEqual(preparar.carpetas_de_escritura(str(self.carpeta))[:2],
                         [str(self.carpeta), str(self.carpeta / ".git")])

    def test_sin_repetir_cuando_la_config_vive_en_el_estado(self):
        # Como `cotejo-dev`: COTEJO_CONFIG dentro de la carpeta de estado.
        os.environ["COTEJO_CONFIG"] = str(self.estado / "config.json")
        carpetas = preparar.carpetas_de_escritura(str(self.carpeta))
        self.assertEqual(carpetas, [str(self.proyectos), str(self.estado)])


class Permisos(unittest.TestCase):

    CARPETAS = ["/p/turnos", "/p/turnos/.git", "/c/cotejo", "/e/estado"]

    def test_codex_workspace_write_y_una_add_dir_por_carpeta(self):
        argv, entorno = clientes.de("codex").permisos(self.CARPETAS)
        self.assertEqual(argv, ["--sandbox", "workspace-write", "--skip-git-repo-check",
                                "--add-dir", "/p/turnos", "--add-dir", "/p/turnos/.git",
                                "--add-dir", "/c/cotejo", "--add-dir", "/e/estado"])
        self.assertEqual(entorno, {})
        self.assertNotIn("danger-full-access", argv)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)

    def test_codex_en_terminal_sin_la_bandera_que_solo_tiene_exec(self):
        argv, _ = clientes.de("codex").permisos(self.CARPETAS, interactivo=True)
        self.assertEqual(argv[:2], ["--sandbox", "workspace-write"])
        self.assertNotIn("--skip-git-repo-check", argv)

    def test_opencode_external_directory_solo_para_esas_carpetas(self):
        argv, entorno = clientes.de("opencode").permisos(self.CARPETAS, entorno={})
        self.assertEqual(argv, [])
        externo = json.loads(entorno["OPENCODE_CONFIG_CONTENT"])["permission"][
            "external_directory"]
        esperado = {}
        for c in self.CARPETAS:
            esperado[c] = "allow"
            esperado[c + "/*"] = "allow"
        self.assertEqual(externo, esperado)
        self.assertNotIn("*", externo)  # nada de «todo permitido»

    def test_opencode_se_funde_con_lo_que_ya_traia_la_variable(self):
        previo = json.dumps({"model": "x/y", "permission": {
            "bash": "allow", "external_directory": {"/otra/*": "deny"}}})
        _, entorno = clientes.de("opencode").permisos(
            ["/p"], entorno={"OPENCODE_CONFIG_CONTENT": previo})
        datos = json.loads(entorno["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(datos["model"], "x/y")
        self.assertEqual(datos["permission"]["bash"], "allow")
        self.assertEqual(datos["permission"]["external_directory"],
                         {"/otra/*": "deny", "/p": "allow", "/p/*": "allow"})
        # Un valor suelto queda como regla general, y un JSON roto se descarta.
        _, entorno = clientes.de("opencode").permisos(["/p"], entorno={
            "OPENCODE_CONFIG_CONTENT": json.dumps({"permission": {"external_directory": "ask"}})})
        self.assertEqual(json.loads(entorno["OPENCODE_CONFIG_CONTENT"])["permission"][
            "external_directory"], {"*": "ask", "/p": "allow", "/p/*": "allow"})
        _, entorno = clientes.de("opencode").permisos(
            ["/p"], entorno={"OPENCODE_CONFIG_CONTENT": "{roto"})
        self.assertEqual(json.loads(entorno["OPENCODE_CONFIG_CONTENT"]),
                         {"permission": {"external_directory": {"/p": "allow", "/p/*": "allow"}}})

    def test_gemini_confia_en_la_carpeta_solo_esta_sesion(self):
        self.assertEqual(clientes.de("gemini").permisos(self.CARPETAS),
                         ([], {"GEMINI_CLI_TRUST_WORKSPACE": "true"}))

    def test_claude_no_necesita_nada(self):
        self.assertEqual(clientes.de("claude").permisos(self.CARPETAS), ([], {}))


class Comando(Base):

    def config(self):
        return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})

    def test_el_argv_de_cada_cliente_con_la_carpeta(self):
        carpetas = preparar.carpetas_de_escritura(str(self.carpeta))
        add = [x for c in carpetas for x in ("--add-dir", c)]
        esperado = {
            "claude": ["claude", "-p", "--allowedTools", "Bash(cotejo:*)", "--", "P"],
            "codex": ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
                      *add, "P"],
            "opencode": ["opencode", "run", "P"],
            "gemini": ["gemini", "--allowed-tools", "run_shell_command(cotejo)", "-p", "P"],
        }
        for nombre in CLIENTES:
            with self.subTest(nombre):
                self.assertEqual(preparar.comando(self.config(), clientes.de(nombre), "", "P",
                                                  carpeta=str(self.carpeta)), esperado[nombre])

    def test_el_entorno_de_cada_cliente(self):
        for nombre in CLIENTES:
            with self.subTest(nombre):
                entorno = preparar.entorno_del_agente({
                    "cliente": nombre, "carpeta": str(self.carpeta),
                    "entorno": dict(inicio.ENTORNO)})
                self.assertEqual(entorno["COTEJO_FUENTE"], "repo")
                self.assertEqual(entorno["PATH"].split(os.pathsep)[0],
                                 str(mismo_cotejo.carpeta()))
                self.assertEqual("OPENCODE_CONFIG_CONTENT" in entorno, nombre == "opencode")
                self.assertEqual("GEMINI_CLI_TRUST_WORKSPACE" in entorno, nombre == "gemini")


class ConElPromptDeInicio(Base):
    """`preparar.lanzar` con cada cliente, como lo lanza el board, y un ejecutable falso con su
    nombre que corre el `cotejo init` del primer paso."""

    def setUp(self):
        super().setUp()
        self.script = self.base / "cliente.py"
        self.script.write_text(CLIENTE)
        parche = mock.patch.object(preparar, "avisar_a_la_barra", lambda *_a: None)
        parche.start()
        self.addCleanup(parche.stop)
        self.hilos = []
        original = preparar.vigilar

        def vigilar(*a, **k):
            hilo = original(*a, **k)
            self.hilos.append(hilo)
            return hilo
        parche = mock.patch.object(preparar, "vigilar", vigilar)
        parche.start()
        self.addCleanup(parche.stop)
        self.addCleanup(self._limpiar)
        falso = [sys.executable, str(self.script)]
        self.config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {
            "motores": {"headless": {"comando": falso, "aislar": False, "timeout_seg": 60,
                                     "clientes": {n: {"comando": falso} for n in CLIENTES}}},
            "maestro": {"modelos": {}},
        })

    def _limpiar(self):
        for registro in preparacion.todas():
            if registro.get("fase") == "lanzado":
                procesos.terminar(registro.get("pid"), registro.get("programa", ""))
        for hilo in self.hilos:
            hilo.join(30)

    def test_los_cuatro_reciben_sus_permisos_y_init_funciona(self):
        for nombre in CLIENTES:
            with self.subTest(nombre):
                carpeta = self.proyectos / nombre / "turnos"
                carpeta.parent.mkdir()
                r = inicio.Respuestas(que_es="Una app de turnos", que_hace="Reservar",
                                      carpeta=str(carpeta))
                salida = preparar.lanzar(r, cliente=nombre, config=self.config)
                self.hilos[-1].join(60)
                visto = json.loads((carpeta.parent / "visto.json").read_text())
                self.assertEqual(visto["codigo"], 0, visto["salida"])
                self.assertTrue((carpeta / ".cotejo" / "tareas.md").is_file())
                self.assertIn(str(carpeta), self.config_json.read_text())
                self.assertEqual(visto["entorno"]["COTEJO_FUENTE"], "repo")
                argv = visto["argv"]
                self.assertEqual(argv[-1], preparacion.leer(salida["id"])["prompt"])
                carpetas = [str(carpeta.parent), str(self.config_json.parent), str(self.estado)]
                if nombre == "codex":
                    self.assertEqual(argv[:4], ["exec", "--sandbox", "workspace-write",
                                                "--skip-git-repo-check"])
                    self.assertEqual([argv[i + 1] for i, a in enumerate(argv)
                                      if a == "--add-dir"], carpetas)
                else:
                    self.assertNotIn("--sandbox", argv)
                if nombre == "opencode":
                    externo = json.loads(visto["entorno"]["OPENCODE_CONFIG_CONTENT"])[
                        "permission"]["external_directory"]
                    self.assertEqual(sorted(externo), sorted(
                        [c for d in carpetas for c in (d, d + "/*")]))
                else:
                    self.assertIsNone(visto["entorno"]["OPENCODE_CONFIG_CONTENT"])
                self.assertEqual(visto["entorno"]["GEMINI_CLI_TRUST_WORKSPACE"],
                                 "true" if nombre == "gemini" else None)
                if nombre == "gemini":
                    self.assertIn("run_shell_command(cotejo)", argv)
                if nombre == "claude":
                    self.assertIn("Bash(cotejo:*)", argv)

    def test_reintentar_pone_al_dia_el_git_que_dejo_el_primer_intento(self):
        r = inicio.Respuestas(que_es="Una app de turnos", que_hace="Reservar",
                              carpeta=str(self.carpeta))
        salida = preparar.lanzar(r, cliente="codex", config=self.config)
        self.hilos[-1].join(60)
        self.assertNotIn(str(self.carpeta / ".git"), preparacion.leer(salida["id"])["comando"])
        preparar.reintentar(salida["id"], config=self.config)
        self.hilos[-1].join(60)
        comando = preparacion.leer(salida["id"])["comando"]
        self.assertIn(str(self.carpeta), comando)
        self.assertIn(str(self.carpeta / ".git"), comando)
        self.assertEqual(comando[-1], preparacion.leer(salida["id"])["prompt"])


if __name__ == "__main__":
    unittest.main()
