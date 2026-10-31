"""El maestro como conversación, sin terminal (v1.3.0, cotejo-9ybn1a), sin GTK.

De punta a punta con el cliente falso (`cliente_falso.py`) en lugar de un agente: `cotejo
maestro` lanza un turno sin interfaz, el falso corre `cotejo crear` con el `cotejo` que le puso
el lanzador en el PATH (la tarea aparece en el vault de verdad), contesta, y la CLI devuelve su
respuesta con lo que propuso repartir, ya filtrado por Cotejo. La conversación queda en la
carpeta de estado y el siguiente turno la lee. Ninguna prueba abre una terminal: si alguna lo
intentara, `terminal.abrir` falla la prueba.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import clientes, config as cfg, conversacion, maestro, verbos
from enrutador.motores import terminal
from tareas import preparacion

FALSO = str(Path(__file__).with_name("cliente_falso.py"))


def _nunca_una_terminal(*_a, **_k):
    raise AssertionError("el maestro no puede abrir una terminal")


class Conversacion(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.estado = Path(temporal.name) / "estado"
        self.argv_falso = Path(temporal.name) / "argv.json"
        self.repo = Path(temporal.name) / "uno"
        self.repo.mkdir()
        for parche in (mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.estado),
                                                    "FALSO_ARGV": str(self.argv_falso)}),
                       mock.patch.object(preparacion, "CARPETA",
                                         self.estado / "preparaciones"),
                       mock.patch.object(terminal, "abrir", _nunca_una_terminal),
                       mock.patch("enrutador.clientes.shutil.which",
                                  return_value="/usr/bin/x")):
            parche.start()
            self.addCleanup(parche.stop)
        self.escribir_config({
            "proyectos": {"Uno": str(self.repo)},
            "motores": {"headless": {"comando": [sys.executable, FALSO], "aislar": False}}})
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/sonnet ^cotejo-asig",
            "- [ ] Rediseñar la capa Fuente #medio ^cotejo-prop",
            "- [ ] Llamar al contador #agente/persona ^cotejo-pers",
        ))

    def hablar(self, pedido, *extra, **entorno):
        with mock.patch.dict(os.environ, entorno):
            return self.correr("maestro", "--proyecto", "Uno", "--pedido", pedido,
                               "--cliente", "claude", *extra)

    def argv(self):
        return json.loads(self.argv_falso.read_text(encoding="utf-8"))

    # --- de punta a punta ---------------------------------------------------------------------

    def test_pedir_una_tarea_la_apunta_en_el_proyecto_y_contesta(self):
        codigo, datos = self.hablar("apunta que falta el login", FALSO_CREAR="Hacer el login",
                                    FALSO_PROYECTO="Uno",
                                    FALSO_RESPUESTA="Apunté «Hacer el login».")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["respuesta"], "Apunté «Hacer el login».")
        self.assertIn("Hacer el login", self.leer_nota("Uno.md"))
        # La conversación queda guardada, con los dos turnos.
        turnos = conversacion.leer("Uno")["turnos"]
        self.assertEqual([t["quien"] for t in turnos], ["persona", "maestro"])
        self.assertEqual(turnos[0]["texto"], "apunta que falta el login")
        self.assertNotIn("en_curso", conversacion.leer("Uno"))

    def test_el_cliente_va_sin_interfaz_y_solo_puede_correr_cotejo(self):
        self.hablar("hola")
        argv = self.argv()["argv"]
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Bash(cotejo:*)")
        for vedada in ("Edit", "Write"):
            self.assertIn(vedada, argv[argv.index("--disallowedTools"):])
        self.assertIn("--setting-sources", argv)
        self.assertEqual(argv[-2], "--")      # el prompt no se lo come --disallowedTools
        # Trabaja en la carpeta del proyecto y usa el mismo cotejo que el board.
        self.assertEqual(self.argv()["cwd"], str(self.repo))
        self.assertTrue(self.argv()["path"].startswith(
            str(self.estado / "agente" / "bin")))

    def test_el_siguiente_turno_lee_la_conversacion(self):
        self.hablar("qué falta", FALSO_RESPUESTA="Falta el parseo.")
        self.hablar("y qué más")
        prompt = self.argv()["argv"][-1]
        self.assertIn("[Persona] qué falta", prompt)
        self.assertIn("[Maestro] Falta el parseo.", prompt)
        self.assertIn("y qué más", prompt)

    def test_repartir_solo_propone_lo_que_una_persona_asigno(self):
        codigo, datos = self.hablar(
            "reparte lo asignado",
            FALSO_RESPUESTA="Te propongo esta.\nREPARTIR: cotejo-asig cotejo-prop cotejo-pers")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["repartir"], ["cotejo-asig"])
        self.assertEqual(datos["respuesta"], "Te propongo esta.")
        self.assertEqual(conversacion.leer("Uno")["turnos"][-1]["repartir"], ["cotejo-asig"])
        # Proponer no lanza ni toma nada.
        self.assertNotIn("#en-curso", self.leer_nota("Uno.md"))

    def test_un_cliente_que_contesta_en_texto_plano_tambien_vale(self):
        with mock.patch.dict(os.environ, {"FALSO_PLANO": "1", "FALSO_RESPUESTA": "Hola, soy el"
                                          " maestro.", "FALSO_CREAR": "Algo nuevo",
                                          "FALSO_PROYECTO": "Uno"}):
            self.escribir_config({
                "proyectos": {"Uno": str(self.repo)},
                "motores": {"headless": {"clientes": {"codex": {
                    "comando": [sys.executable, FALSO]}}, "aislar": False}}})
            codigo, datos = self.correr("maestro", "--proyecto", "Uno", "--pedido", "hola",
                                        "--cliente", "codex")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertEqual(datos["respuesta"], "Hola, soy el maestro.")
        argv = self.argv()["argv"]
        self.assertIn("exec", argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")
        # Codex escribe solo donde van las tareas: arranca ahí, no en el código.
        self.assertEqual(Path(self.argv()["cwd"]), self.vault / self.CARPETA)
        self.assertIn("Algo nuevo", self.leer_nota("Uno.md"))

    def test_si_el_cliente_falla_lo_dice_en_la_conversacion(self):
        codigo, datos = self.hablar("hola", FALSO_PLANO="1", FALSO_RESPUESTA="",
                                    FALSO_CODIGO="3")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["ok"])
        self.assertIn("no contestó", datos["respuesta"])

    def test_olvidar_empieza_de_cero(self):
        self.hablar("qué falta")
        self.assertTrue(conversacion.leer("Uno")["turnos"])
        self.hablar("hola", "--olvidar")
        self.assertEqual(len(conversacion.leer("Uno")["turnos"]), 2)
        self.assertNotIn("[Persona] qué falta", self.argv()["argv"][-1])

    def test_simular_no_lanza_nada(self):
        with mock.patch("enrutador.apertura.ramas_pendientes.detectar", return_value=[{
                "rama": "cotejo/cotejo-guardado", "commits": 2, "ultimo": "Hacer la app",
                "texto": "Hacer la app", "motivo": "espera aprobación"}]):
            codigo, datos = self.correr("maestro", "--proyecto", "uno", "--pedido", "hola",
                                        "--simular")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["lanzado"])
        self.assertFalse(self.argv_falso.exists())
        self.assertEqual(datos["proyecto"], "Uno")
        self.assertEqual({t["id"] for t in datos["asignadas"]}, {"cotejo-asig"})
        self.assertEqual(datos["ramas_pendientes"][0]["rama"], "cotejo/cotejo-guardado")
        self.assertIn("cotejo/cotejo-guardado", datos["prompt"])

    def test_un_turno_que_murio_sin_volver_no_se_queda_pensando(self):
        datos = {"proyecto": "Uno", "turnos": [{"quien": "persona", "texto": "hola"}],
                 "en_curso": {"pid": 999999999, "programa": "claude", "cliente": "claude",
                              "out": str(self.estado / "nada.out")}}
        conversacion._guardar(datos)
        leido = conversacion.leer("Uno")
        self.assertNotIn("en_curso", leido)
        self.assertIn("se cortó", leido["turnos"][-1]["texto"])


class Permisos(PruebaDeEnrutador):
    """Lo que puede hacer cada cliente en un turno: solo leer y correr `cotejo`."""

    def comando(self, nombre, directorio="/tmp/proy", escritura=("/tmp/tareas", "/tmp/estado")):
        return conversacion.comando(cfg.cargar(), clientes.de(nombre), "", "PROMPT",
                                    directorio, list(escritura))

    def test_opencode_no_edita_y_solo_corre_cotejo(self):
        argv, env, trabajo = self.comando("opencode")
        self.assertEqual(argv[:2], ["opencode", "run"])
        permiso = json.loads(env["OPENCODE_CONFIG_CONTENT"])["permission"]
        self.assertEqual(permiso["edit"], "deny")
        self.assertEqual(permiso["bash"], {"*": "deny", "cotejo": "allow", "cotejo *": "allow"})
        self.assertEqual(trabajo, "/tmp/proy")

    def test_gemini_solo_corre_cotejo(self):
        argv, env, _ = self.comando("gemini")
        self.assertIn("run_shell_command(cotejo)", argv)
        self.assertEqual(argv[-2:], ["-p", "PROMPT"])
        self.assertIn("GEMINI_CLI_TRUST_WORKSPACE", env)

    def test_codex_escribe_solo_en_las_tareas_y_el_estado(self):
        argv, _, trabajo = self.comando("codex")
        self.assertEqual(trabajo, "/tmp/tareas")
        self.assertEqual(argv[argv.index("--add-dir") + 1], "/tmp/estado")
        self.assertNotIn("/tmp/proy", argv[:-1])

    def test_antigravity_no_habla_sin_su_jaula(self):
        with mock.patch("enrutador.sandbox.disponible_bwrap", return_value=(False, "sin bwrap")):
            with self.assertRaises(conversacion.NoSePuede):
                self.comando("antigravity")


class Instruccion(unittest.TestCase):
    ASIGNADAS = [{"id": "cotejo-asig", "modelo": "sonnet", "texto": "Arreglar el parseo"}]

    def test_ensena_las_tres_cosas_y_ningun_verbo_para_finalizar(self):
        texto = maestro.instruccion("Uno", self.ASIGNADAS, "/tmp/uno", "hola")
        for parte in ('cotejo crear "', "cotejo tareas --proyecto", "REPARTIR:",
                      "cotejo-asig → sonnet", "/tmp/uno"):
            self.assertIn(parte, texto)
        for verbo in ("cotejo finalizar", "cotejo marcar", "--motor headless", "terminal que"):
            self.assertNotIn(verbo, texto)

    def test_sin_asignadas_dice_donde_se_asignan(self):
        self.assertIn("Asignar a", maestro.instruccion("Uno", [], None, "reparte"))

    def test_la_historia_se_recorta(self):
        historia = [{"quien": "persona", "texto": f"mensaje {i}"} for i in range(30)]
        texto = maestro.instruccion("Uno", [], None, "y ahora", historia)
        self.assertNotIn("mensaje 0\n", texto)
        self.assertIn("mensaje 29", texto)

    def test_pedidas_filtra_y_sin_marca_limpia(self):
        respuesta = "Hecho.\n**REPARTIR:** cotejo-asig, cotejo-otra cotejo-asig"
        self.assertEqual(maestro.pedidas(respuesta, self.ASIGNADAS), ["cotejo-asig"])
        self.assertEqual(maestro.sin_marca(respuesta), "Hecho.")


if __name__ == "__main__":
    unittest.main()
