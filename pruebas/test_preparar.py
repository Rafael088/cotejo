"""Preparar un proyecto en segundo plano (v1.3.0) sin lanzar ningún agente de verdad.

El «cliente» es un script de Python (`CLIENTE`) que hace lo que haría un agente con el prompt de
inicio: lee la carpeta del prompt, escribe en `.cotejo/` y sale. Qué hace lo decide un archivo
`modo` junto a la carpeta: `ok` (deja una tarea), `vacio` (sale bien sin dejar nada), `error`
(sale con 3) o `dormir` (no vuelve). Nada de red ni de clientes reales.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from apoyo import RAIZ  # noqa: F401
from enrutador import clientes, config as cfg, preparar, procesos
from tareas import estado, inicio, preparacion

CLIENTE = textwrap.dedent('''
    import os, re, sys, time
    prompt = sys.argv[-1]
    carpeta = re.search(r"^Carpeta del proyecto: (.+)$", prompt, re.M).group(1)
    modo = open(os.path.join(os.path.dirname(carpeta), "modo")).read().strip()
    print("cliente falso, modo", modo, flush=True)
    os.makedirs(os.path.join(carpeta, ".cotejo"), exist_ok=True)
    with open(os.path.join(carpeta, ".cotejo", "entorno"), "w") as f:
        f.write(os.environ.get("COTEJO_FUENTE", ""))
    if modo == "ok":
        with open(os.path.join(carpeta, ".cotejo", "tareas.md"), "w") as f:
            f.write("# Tareas\\n- [ ] Primera: algo #v0.1.0\\n")
    elif modo == "error":
        print("no tengo sesion", flush=True)
        sys.exit(3)
    elif modo == "dormir":
        time.sleep(60)
''')


class Preparar(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.script = self.base / "cliente.py"
        self.script.write_text(CLIENTE)
        self.proyectos = self.base / "proyectos"
        self.proyectos.mkdir()
        self.carpeta = self.proyectos / "turnos"
        for objetivo, valor in ((preparacion, "CARPETA"),):
            parche = mock.patch.object(objetivo, valor, self.base / "estado" / "preparaciones")
            parche.start()
            self.addCleanup(parche.stop)
        self.avisos = []
        parche = mock.patch.object(preparar, "avisar_a_la_barra",
                                   lambda *_a: self.avisos.append(1))
        parche.start()
        self.addCleanup(parche.stop)
        self.config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {
            "motores": {"headless": {"comando": [sys.executable, str(self.script)],
                                     "aislar": False, "timeout_seg": 20}},
            "maestro": {"terminal": ["terminal-falsa", "-e"], "modelos": {}},
            "preparar": {"argumentos_extra": {"claude": []}},
        })
        # Cada hilo que espera a un cliente, para esperarlo al final: si no, uno escribiría su
        # registro con la carpeta temporal ya borrada.
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

    def _limpiar(self):
        for registro in preparacion.todas():
            if registro.get("fase") == "lanzado":
                procesos.terminar(registro.get("pid"), registro.get("programa", ""))
        for hilo in self.hilos:
            hilo.join(20)

    def modo(self, cual):
        (self.proyectos / "modo").write_text(cual)

    def respuestas(self):
        return inicio.Respuestas(que_es="Una app de turnos", que_hace="Reservar",
                                 carpeta=str(self.carpeta))

    def lanzar(self, modo, **kw):
        self.modo(modo)
        salida = preparar.lanzar(self.respuestas(), cliente="claude", config=self.config, **kw)
        return salida, self.hilos[-1]

    # --- lanzar y terminar ---------------------------------------------------------------

    def test_lanza_anota_el_pid_y_queda_listo(self):
        salida, hilo = self.lanzar("ok")
        self.assertEqual(salida["estado"], preparacion.PREPARANDO)
        registro = preparacion.leer(salida["id"])
        # Como un despacho: fase, pid, el programa del cliente (no systemd-run) y la máquina.
        self.assertEqual(registro["fase"], "lanzado")
        self.assertEqual(registro["programa"], sys.executable)
        self.assertTrue(registro["host"])
        hilo.join(20)
        registro = preparacion.leer(salida["id"])
        self.assertEqual((registro["fase"], registro["codigo"]), ("terminado", 0))
        self.assertEqual(preparar.estado(salida["id"])["estado"], preparacion.LISTO)
        self.assertGreaterEqual(len(self.avisos), 2)  # al lanzar y al terminar

    def test_el_agente_corre_con_la_fuente_repo_por_entorno(self):
        _salida, hilo = self.lanzar("ok")
        hilo.join(20)
        self.assertEqual((self.carpeta / ".cotejo" / "entorno").read_text(), "repo")

    def test_al_terminar_recibe_el_estado(self):
        recibidos = []
        _salida, hilo = self.lanzar("ok", al_terminar=recibidos.append)
        hilo.join(20)
        self.assertEqual([e["estado"] for e in recibidos], [preparacion.LISTO])

    def test_codigo_distinto_de_cero_es_fallo_con_acciones_y_salida(self):
        salida, hilo = self.lanzar("error")
        hilo.join(20)
        e = preparar.estado(salida["id"])
        self.assertEqual(e["estado"], preparacion.FALLO)
        self.assertEqual(e["codigo"], 3)
        self.assertEqual(e["acciones"], ["reintentar", "abrir_en_terminal"])
        self.assertIn("no tengo sesion", e["salida"])

    def test_cero_sin_tareas_tambien_es_fallo(self):
        salida, hilo = self.lanzar("vacio")
        hilo.join(20)
        e = preparar.estado(salida["id"])
        self.assertEqual(e["estado"], preparacion.FALLO)
        self.assertIn("sin crear ninguna tarea", e["por_que"])

    def test_si_no_vuelve_a_tiempo_se_para_y_es_fallo(self):
        self.config["motores"]["headless"]["timeout_seg"] = 1
        salida, hilo = self.lanzar("dormir")
        hilo.join(20)
        e = preparar.estado(salida["id"])
        self.assertEqual((e["estado"], e["codigo"]), (preparacion.FALLO, 124))
        self.assertFalse(procesos.vivo(salida["pid"]))

    # --- colgado ------------------------------------------------------------------------

    def test_colgado_sin_actividad_y_preparando_con_ella(self):
        salida, _hilo = self.lanzar("dormir")
        time.sleep(0.5)
        registro = preparacion.leer(salida["id"])
        ahora = time.time()
        self.assertEqual(preparacion.estado(registro, ahora, minutos=10)["estado"],
                         preparacion.PREPARANDO)
        colgado = preparacion.estado(registro, ahora + 11 * 60, minutos=10)
        self.assertEqual(colgado["estado"], preparacion.COLGADO)
        self.assertEqual(colgado["acciones"], ["reintentar", "abrir_en_terminal"])
        self.assertIn("11 minutos", colgado["por_que"])

    def test_los_minutos_salen_de_la_config(self):
        with mock.patch.object(preparacion.configuracion, "cargar",
                               return_value={"enrutador": {"preparar":
                                                           {"minutos_sin_actividad": 3}}}):
            self.assertEqual(preparacion.minutos_sin_actividad(), 3)
        with mock.patch.object(preparacion.configuracion, "cargar", return_value={}):
            self.assertEqual(preparacion.minutos_sin_actividad(),
                             preparacion.MINUTOS_SIN_ACTIVIDAD)

    def test_muerto_sin_volver_decide_lo_que_haya_en_la_carpeta(self):
        # Como `revisar` con un headless «perdido»: anotado al lanzar, nunca al terminar, y el
        # pid ya no existe (aquí, un proceso que ya acabó).
        acabado = subprocess.Popen([sys.executable, "-c", "pass"])
        acabado.wait()
        registro = {"id": "turnos-abc123", "proyecto": "turnos", "carpeta": str(self.carpeta),
                    "comando": [sys.executable], "log": ""}
        preparacion.anotar_lanzado(registro, acabado.pid, sys.executable)
        self.assertEqual(preparar.estado("turnos-abc123")["estado"], preparacion.FALLO)
        (self.carpeta / ".cotejo").mkdir(parents=True)
        (self.carpeta / ".cotejo" / "tareas.md").write_text("- [ ] Una: x\n")
        self.assertEqual(preparar.estado("turnos-abc123")["estado"], preparacion.LISTO)

    # --- reintentar y abrir en terminal -------------------------------------------------

    def test_reintentar_para_el_colgado_y_relanza_con_el_mismo_id(self):
        salida, _hilo = self.lanzar("dormir")
        viejo = salida["pid"]
        self.modo("ok")
        otra = preparar.reintentar(salida["id"], config=self.config)
        self.assertEqual(otra["id"], salida["id"])
        self.assertNotEqual(otra["pid"], viejo)
        self.assertEqual(otra["intentos"], 2)
        self.hilos[-1].join(20)
        self.assertEqual(preparar.estado(salida["id"])["estado"], preparacion.LISTO)
        for _ in range(50):
            if not procesos.vivo(viejo):
                break
            time.sleep(0.1)
        self.assertFalse(procesos.vivo(viejo))

    def test_el_hilo_del_proceso_viejo_no_pisa_al_nuevo(self):
        registro = {"id": "turnos-abc123", "proyecto": "turnos", "carpeta": str(self.carpeta)}
        preparacion.anotar_lanzado(registro, 4242, "claude")
        preparacion.anotar_terminado("turnos-abc123", -15, pid=1111)
        self.assertEqual(preparacion.leer("turnos-abc123")["fase"], "lanzado")

    def test_abrir_en_terminal_mismo_prompt_y_entorno(self):
        salida, _hilo = self.lanzar("dormir")
        registro = preparacion.leer(salida["id"])
        ensayo = preparar.abrir_en_terminal(salida["id"], config=self.config, simular=True)
        self.assertEqual(ensayo["comando"][:4],
                         ["terminal-falsa", "-e", sys.executable, str(self.script)])
        self.assertEqual(ensayo["comando"][-1], registro["prompt"])
        self.assertTrue(procesos.vivo(salida["pid"]))  # el ensayo no para nada
        with mock.patch.object(preparar.terminal, "abrir") as abrir:
            hecho = preparar.abrir_en_terminal(salida["id"], config=self.config)
        self.assertTrue(hecho["abierto"])
        _argv, _dir, entorno = abrir.call_args.args
        self.assertEqual(entorno, inicio.ENTORNO)
        self.assertEqual(preparar.estado(salida["id"])["estado"], preparacion.EN_TERMINAL)
        for _ in range(50):
            if not procesos.vivo(salida["pid"]):
                break
            time.sleep(0.1)
        self.assertFalse(procesos.vivo(salida["pid"]))

    # --- lo que se niega ----------------------------------------------------------------

    def test_respuestas_invalidas_o_cliente_que_falta(self):
        with self.assertRaises(preparar.NoSePuede):
            preparar.lanzar(inicio.Respuestas("", "x", str(self.carpeta)), cliente="claude",
                            config=self.config)
        self.config["motores"]["headless"]["comando"] = ["no-existe-este-cliente"]
        with self.assertRaises(preparar.NoSePuede) as error:
            preparar.lanzar(self.respuestas(), cliente="claude", config=self.config)
        self.assertIn("no-existe-este-cliente", str(error.exception))
        with self.assertRaises(preparar.NoSePuede):
            preparar.lanzar(self.respuestas(), cliente="otro", config=self.config)
        self.assertEqual(preparacion.todas(), [])

    # --- la barra -----------------------------------------------------------------------

    def test_la_barra_ve_lo_listo_y_deja_de_verlo_al_descartarlo(self):
        salida, hilo = self.lanzar("ok")
        hilo.join(20)
        datos = estado.resumir([])
        self.assertEqual(datos["preparaciones"],
                         [{"id": salida["id"], "proyecto": "turnos", "estado": "listo"}])
        preparar.descartar(salida["id"])
        self.assertNotIn("preparaciones", estado.resumir([]))


class Comando(unittest.TestCase):

    def test_por_cliente_como_el_headless(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {})
        claude = preparar.comando(config, clientes.de("claude"), "opus", "P")
        self.assertEqual(claude, ["claude", "-p", "--model", "opus", "--allowedTools",
                                  "Bash(cotejo:*)", "P"])
        self.assertEqual(preparar.comando(config, clientes.de("codex"), "", "P"),
                         ["codex", "exec", "P"])
        self.assertEqual(preparar.comando(config, clientes.de("gemini"), "g-2", "P"),
                         ["gemini", "-m", "g-2", "-p", "P"])

    def test_sin_modelo_no_hay_bandera_vacia(self):
        self.assertEqual(clientes.de("opencode").argv_sin_interfaz("", "P"),
                         ["opencode", "run", "P"])


if __name__ == "__main__":
    unittest.main()
