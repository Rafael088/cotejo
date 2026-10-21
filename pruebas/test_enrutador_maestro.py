"""El maestro y los clientes: que cada modelo se lance con el cliente que lo ejecuta, y que el
maestro solo reparta lo que una persona asignó.

Ninguna de estas pruebas lanza un cliente ni abre una terminal: `terminal.abrir` y `which` van
simulados. Una prueba que abre ventanas o gasta tokens se acaba desactivando.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from apoyo import RAIZ, PruebaDeEnrutador, proyecto

from enrutador import clientes, config as cfg, maestro, motor, verbos
from enrutador.motores import terminal
from tareas import rutas

KIMI = {"clave": "kimi-k2.7-code", "nombre": "Kimi K2.7 Code",
        "modelo_id": "opencode-go/kimi-k2.7-code", "cliente": "opencode", "nivel": "n2"}


def encargo(cliente="claude", modelo="sonnet", modelo_id=""):
    return motor.Encargo(prompt="haz esto", modelo=modelo, modelo_id=modelo_id,
                         cliente=cliente)


class Clientes(unittest.TestCase):
    def test_cada_cliente_se_pide_sin_interfaz_a_su_manera(self):
        esperado = {
            "claude": ["claude", "-p", "--model", "sonnet", "haz esto"],
            "opencode": ["opencode", "run", "-m", "prov/m", "haz esto"],
            "codex": ["codex", "exec", "-m", "prov/m", "haz esto"],
            "gemini": ["gemini", "-m", "prov/m", "-p", "haz esto"],
        }
        for nombre, argv in esperado.items():
            with self.subTest(cliente=nombre):
                cliente = clientes.de(nombre)
                modelo = cliente.modelo_de("sonnet", "prov/m" if nombre != "claude" else "")
                self.assertEqual(cliente.argv_sin_interfaz(modelo, "haz esto"), argv)

    def test_claude_usa_el_alias_y_los_demas_el_id(self):
        self.assertEqual(clientes.de("claude").modelo_de("opus", "claude-opus-5"), "opus")
        self.assertEqual(clientes.de("opencode").modelo_de("kimi-k2.7-code",
                                                           "opencode-go/kimi-k2.7-code"),
                         "opencode-go/kimi-k2.7-code")

    def test_un_cliente_que_no_se_conoce_lo_dice_con_los_que_si(self):
        with self.assertRaises(clientes.ClienteDesconocido) as error:
            clientes.de("aider")
        self.assertIn("opencode", str(error.exception))


class TerminalPorPlataforma(PruebaDeEnrutador):
    """`enrutador.maestro.terminal` sale de la plataforma cuando la config no dice otra.

    Antes el defecto era siempre `["xdg-terminal-exec"]`, que no existe en Windows: el botón del
    maestro del board fallaba ahí con un consejo de Linux (`alacritty -e`). Las pruebas fingen la
    plataforma con `sys.platform`, como `pruebas/test_rutas.py`: no hace falta una máquina
    Windows para saber qué saldría ahí.
    """

    def test_en_windows_el_defecto_es_cmd_start(self):
        with mock.patch.object(rutas.sys, "platform", "win32"):
            self.assertEqual(cfg.cargar()["maestro"]["terminal"],
                             ["cmd", "/c", "start", ""])

    def test_en_linux_sigue_siendo_xdg_terminal_exec(self):
        with mock.patch.object(rutas.sys, "platform", "linux"):
            self.assertEqual(cfg.cargar()["maestro"]["terminal"], ["xdg-terminal-exec"])

    def test_una_terminal_puesta_a_mano_gana_en_cualquier_plataforma(self):
        self.escribir_config({"maestro": {"terminal": ["wezterm", "start", "--"]}})
        for plataforma in ("win32", "linux", "darwin"):
            with self.subTest(plataforma):
                with mock.patch.object(rutas.sys, "platform", plataforma):
                    self.assertEqual(cfg.cargar()["maestro"]["terminal"],
                                     ["wezterm", "start", "--"])

    def test_el_defecto_de_windows_no_se_cuela_en_los_defectos_de_modulo(self):
        # `_fundir` puede devolver el propio diccionario de DEFECTOS cuando nadie lo pisa; si
        # `cargar()` lo rellenara sin copiarlo antes, esta prueba (y cualquier llamada posterior
        # en Linux) heredaría el `cmd /c start` calculado aquí.
        with mock.patch.object(rutas.sys, "platform", "win32"):
            cfg.cargar()
        self.assertIsNone(cfg.DEFECTOS["maestro"]["terminal"])
        with mock.patch.object(rutas.sys, "platform", "linux"):
            self.assertEqual(cfg.cargar()["maestro"]["terminal"], ["xdg-terminal-exec"])

    def test_el_maestro_abre_cmd_start_en_windows(self):
        self.escribir_config({"proyectos": {"Uno": "/tmp/uno"}})
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el build #agente/opus ^cotejo-win",
        ))
        with mock.patch.object(rutas.sys, "platform", "win32"), \
                mock.patch.object(terminal, "abrir") as abrir, \
                mock.patch("enrutador.clientes.shutil.which", return_value="C:/claude.exe"):
            codigo, datos = self.correr("maestro", "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.OK)
        self.assertTrue(datos["abierto"])
        comando, directorio = abrir.call_args.args
        self.assertEqual(comando[:5], ["cmd", "/c", "start", "", "claude"])
        self.assertEqual(str(directorio), "/tmp/uno")

    def test_el_mensaje_sin_terminal_no_manda_a_instalar_algo_de_otro_sistema(self):
        with mock.patch.object(terminal.shutil, "which", return_value=None):
            with mock.patch.object(rutas.sys, "platform", "win32"):
                with self.assertRaises(terminal.SinTerminal) as error:
                    terminal.abrir(["no-existe"])
            self.assertIn("cmd", str(error.exception))
            self.assertNotIn("alacritty", str(error.exception))

            with mock.patch.object(rutas.sys, "platform", "linux"):
                with self.assertRaises(terminal.SinTerminal) as error:
                    terminal.abrir(["no-existe"])
            self.assertIn("alacritty", str(error.exception))


class Motores(PruebaDeEnrutador):
    def test_el_headless_lanza_el_cliente_del_modelo_y_no_siempre_claude(self):
        # El caso que lo motivó: una tarea de #agente/kimi-k2.7-code acababa en
        # `claude --model kimi-k2.7-code`, que no existe.
        argv = motor.abrir("headless", cfg.cargar()).argv(
            encargo("opencode", "kimi-k2.7-code", "opencode-go/kimi-k2.7-code"))
        self.assertEqual(argv[:4], ["opencode", "run", "-m", "opencode-go/kimi-k2.7-code"])

    def test_los_argumentos_de_otro_cliente_van_en_su_propia_clave(self):
        self.escribir_config({"motores": {"headless": {
            "argumentos_extra": ["--solo-claude"],
            "clientes": {"opencode": {"argumentos_extra": ["--auto"]}}}}})
        argv = motor.abrir("headless", cfg.cargar()).argv(
            encargo("opencode", "k", "prov/k"))
        self.assertIn("--auto", argv)
        self.assertNotIn("--solo-claude", argv)

    def test_el_headless_avisa_antes_si_el_cliente_no_esta_instalado(self):
        headless = motor.abrir("headless", cfg.cargar())
        with mock.patch("enrutador.motores.claude_cli.shutil.which", return_value=None):
            self.assertIn("No encontré «opencode»",
                          headless.comprobar(encargo("opencode", "k", "prov/k")))
        self.assertIn("No sé cómo lanzar", headless.comprobar(encargo("aider", "k", "p/k")))

    def test_una_sesion_solo_sabe_abrir_claude(self):
        sesion = motor.abrir("sesion", cfg.cargar())
        with mock.patch("enrutador.motores.sesion.shutil.which", return_value="/bin/claude"):
            self.assertEqual(sesion.comprobar(encargo()), "")
        problema = sesion.comprobar(encargo("opencode", "k", "prov/k"))
        self.assertIn("--motor headless", problema)
        self.assertFalse(sesion.ejecutar(encargo("opencode", "k", "prov/k")).ejecutado)

    def test_el_simulado_ensena_el_cliente_de_verdad(self):
        resultado = motor.abrir("simulado", cfg.cargar()).ejecutar(
            encargo("opencode", "k", "prov/k"))
        self.assertEqual(resultado.comando[:2], ["opencode", "run"])


class Despachar(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_config({"modelos": [KIMI]})
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/kimi-k2.7-code ^cotejo-kimi",
        ))

    def test_si_el_cliente_no_esta_la_tarea_no_se_toma(self):
        # Descubrirlo después de tomarla dejaba la tarea en «Haciéndola» a nombre de un modelo
        # que nunca empezó.
        with mock.patch("enrutador.motores.claude_cli.shutil.which", return_value=None):
            codigo, datos = self.correr("despachar", "cotejo-kimi", "--motor", "headless")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("opencode", datos["error"])
        self.assertIn("#agente/kimi-k2.7-code", self.leer_nota("Uno.md"))
        self.assertNotIn("#en-curso", self.leer_nota("Uno.md"))
        self.assertEqual(self.despachados()[-1]["rechazo"], "motor")

    def test_despachar_le_pasa_el_cliente_al_motor(self):
        codigo, datos = self.correr("despachar", "cotejo-kimi", "--simular")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["comando"][:4],
                         ["opencode", "run", "-m", "opencode-go/kimi-k2.7-code"])


class Maestro(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_config({"modelos": [KIMI], "proyectos": {"Uno": "/tmp/uno"}})
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/kimi-k2.7-code ^cotejo-kimi",
            "- [ ] Documentar el protocolo #agente/opus ^cotejo-opus",
            "- [ ] Rediseñar la capa Fuente #medio ^cotejo-prop",
            "- [ ] Comprar el dominio atlas.co ^cotejo-hum1",
            "- [ ] Llamar al contador #agente/persona ^cotejo-pers",
        ))
        self.escribir_nota("Dos.md", proyecto("- [ ] Algo sin asignar ^cotejo-dos1"))

    def test_plan_solo_asignadas_deja_las_que_una_persona_dio_a_un_modelo(self):
        _, datos = self.correr("plan", "--proyecto", "Uno", "--solo-asignadas")
        self.assertEqual({t["id"] for t in datos["tareas"]}, {"cotejo-kimi", "cotejo-opus"})

    def test_el_maestro_solo_reparte_lo_asignado(self):
        codigo, datos = self.correr("maestro", "--proyecto", "Uno", "--simular")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual({t["id"] for t in datos["asignadas"]}, {"cotejo-kimi", "cotejo-opus"})
        instruccion = datos["comando"][-1]
        for fuera in ("cotejo-prop", "cotejo-hum1", "cotejo-pers"):
            self.assertNotIn(fuera, instruccion)
        self.assertIn("cotejo despachar <id> --motor headless", instruccion)
        self.assertIn("/tmp/uno", instruccion)
        self.assertFalse(datos["abierto"])

    def test_el_maestro_se_abre_en_una_terminal_con_el_cliente_elegido(self):
        with mock.patch.object(terminal, "abrir") as abrir, \
                mock.patch("enrutador.clientes.shutil.which", return_value="/usr/bin/x"):
            codigo, datos = self.correr("maestro", "--proyecto", "uno", "--cliente", "opencode")
        self.assertEqual(codigo, verbos.OK)
        self.assertTrue(datos["abierto"])
        comando, directorio = abrir.call_args.args
        self.assertEqual(comando[:3], ["xdg-terminal-exec", "opencode", "--prompt"])
        self.assertEqual(str(directorio), "/tmp/uno")
        # Abrir el maestro no toma nada: eso lo hace cada despacho.
        self.assertNotIn("#en-curso", self.leer_nota("Uno.md"))

    def test_claude_abre_el_maestro_con_el_modelo_de_la_config(self):
        _, datos = self.correr("maestro", "--proyecto", "Uno", "--simular")
        self.assertEqual(datos["comando"][:4], ["xdg-terminal-exec", "claude", "--model", "opus"])

    def test_sin_tareas_asignadas_no_se_abre_nada(self):
        with mock.patch.object(terminal, "abrir") as abrir, \
                mock.patch("enrutador.clientes.shutil.which", return_value="/usr/bin/x"):
            codigo, datos = self.correr("maestro", "--proyecto", "Dos")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("asigna", datos["salida"].lower())
        abrir.assert_not_called()

    def test_un_cliente_no_instalado_no_abre_nada(self):
        with mock.patch.object(terminal, "abrir") as abrir, \
                mock.patch("enrutador.clientes.shutil.which", return_value=None):
            codigo, datos = self.correr("maestro", "--proyecto", "Uno", "--cliente", "codex")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("no está instalado", datos["error"])
        abrir.assert_not_called()

    def sin_clientes(self):
        """Un PATH que existe pero está vacío: ningún agente, con el `which` de verdad."""
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = mock.patch.dict(os.environ, {"PATH": carpeta.name})
        parche.start()
        self.addCleanup(parche.stop)

    def test_sin_ningun_agente_el_maestro_dice_que_hacer_y_no_nombra_a_claude(self):
        self.sin_clientes()
        for extra in ((), ("--simular",)):
            with self.subTest(extra=extra), mock.patch.object(terminal, "abrir") as abrir:
                codigo, datos = self.correr("maestro", "--proyecto", "Uno", *extra)
            self.assertEqual(codigo, verbos.ERROR)
            self.assertEqual(datos["error"], clientes.SIN_AGENTE)
            self.assertEqual(datos["salida"], clientes.SIN_AGENTE_SALIDA)
            self.assertIn("MCP", datos["salida"])
            self.assertNotIn("claude", datos["error"].lower())
            self.assertNotIn("«claude»", datos["salida"])
            self.assertNotIn("clientes_que_faltan", datos)
            abrir.assert_not_called()

    def test_el_mensaje_sin_agente_es_el_mismo_en_la_cli_y_en_el_board(self):
        # El board muestra `SIN_AGENTE_TEXTO`: mensaje y salida de la CLI unidos.
        self.sin_clientes()
        _, datos = self.correr("maestro", "--proyecto", "Uno")
        self.assertEqual(f"{datos['error']}. {datos['salida']}.", clientes.SIN_AGENTE_TEXTO)
        self.assertIn("Claude Code, Codex, Gemini CLI u opencode", clientes.SIN_AGENTE_TEXTO)

    def test_sin_ningun_agente_pedir_un_cliente_concreto_si_lo_nombra(self):
        self.sin_clientes()
        for extra in (("--cliente", "claude"), ("--cliente", "claude", "--simular")):
            with self.subTest(extra=extra), mock.patch.object(terminal, "abrir") as abrir:
                codigo, datos = self.correr("maestro", "--proyecto", "Uno", *extra)
            if "--simular" in extra:
                self.assertEqual(codigo, verbos.OK)
                self.assertEqual(datos["cliente"], "claude")
            else:
                self.assertEqual(codigo, verbos.ERROR)
                self.assertIn("«claude» no está instalado", datos["error"])
            abrir.assert_not_called()

    def test_el_verbo_maestro_de_punta_a_punta_sin_clientes_en_el_path(self):
        # El programa de verdad, en otro proceso, con HOME y XDG aislados y un PATH sin agentes.
        self.sin_clientes()
        with tempfile.TemporaryDirectory() as casa:
            entorno = {**os.environ, "HOME": casa, "XDG_CONFIG_HOME": casa + "/c",
                       "XDG_STATE_HOME": casa + "/s", "XDG_DATA_HOME": casa + "/d",
                       "DBUS_SESSION_BUS_ADDRESS": "", "COTEJO_MOTOR": "agente",
                       "PYTHONPATH": str(RAIZ)}
            hecho = subprocess.run([sys.executable, "-m", "tareas", "maestro", "--proyecto",
                                    "Uno"], capture_output=True, text=True, env=entorno,
                                   cwd=casa)
        self.assertNotEqual(hecho.returncode, 0)
        texto = hecho.stdout + hecho.stderr
        self.assertIn(clientes.SIN_AGENTE, texto)
        # «Claude Code» sale en la lista de agentes para instalar; claude como el elegido, no.
        self.assertNotIn("claude", texto.lower().replace("claude code", ""))

    def test_sin_cliente_pedido_se_abre_con_el_primero_instalado(self):
        solo_codex = lambda nombre: "/usr/bin/codex" if nombre == "codex" else None
        with mock.patch.object(terminal, "abrir") as abrir, \
                mock.patch("enrutador.clientes.shutil.which", side_effect=solo_codex):
            codigo, datos = self.correr("maestro", "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["cliente"], "codex")
        self.assertTrue(abrir.called)

    def test_sin_agentes_modelos_decidir_y_plan_avisan_sin_cambiar_despachable(self):
        con = {}
        for etiqueta, instalado in (("con", "/usr/bin/x"), ("sin", None)):
            with mock.patch("enrutador.clientes.shutil.which", return_value=instalado):
                _, modelos = self.correr("modelos")
                _, decidir = self.correr("decidir", "cambiar un typo", "--modelo",
                                         "sonnet")
                _, plan = self.correr("plan", "--proyecto", "Uno")
            con[etiqueta] = (modelos, decidir, plan)
        sin_m, sin_d, sin_p = con["sin"]
        con_m, con_d, con_p = con["con"]
        sonnet = next(n for n in sin_m["niveles"] if n["modelo"] == "sonnet")
        self.assertTrue(sonnet["despachable"])
        self.assertFalse(sonnet["cliente_instalado"])
        self.assertTrue(next(n for n in con_m["niveles"]
                             if n["modelo"] == "sonnet")["cliente_instalado"])
        self.assertTrue(sin_d["decision"]["despachable"])
        self.assertFalse(sin_d["decision"]["cliente_instalado"])
        self.assertTrue(con_d["decision"]["cliente_instalado"])
        for sin in (sin_m, sin_d, sin_p):
            self.assertTrue(any("ningún agente" in a for a in sin["avisos"]), sin)
        for con_ in (con_m, con_d, con_p):
            self.assertNotIn("avisos", con_)
        self.assertEqual([t["despachable"] for t in sin_p["tareas"]],
                         [t["despachable"] for t in con_p["tareas"]])

    def test_el_nombre_del_proyecto_se_resuelve_sin_adivinar(self):
        self.assertEqual(maestro.resolver_proyecto("cotejo", ["Cotejo", "Cotejo Web"]), "Cotejo")
        self.assertEqual(maestro.resolver_proyecto("web", ["Cotejo", "Cotejo Web"]),
                         "Cotejo Web")
        with self.assertRaises(maestro.SinProyecto):
            maestro.resolver_proyecto("cot", ["Cotejo", "Cotejo Web"])
        with self.assertRaises(maestro.SinProyecto):
            maestro.resolver_proyecto("nada", ["Cotejo"])

    def test_sin_carpeta_configurada_el_maestro_pregunta_antes_de_despachar(self):
        texto = maestro.instruccion("Uno", [{"id": "x", "modelo": "opus", "texto": "t"}])
        self.assertIn("pregúntale a la persona en qué carpeta", texto)

    def test_el_maestro_no_aprende_a_finalizar(self):
        # Mismo veto que la CLI y el enrutador: la instrucción nombra entregar y bloquear, y
        # dice que [x] es de una persona. No puede nombrar un verbo para finalizar.
        texto = maestro.instruccion("Uno", [{"id": "x", "modelo": "opus", "texto": "t"}])
        for verbo in ("cotejo finalizar", "cotejo marcar", "--motor headless --auto"):
            self.assertNotIn(verbo, texto)

    def test_la_indicacion_de_la_persona_llega_al_maestro_sin_saltarse_reglas(self):
        asignadas = [{"id": "x", "modelo": "opus", "texto": "t"}]
        texto = maestro.instruccion("Uno", asignadas, indicacion="  solo las de   la v1.2.4 ")
        self.assertIn("«solo las de la v1.2.4»", texto)
        self.assertIn("dentro de las reglas", texto)
        self.assertNotIn("indicación", maestro.instruccion("Uno", asignadas))


if __name__ == "__main__":
    unittest.main()
