"""Antigravity CLI (`agy`) como cliente de Cotejo (v1.3.0, cotejo-r4yg0n).

Desde el 18-jun-2026 Google manda al plan gratuito, Pro y Ultra a Antigravity CLI en vez de
Gemini CLI. Aquí se comprueba, sin lanzar el `agy` de verdad (los CLIs son scripts falsos en un
PATH temporal o `Popen` simulado), que Cotejo le habla con las banderas que documenta
https://antigravity.google/docs/cli/reference y …/docs/cli/headless:

- sin interfaz `agy --print-timeout 0 [--model <slug>] … -p <prompt>`; en una terminal
  `agy [--model <slug>] … -i <prompt>`;
- sus carpetas con `--add-dir` y sus comandos aprobados con `--dangerously-skip-permissions`
  (preparar y la terminal libre del board), sin su `--sandbox` por defecto;
- `agy models` como su lista de modelos y la sesión que solo se ve por entorno.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import armado, clientes, config as cfg, maestro, modelos_vivos, niveles, preparar, sandbox
from enrutador import motor
from enrutador.motores import claude_cli

# La salida de `agy models` tal como la enseña https://antigravity.google/docs/cli/headless.
MODELOS = """#!/bin/sh
[ "$1" = "models" ] || exit 3
echo "gemini-4-argon-high       Gemini 4 Argon (High)"
echo "gemini-3.8-flash-medium   Gemini 3.8 Flash (Medium)"
echo "gemini-3.1-pro-high       Gemini 3.1 Pro (High)"
echo "..."
"""


def config(encima=None):
    return cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), encima or {})


class Argumentos(unittest.TestCase):
    CARPETAS = ["/p/wt", "/p/repo/.git", "/c/cotejo", "/e/estado"]

    def setUp(self):
        self.agy = clientes.de("antigravity")
        self.ajustes = sandbox.ajustes_claude(self.CARPETAS, ["/c/cotejo/config.json"])

    def test_se_llama_agy_y_esta_en_la_tabla(self):
        self.assertEqual((self.agy.ejecutable, self.agy.titulo), ("agy", "Antigravity CLI"))
        self.assertIn("antigravity", clientes.CLIENTES)

    def test_sin_interfaz_con_y_sin_modelo(self):
        self.assertEqual(self.agy.argv_sin_interfaz("gemini-3.8-flash-medium", "P"),
                         ["agy", "--print-timeout", "0", "--model", "gemini-3.8-flash-medium",
                          "-p", "P"])
        self.assertEqual(self.agy.argv_sin_interfaz("", "P"),
                         ["agy", "--print-timeout", "0", "-p", "P"])

    def test_en_una_terminal_sigue_la_sesion_con_i(self):
        self.assertEqual(self.agy.argv_interactivo("P", "gemini-4-argon-high"),
                         ["agy", "--model", "gemini-4-argon-high", "-i", "P"])
        self.assertEqual(maestro.argv("antigravity", "P", terminal=["t"]), ["t", "agy", "-i", "P"])

    def test_permisos_una_add_dir_por_carpeta_y_nada_por_entorno(self):
        argv, entorno = self.agy.permisos(self.CARPETAS)
        self.assertEqual(argv, [x for c in self.CARPETAS for x in ("--add-dir", c)])
        self.assertEqual(entorno, {})
        self.assertEqual(self.agy.permisos(self.CARPETAS, interactivo=True)[0], argv)

    def test_terminal_libre_aprueba_sus_comandos_sin_sandbox_ni_banderas_de_otros(self):
        argv, entorno = self.agy.terminal_libre(self.CARPETAS, ["main"])
        self.assertEqual(argv[-1], "--dangerously-skip-permissions")
        self.assertEqual(argv[:-1], self.agy.permisos(self.CARPETAS)[0])
        self.assertEqual(entorno, {})
        for ajena in ("--sandbox", "--approval-mode", "--policy", "--allowedTools",
                      "--permission-mode", "--mode"):
            self.assertNotIn(ajena, argv)

    def test_el_armado_del_board_lleva_jaula_aprobacion_y_prompt_al_final(self):
        argv = armado.comando(config(), self.agy, "antigravity", "", "Haz la tarea",
                              self.CARPETAS, ["main"], sandbox=self.ajustes)
        self.assertEqual(Path(argv[0]).name, "bwrap")
        agy = argv[argv.index("--") + 1:]
        self.assertEqual(agy[:3], ["agy", "--print-timeout", "0"])
        self.assertNotIn("--model", agy)                   # el de fábrica: el que tenga elegido
        self.assertIn("--dangerously-skip-permissions", agy)
        self.assertEqual(agy[-2:], ["-p", "Haz la tarea"])

    def test_usa_la_jaula_propia_no_el_sandbox_de_claude(self):
        cotejo = mock.Mock()
        cotejo.carpeta_de_la_tarea.return_value = None
        with mock.patch.object(sandbox, "disponible_bwrap", return_value=(True, "")):
            encerrado = armado.sandbox_de({}, self.agy, cotejo, "t1", Path("/p/wt"))
        self.assertTrue(encerrado["activo"])
        self.assertEqual(encerrado["cliente"], "antigravity")
        self.assertIn("allowWrite", encerrado["ajustes"]["sandbox"]["filesystem"])

    def test_sin_bwrap_no_se_lanza(self):
        with mock.patch.object(sandbox, "disponible_bwrap", return_value=(False, "falta bwrap")):
            encerrado = armado.sandbox_de({}, self.agy, mock.Mock(), "t1", Path("/p/wt"))
        self.assertFalse(encerrado["activo"])
        with self.assertRaisesRegex(sandbox.SandboxNoDisponible, "no se lanzará"):
            armado.comando(config(), self.agy, "antigravity", "", "P", self.CARPETAS)

    def test_su_sandbox_se_pide_en_la_config_dentro_de_la_jaula(self):
        argv = armado.comando(config({"lanzar": {"argumentos_extra": {
            "antigravity": ["--sandbox"]}}}), self.agy, "antigravity", "", "P",
            self.CARPETAS, ["main"], sandbox=self.ajustes)
        self.assertIn("--sandbox", argv)
        self.assertLess(argv.index("--sandbox"), argv.index("-p"))

    def test_preparar_aprueba_sus_comandos_y_le_da_las_carpetas(self):
        argv = preparar.comando(config(), self.agy, "", "P")
        self.assertEqual(argv, ["agy", "--print-timeout", "0",
                                "--dangerously-skip-permissions", "-p", "P"])

    def test_preparar_con_carpeta_tambien_va_en_la_jaula(self):
        with tempfile.TemporaryDirectory() as carpeta, \
                mock.patch.object(sandbox, "disponible_bwrap", return_value=(True, "")), \
                mock.patch.dict(os.environ, {"COTEJO_CONFIG": str(Path(carpeta) / "config.json")}):
            argv = preparar.comando(config(), self.agy, "", "P", carpeta=carpeta)
        self.assertEqual(Path(argv[0]).name, "bwrap")
        agy = argv[argv.index("--") + 1:]
        self.assertIn("--dangerously-skip-permissions", agy)
        self.assertNotIn(str(Path(carpeta) / "config.json"), agy)
        self.assertEqual(agy[-2:], ["-p", "P"])

    def test_preparar_registra_el_repo_fuera_de_la_jaula_una_sola_vez(self):
        from tareas import configuracion
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            config_real = raiz / "config" / "cotejo" / "config.json"
            with mock.patch.dict(os.environ, {"COTEJO_CONFIG": str(config_real),
                                              "XDG_CONFIG_HOME": str(raiz / "config")}):
                os.environ.pop(configuracion.VEDADA, None)
                preparar._registrar_repo_para_antigravity(raiz / "proyecto")
                preparar._registrar_repo_para_antigravity(raiz / "proyecto")
                datos = configuracion.cargar()
        self.assertEqual(datos["fuentes"]["repo"]["repos"], [str(raiz / "proyecto")])


class Catalogo(unittest.TestCase):
    def test_de_fabrica_el_modelo_que_tenga_elegido_para_cualquier_nivel(self):
        n1, n2, n3 = (niveles.POR_CLAVE[c] for c in ("n1", "n2", "n3"))
        for nivel in (n1, n2, n3):
            elegido = niveles.del_cliente(nivel, "antigravity")
            self.assertEqual((elegido.clave, elegido.cliente), ("antigravity", "antigravity"))
            self.assertEqual(clientes.de("antigravity").modelo_de(elegido.modelo,
                                                                  elegido.modelo_id), "")

    def test_un_slug_registrado_se_lanza_con_model(self):
        propio = {"clave": "argon", "modelo_id": "gemini-4-argon-high",
                  "cliente": "antigravity", "nivel": "n3"}
        elegido = niveles.del_cliente(niveles.POR_CLAVE["n3"], "antigravity", [propio])
        self.assertEqual(elegido.modelo_id, "gemini-4-argon-high")
        self.assertEqual(clientes.de("antigravity").modelo_de(elegido.modelo,
                                                              elegido.modelo_id),
                         "gemini-4-argon-high")

    def test_sale_en_asignar_a(self):
        grupos = dict(niveles.grupos((), ["antigravity"]))
        self.assertEqual(grupos, {"antigravity": ["antigravity"]})


class ConMaquinaFalsa(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        self.casa = raiz / "casa"
        self.bin = raiz / "bin"
        self.casa.mkdir()
        self.bin.mkdir()
        os.symlink(shutil.which("sh"), self.bin / "sh")
        parche = mock.patch.dict(os.environ, {
            "HOME": str(self.casa), "PATH": str(self.bin),
            "XDG_STATE_HOME": str(raiz / "estado"), "GEMINI_API_KEY": "", "AGY_ADC_AUTH": ""})
        parche.start()
        self.addCleanup(parche.stop)

    def agy(self, guion=MODELOS):
        ruta = self.bin / "agy"
        ruta.write_text(guion, encoding="utf-8")
        ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)
        return ruta

    def settings(self, datos):
        ruta = self.casa / ".gemini" / "antigravity-cli" / "settings.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")


class Modelos(ConMaquinaFalsa):
    def test_agy_models_es_su_lista(self):
        self.agy()
        self.assertEqual(modelos_vivos.listar("antigravity"),
                         ["gemini-4-argon-high", "gemini-3.8-flash-medium", "gemini-3.1-pro-high"])

    def test_sin_agy_o_si_falla_no_inventa_ninguno(self):
        self.assertEqual(modelos_vivos.listar("antigravity"), [])
        self.agy("#!/bin/sh\nexit 1\n")
        self.assertEqual(modelos_vivos.listar("antigravity", refrescar=True), [])

    def test_leer_agy_aguanta_basura(self):
        self.assertEqual(modelos_vivos.leer_agy("Available models:\n\n  ...\nError: x\n"), [])


class Sesion(ConMaquinaFalsa):
    def test_en_el_llavero_no_se_ve_pero_instalado_cuenta_como_listo(self):
        self.agy()
        self.assertFalse(modelos_vivos.sesion("antigravity"))
        self.assertFalse(modelos_vivos.sesion_visible("antigravity"))
        self.assertIn("antigravity", modelos_vivos.listos())
        fila = next(f for f in modelos_vivos.resumen(preguntar_cli=False)
                    if f["cliente"] == "antigravity")
        self.assertEqual((fila["instalado"], fila["sesion"], fila["sesion_visible"]),
                         (True, False, False))

    def test_sin_instalar_no_cuenta(self):
        self.assertNotIn("antigravity", modelos_vivos.listos())

    def test_por_adc(self):
        with mock.patch.dict(os.environ, {"AGY_ADC_AUTH": "true"}):
            self.assertTrue(modelos_vivos.sesion("antigravity"))

    def test_la_clave_de_gemini_solo_vale_con_su_proveedor(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            self.assertFalse(modelos_vivos.sesion("antigravity"))
            self.settings({"modelProvider": "gemini"})
            self.assertTrue(modelos_vivos.sesion("antigravity"))

    def test_no_se_le_pregunta_nada_al_cli(self):
        self.agy("#!/bin/sh\ntouch \"$HOME/lanzado\"\n")
        modelos_vivos.sesion("antigravity", preguntar_cli=True)
        self.assertFalse((self.casa / "lanzado").exists())


class PorElMotorHeadless(unittest.TestCase):
    def test_sin_carpeta_no_lanza_agy_desprotegido(self):
        instancia = claude_cli.ClaudeCLI({})
        instancia.config = config()
        encargo = motor.Encargo(prompt="Haz la tarea", modelo="antigravity", modelo_id="",
                                cliente="antigravity")
        with self.assertRaises(sandbox.SandboxNoDisponible):
            instancia.argv(encargo)
        self.assertIn("no se lanzará", instancia.comprobar(encargo))

    def test_con_carpeta_lanza_la_jaula(self):
        instancia = claude_cli.ClaudeCLI({})
        instancia.config = config()
        encargo = motor.Encargo(prompt="Haz la tarea", modelo="antigravity", modelo_id="",
                                cliente="antigravity", directorio="/p/wt", tarea_id="t1")
        ajustes = sandbox.ajustes_claude(["/p/wt"])
        hecho = {"carpetas": ["/p/wt"], "ramas": ["main"],
                 "encerrado": {"activo": True, "cliente": "antigravity", "ajustes": ajustes,
                               "entorno": {}, "avisos": []}}
        with mock.patch.object(instancia, "_armado", return_value=hecho):
            argv = instancia.argv(encargo)
        self.assertEqual(Path(argv[0]).name, "bwrap")
        self.assertEqual(argv[-2:], ["-p", mock.ANY])
        self.assertIn("Haz la tarea", argv[-1])


@unittest.skipUnless(shutil.which("bwrap") and sandbox.disponible_bwrap()[0],
                     "sin bwrap o sin namespaces")
class EnLaJaula(unittest.TestCase):
    """Un `agy` de mentira, jamás el real: la jaula deja trabajar y bloquea el resto."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-b1iwpj-"))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.trabajo = self.base / "trabajo"
        self.fuera = self.base / "fuera"
        self.bin = self.base / "bin"
        for carpeta in (self.trabajo, self.fuera, self.bin):
            carpeta.mkdir()
        self.config = self.base / "config" / "cotejo" / "config.json"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("original\n", encoding="utf-8")
        self.agy = self.bin / "agy"
        self.agy.write_text("""#!/bin/sh
printf dentro > \"$TRABAJO/dentro\"
printf fuera > \"$FUERA/archivo\" 2>/dev/null && echo ESCRIBIO_FUERA || echo FUERA_BLOQUEADA
printf config > \"$CONFIG\" 2>/dev/null && echo ESCRIBIO_CONFIG || echo CONFIG_BLOQUEADA
printf '%s\\n' \"$@\" > \"$TRABAJO/argumentos\"
""", encoding="utf-8")
        self.agy.chmod(0o755)

    def test_el_agy_falso_escribe_solo_lo_suyo(self):
        ajustes = sandbox.ajustes_claude([str(self.trabajo)], [str(self.config)])
        argv = sandbox.envolver_antigravity(
            [str(self.agy), "--dangerously-skip-permissions", "-p", "P"], ajustes, self.trabajo)
        hecho = subprocess.run(argv, cwd=self.trabajo, capture_output=True, text=True, timeout=30,
                               env={**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                                    "TRABAJO": str(self.trabajo), "FUERA": str(self.fuera),
                                    "CONFIG": str(self.config)})
        self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        self.assertEqual((self.trabajo / "dentro").read_text(), "dentro")
        self.assertIn("--dangerously-skip-permissions",
                      (self.trabajo / "argumentos").read_text())
        self.assertIn("FUERA_BLOQUEADA", hecho.stdout)
        self.assertIn("CONFIG_BLOQUEADA", hecho.stdout)
        self.assertFalse((self.fuera / "archivo").exists())
        self.assertEqual(self.config.read_text(), "original\n")


if __name__ == "__main__":
    unittest.main()
