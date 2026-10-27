"""La config de Cotejo fuera del alcance del agente de una tarea (cotejo-dgb7l2, encima de
cotejo-amui0f y dec-kiik).

En la config viven `lanzar.sandbox` y `lanzar.argumentos_extra`: el agente que la escribiera le
quitaría el sandbox y los prohibidos a los lanzamientos siguientes. Tres capas, y cada una se
prueba sola:

- **la guarda**: con `COTEJO_CONFIG_VEDADA` en el entorno, `cotejo` no escribe la config y lo
  dice en llano (`configuracion.sin_vedar`);
- **las carpetas**: la de la config no está entre las del agente (en macOS, donde la de estado
  cuelga de ella, se da solo la de estado), y sus archivos van vedados en el sandbox de Claude y
  en sus herramientas de editar;
- **la jaula de verdad**: en bubblewrap con las reglas del sandbox, los verbos que usa el agente
  durante una tarea funcionan, y escribir la config falla por la guarda, sin ella, y aunque una
  carpeta de escritura la contenga. Se salta sin bwrap.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "pruebas"))

from enrutador import armado, clientes, config as cfg, sandbox  # noqa: E402
from tareas import cli, configuracion, rutas  # noqa: E402
from test_navegador_sandbox import BWRAP, bwrap_como_claude, filtro_sin_sockets_unix  # noqa: E402

ORIGINAL = {"fuente": "repo", "fuentes": {"repo": {"repos": []}}, "lanzar": {"sandbox": {}}}


class ConConfig(unittest.TestCase):
    """Una config de verdad en una carpeta temporal, por `COTEJO_CONFIG`."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.base = Path(temporal.name)
        self.config = self.base / "config" / "cotejo" / "config.json"
        self.config.parent.mkdir(parents=True)
        self.texto = json.dumps(ORIGINAL, indent=2) + "\n"
        self.config.write_text(self.texto, encoding="utf-8")
        entorno = mock.patch.dict(os.environ, {"COTEJO_CONFIG": str(self.config),
                                               "XDG_CONFIG_HOME": str(self.base / "config")})
        entorno.start()
        self.addCleanup(entorno.stop)
        os.environ.pop(configuracion.VEDADA, None)

    def vedar(self):
        os.environ[configuracion.VEDADA] = "1"


class Guarda(ConConfig):
    def test_sin_marca_se_escribe_como_siempre(self):
        configuracion.guardar({**ORIGINAL, "tema": "claro"})
        self.assertEqual(json.loads(self.config.read_text())["tema"], "claro")

    def test_con_marca_no_se_escribe_nada(self):
        self.vedar()
        with self.assertRaises(configuracion.ConfigVedada):
            configuracion.guardar({**ORIGINAL, "lanzar": {"sandbox": False}})
        self.assertEqual(self.config.read_text(), self.texto)
        self.assertEqual(sorted(p.name for p in self.config.parent.iterdir()), ["config.json"])

    def test_el_catalogo_de_modelos_tampoco(self):
        self.vedar()
        with self.assertRaises(configuracion.ConfigVedada):
            cfg.guardar_modelos([], self.config)
        self.assertEqual(self.config.read_text(), self.texto)

    def test_la_cli_lo_dice_en_llano_y_sale_con_3(self):
        self.vedar()
        salida = mock.patch("sys.stdout", new_callable=__import__("io").StringIO)
        with salida as texto:
            codigo = cli.main(["temas", "usar", "claro"])
        datos = json.loads(texto.getvalue())
        self.assertEqual(codigo, 3)
        self.assertIn("no se cambia desde una tarea", datos["error"])
        self.assertFalse(datos["reintentable"])
        self.assertEqual(self.config.read_text(), self.texto)

    def test_leerla_sigue_valiendo(self):
        self.vedar()
        self.assertEqual(configuracion.cargar(), ORIGINAL)

    def test_archivos_son_todos_los_que_podrian_mandar(self):
        archivos = configuracion.archivos()
        self.assertEqual(archivos[0], os.path.abspath(self.config))
        for otro in (configuracion.nueva(), configuracion.legado(),
                     self.base / "config" / "foco" / "config.json"):
            self.assertIn(os.path.abspath(otro), archivos)
        self.assertEqual(len(archivos), len(set(archivos)))


class Armado(ConConfig):
    def test_la_carpeta_de_la_config_no_es_del_agente(self):
        carpetas = armado.carpetas_de_escritura(self.base / "trabajo")
        self.assertNotIn(os.path.abspath(self.config.parent), carpetas)
        self.assertIn(str(Path(os.path.abspath(rutas.estado()))), carpetas)

    def test_en_macos_se_da_la_de_estado_sin_la_de_config(self):
        estado = self.config.parent / "estado"
        with mock.patch.object(rutas, "estado", return_value=estado):
            carpetas = armado.carpetas_de_escritura(self.base / "trabajo")
        self.assertIn(os.path.abspath(estado), carpetas)
        self.assertNotIn(os.path.abspath(self.config.parent), carpetas)

    def test_preparar_si_la_tiene(self):
        # `init`, en el inicio de un proyecto, registra el repo en la config.
        from enrutador import preparar
        self.assertIn(os.path.abspath(self.config.parent),
                      preparar.carpetas_de_escritura(self.base / "trabajo"))

    def test_el_sandbox_veda_los_archivos(self):
        cotejo = mock.Mock()
        cotejo.carpeta_de_la_tarea.return_value = None
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})
        with mock.patch.object(sandbox, "disponible", return_value=(True, "")):
            hecho = armado.sandbox_de(config, clientes.de("claude"), cotejo, "cotejo-x",
                                      self.base / "trabajo")
        fs = hecho["ajustes"]["sandbox"]["filesystem"]
        self.assertIn(os.path.abspath(self.config), fs["denyWrite"])
        self.assertNotIn(os.path.abspath(self.config.parent), fs["allowWrite"])

    def test_lo_vedado_gana_a_una_carpeta_de_la_config_de_la_persona(self):
        hecho = sandbox.del_lanzamiento(["/w"], ajustes={"escritura": [str(self.base)]},
                                        vedadas=armado.vedados(), token=None)
        fs = hecho["ajustes"]["sandbox"]["filesystem"]
        self.assertIn(str(self.base), fs["allowWrite"])
        self.assertIn(os.path.abspath(self.config), fs["denyWrite"])

    def test_claude_no_la_edita_con_sus_herramientas(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})
        argv = armado.comando(config, clientes.de("claude"), "sonnet", None, "P", ["/w"],
                              ["main"])
        self.assertIn(f"Edit(/{os.path.abspath(self.config)})", argv)
        despues = argv[argv.index("--disallowedTools"):]
        self.assertIn("Bash(sudo *)", despues)   # los prohibidos siguen

    def test_el_entorno_del_agente_lleva_la_marca(self):
        encerrado = {"activo": False, "entorno": {}}
        for nombre in ("claude", "codex", "opencode", "gemini"):
            with self.subTest(nombre), mock.patch.dict(os.environ, {"COTEJO_ESTADO":
                                                                    str(self.base / "e")}):
                entorno = armado.entorno(clientes.de(nombre), ["/w"], ["main"], encerrado)
                self.assertEqual(entorno.get(configuracion.VEDADA), "1")

    def test_la_ruta_de_un_permiso(self):
        self.assertEqual(clientes._ruta_de_permiso("/a/b.json"), "//a/b.json")
        self.assertEqual(clientes._ruta_de_permiso(".claude/x.json"), ".claude/x.json")


@unittest.skipUnless(BWRAP and filtro_sin_sockets_unix(), "sin bwrap o sin filtro")
class EnLaJaula(unittest.TestCase):
    """Los verbos de verdad, en bubblewrap con las reglas que arma el lanzamiento."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-dgb7l2-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.config = self.base / "config" / "cotejo" / "config.json"
        self.config.parent.mkdir(parents=True)
        self.estado = self.base / "estado"
        self.repo = self.base / "repo"
        self.tmp = self.base / "tmp"
        for carpeta in (self.estado, self.repo / ".cotejo", self.tmp):
            carpeta.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".cotejo" / "tareas.md").write_text(
            "# Tareas\n\n- [ ] Hacer la prueba #agente/opus #en-curso ^cotejo-abc123\n",
            encoding="utf-8")
        self.texto = json.dumps({**ORIGINAL, "fuentes": {"repo": {"repos": [str(self.repo)]}}},
                                indent=2) + "\n"
        self.config.write_text(self.texto, encoding="utf-8")
        self.entorno = {**os.environ, "PYTHONPATH": str(RAIZ), "HOME": str(self.base),
                        "COTEJO_CONFIG": str(self.config), "COTEJO_ESTADO": str(self.estado),
                        "XDG_CONFIG_HOME": str(self.base / "config"), configuracion.VEDADA: "1"}

    def ajustes(self, extra=()):
        with mock.patch.dict(os.environ, {k: self.entorno[k] for k in
                                          ("COTEJO_CONFIG", "COTEJO_ESTADO", "XDG_CONFIG_HOME")}):
            carpetas = armado.carpetas_de_escritura(self.repo)
            return sandbox.del_lanzamiento(carpetas, carpeta_tarea=str(self.repo / ".cotejo"),
                                           ajustes={"escritura": list(extra)},
                                           vedadas=armado.vedados(), token=None)["ajustes"]

    def encerrar(self, script, extra=()):
        lectura, escritura = os.pipe()
        os.write(escritura, filtro_sin_sockets_unix())
        os.close(escritura)
        try:
            argv = bwrap_como_claude(self.ajustes(extra), str(self.tmp), lectura)
            argv += ["--chdir", str(self.repo), "--", "/bin/bash", "-c", script]
            return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=120, pass_fds=(lectura,), env=self.entorno)
        finally:
            os.close(lectura)

    def cotejo(self, *args, extra=()):
        import shlex
        return self.encerrar(shlex.join([sys.executable, "-m", "tareas", *args]), extra)

    def test_los_verbos_de_una_tarea_funcionan(self):
        for args in (["contexto"], ["tareas", "--proyecto", "repo"],
                     ["bitacora", "una nota del agente"],
                     ["crear", "Otra cosa que apareció", "--proyecto", "repo"],
                     ["entregar", "cotejo-abc123", "--evidencia", "hecho", "--resumen", "algo"]):
            with self.subTest(args[0]):
                hecho = self.cotejo(*args)
                self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        self.assertEqual(self.config.read_text(), self.texto)

    def test_cotejo_no_la_escribe(self):
        hecho = self.cotejo("temas", "usar", "claro")
        self.assertEqual(hecho.returncode, 3)
        self.assertIn("no se cambia desde una tarea", hecho.stdout)
        self.assertEqual(self.config.read_text(), self.texto)

    def test_sin_la_marca_la_para_el_sandbox(self):
        for extra in ((), (str(self.base),)):   # y con una carpeta que la contiene
            with self.subTest(extra=extra):
                for script in (
                        f"env -u {configuracion.VEDADA} {sys.executable} -m tareas temas usar claro",
                        f"echo '{{\"lanzar\": {{\"sandbox\": false}}}}' > {self.config}",
                        f"echo '{{}}' > {self.estado}/x.json && mv -f {self.estado}/x.json "
                        f"{self.config}",
                        f"rm -f {self.config}"):
                    hecho = self.encerrar(script, extra)
                    self.assertNotEqual(hecho.returncode, 0, script)
                self.assertEqual(self.config.read_text(), self.texto)

    def test_la_jaula_muerde(self):
        # Para que el verde no salga de una jaula floja: lo suyo sí se escribe.
        hecho = self.encerrar(f"echo x > {self.repo}/nuevo && echo x > {self.estado}/nuevo")
        self.assertEqual(hecho.returncode, 0, hecho.stderr)


if __name__ == "__main__":
    unittest.main()
