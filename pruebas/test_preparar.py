"""Preparar un proyecto en segundo plano (v1.3.0) sin lanzar ningún agente de verdad.

El «cliente» es un script de Python (`CLIENTE`) que hace lo que haría un agente con el prompt de
inicio: lee la carpeta del prompt, escribe en `.cotejo/` y sale. Qué hace lo decide un archivo
`modo` junto a la carpeta: `ok` (deja una tarea), `vacio` (sale bien sin dejar nada), `error`
(sale con 3) o `dormir` (no vuelve). Nada de red ni de clientes reales.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
import tareas
from unittest import mock

from apoyo import RAIZ  # noqa: F401
from enrutador import clientes, config as cfg, mismo_cotejo, preparar, procesos
from tareas import __version__, estado, inicio, preparacion, preparando

# Un Cotejo «instalado» de otra versión, primero en el PATH: el caso del dueño (el board del
# repo con el 1.2.5 instalado, sin `anotar --pieza`).
OTRO_COTEJO = textwrap.dedent('''\
    #!/bin/sh
    case "$1" in
      --version) echo "cotejo 0.9.0" ;;
      *) echo "usage: cotejo anotar [--tipo TIPO]" ;;
    esac
''')

CLIENTE = textwrap.dedent('''
    import json, os, re, shutil, subprocess, sys, time
    prompt = sys.argv[-1]
    carpeta = re.search(r"^Carpeta del proyecto: (.+)$", prompt, re.M).group(1)
    modo = open(os.path.join(os.path.dirname(carpeta), "modo")).read().strip()
    print("cliente falso, modo", modo, flush=True)
    os.makedirs(os.path.join(carpeta, ".cotejo"), exist_ok=True)
    with open(os.path.join(carpeta, ".cotejo", "entorno"), "w") as f:
        f.write(os.environ.get("COTEJO_FUENTE", ""))
    # Lo que el agente encuentra al llamar a `cotejo` por su nombre, como hace el de verdad.
    ruta = shutil.which("cotejo")
    def cotejo(*args):
        r = subprocess.run(["cotejo", *args], capture_output=True, text=True, timeout=60)
        return r.stdout + r.stderr
    with open(os.path.join(carpeta, ".cotejo", "cotejo.json"), "w") as f:
        json.dump({"ruta": ruta, "path": os.environ.get("PATH", ""),
                   "version": cotejo("--version").strip(),
                   "anotar": cotejo("anotar", "arquitectura", "--help")}, f)
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
        # El otro Cotejo, primero en el PATH de este proceso (el del board).
        self.otro_bin = self.base / "instalado"
        self.otro_bin.mkdir()
        otro = self.otro_bin / "cotejo"
        otro.write_text(OTRO_COTEJO)
        otro.chmod(0o755)
        parche = mock.patch.dict(os.environ, {
            "PATH": str(self.otro_bin) + os.pathsep + os.environ.get("PATH", "")})
        parche.start()
        self.addCleanup(parche.stop)

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

    def test_un_modelo_del_catalogo_prepara_con_su_cliente_y_sus_argumentos(self):
        # La interfaz manda un modelo concreto (`astra`) y el cliente sale de él, no del que
        # estuviera elegido en el desplegable.
        self.config["modelos"] = [
            {"clave": "astra", "modelo_id": "gpt-6-astra", "cliente": "codex", "nivel": "n3",
             "argumentos": ["-c", "model_reasoning_effort=high"]}]
        self.config["motores"]["headless"]["clientes"] = {
            "codex": {"comando": [sys.executable, str(self.script)]}}
        self.modo("ok")
        salida = preparar.lanzar(self.respuestas(), cliente="claude", modelo="astra",
                                 config=self.config)
        registro = preparacion.leer(salida["id"])
        self.assertEqual(registro["cliente"], "codex")
        self.assertEqual(registro["modelo"], "astra")
        comando = registro["comando"]
        self.assertIn("gpt-6-astra", comando)
        self.assertIn(("-c", "model_reasoning_effort=high"),
                      list(zip(comando, comando[1:])))
        self.hilos[-1].join(20)

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

    def test_reintentar_apunta_las_propuestas_previas_y_avisa_en_el_prompt(self):
        from tareas import almacen, reintento
        salida, _hilo = self.lanzar("dormir")
        self.assertNotIn(inicio.MARCA_REINTENTO, preparacion.leer(salida["id"])["prompt"])
        alm = almacen.Almacen(self.carpeta)
        propuesta = alm.crear("decision", "Stack", "x", temas=["stack"])
        aceptada = alm.crear("decision", "Datos", "x", temas=["datos"])
        alm.poner_estado(aceptada.id, aceptada.version, "aceptada")
        self.modo("ok")
        preparar.reintentar(salida["id"], config=self.config)
        self.hilos[-1].join(20)
        registro = preparacion.leer(salida["id"])
        self.assertEqual(registro["entorno"][reintento.ENV_PROPUESTAS_PREVIAS], propuesta.id)
        self.assertIn(inicio.MARCA_REINTENTO, registro["prompt"])
        # rehacer no arrastra la variable ni el aviso: es otra cosa
        preparar.rehacer(salida["id"], inicio.armar_rehacer(str(self.carpeta), "dec-aaaa", "T", "m"),
                         config=self.config, motivo="m")
        self.hilos[-1].join(20)
        registro = preparacion.leer(salida["id"])
        self.assertNotIn(reintento.ENV_PROPUESTAS_PREVIAS, registro["entorno"])
        self.assertNotIn(inicio.MARCA_REINTENTO, registro["prompt"])

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
        # En terminal es otra pasada: lo mismo, con el aviso de mirar antes lo que ya hay.
        self.assertEqual(ensayo["comando"][-1], inicio.para_reintento(registro["prompt"]))
        self.assertTrue(procesos.vivo(salida["pid"]))  # el ensayo no para nada
        with mock.patch.object(preparar.terminal, "abrir") as abrir:
            hecho = preparar.abrir_en_terminal(salida["id"], config=self.config)
        self.assertTrue(hecho["abierto"])
        _argv, _dir, entorno = abrir.call_args.args
        # Más el agente elegido, que `init` deja en proyecto.md (cotejo-qixs4j).
        self.assertEqual({k: v for k, v in entorno.items() if k != "PATH"},
                         {**inicio.ENTORNO, "COTEJO_AGENTE": registro["cliente"]})
        self.assertEqual(entorno["PATH"].split(os.pathsep)[0], str(mismo_cotejo.carpeta()))
        self.assertEqual(preparar.estado(salida["id"])["estado"], preparacion.EN_TERMINAL)
        for _ in range(50):
            if not procesos.vivo(salida["pid"]):
                break
            time.sleep(0.1)
        self.assertFalse(procesos.vivo(salida["pid"]))

    # --- el mismo cotejo que el board (cotejo-w7oeio) ------------------------------------

    def visto_por_el_agente(self):
        return json.loads((self.carpeta / ".cotejo" / "cotejo.json").read_text())

    def test_el_agente_llama_al_cotejo_del_board_y_no_al_otro(self):
        _salida, hilo = self.lanzar("ok")
        hilo.join(30)
        visto = self.visto_por_el_agente()
        bin_ = mismo_cotejo.carpeta()
        self.assertEqual(Path(visto["ruta"]).parent, bin_)
        self.assertEqual(visto["path"].split(os.pathsep)[0], str(bin_))
        self.assertIn(str(self.otro_bin), visto["path"])  # el otro sigue, solo que detrás
        self.assertEqual(visto["version"], f"cotejo {__version__}")
        self.assertIn("--pieza", visto["anotar"])  # el verbo que el instalado no tenía
        # Y ese `cotejo` corre el código de este proceso, no otro paquete.
        lanzador = (bin_ / "lanzador.py").read_text()
        self.assertIn(repr(str(Path(tareas.__file__).resolve().parent.parent)), lanzador)
        self.assertIn(sys.executable, (bin_ / "cotejo").read_text())

    def test_el_otro_de_otra_version_queda_anotado_y_preparando_lo_dice(self):
        salida, hilo = self.lanzar("ok")
        hilo.join(30)
        registro = preparacion.leer(salida["id"])
        self.assertEqual(registro["otro_cotejo"]["version"], "0.9.0")
        self.assertEqual(registro["otro_cotejo"]["ruta"], str(self.otro_bin / "cotejo"))
        self.assertEqual(registro["otro_cotejo"]["esta"], __version__)
        self.assertNotIn("PATH", registro["entorno"])  # el PATH se calcula al lanzar
        vista = preparando.Preparando(salida["id"]).refrescar()
        self.assertIn("otro Cotejo instalado (la versión 0.9.0)", vista.aviso)
        self.assertIn("no tienes que hacer nada", vista.aviso)

    def test_con_la_misma_version_no_hay_aviso(self):
        (self.otro_bin / "cotejo").write_text(
            OTRO_COTEJO.replace("0.9.0", __version__))
        salida, hilo = self.lanzar("ok")
        hilo.join(30)
        self.assertNotIn("otro_cotejo", preparacion.leer(salida["id"]))
        self.assertEqual(preparando.Preparando(salida["id"]).refrescar().aviso, "")

    def test_reintentar_y_rehacer_tambien_usan_el_del_board(self):
        salida, _hilo = self.lanzar("dormir")
        self.modo("ok")
        preparar.reintentar(salida["id"], config=self.config)
        self.hilos[-1].join(30)
        self.assertEqual(self.visto_por_el_agente()["version"], f"cotejo {__version__}")
        (self.carpeta / ".cotejo" / "cotejo.json").unlink()
        registro = preparacion.leer(salida["id"])
        preparar.rehacer(salida["id"], registro["prompt"], config=self.config, motivo="otra")
        self.hilos[-1].join(30)
        self.assertEqual(self.visto_por_el_agente()["version"], f"cotejo {__version__}")

    def test_abrir_en_terminal_resuelve_cotejo_al_del_board(self):
        salida, _hilo = self.lanzar("dormir")
        with mock.patch.object(preparar.terminal, "abrir") as abrir:
            preparar.abrir_en_terminal(salida["id"], config=self.config)
        _argv, _dir, entorno = abrir.call_args.args
        env = {**os.environ, **entorno}
        ruta = shutil.which("cotejo", path=env["PATH"])
        self.assertEqual(Path(ruta).parent, mismo_cotejo.carpeta())
        hecho = subprocess.run(["cotejo", "anotar", "arquitectura", "--help"], env=env, capture_output=True,
                               text=True, timeout=60)
        self.assertEqual(hecho.returncode, 0, hecho.stderr)
        self.assertIn("--pieza", hecho.stdout)
        # Sin el entorno del agente, el mismo PATH daría con el otro.
        self.assertEqual(shutil.which("cotejo"), str(self.otro_bin / "cotejo"))

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
                                  "Bash(cotejo:*)", "--", "P"])
        self.assertEqual(preparar.comando(config, clientes.de("codex"), "", "P"),
                         ["codex", "exec", "P"])
        # Gemini sin interfaz niega todo comando que pediría confirmación: como a Claude, se le
        # da solo el de correr `cotejo` (cotejo-p0fybl).
        self.assertEqual(preparar.comando(config, clientes.de("gemini"), "g-2", "P"),
                         ["gemini", "-m", "g-2", "--allowed-tools", "run_shell_command(cotejo)",
                          "-p", "P"])

    def test_sin_modelo_no_hay_bandera_vacia(self):
        self.assertEqual(clientes.de("opencode").argv_sin_interfaz("", "P"),
                         ["opencode", "run", "P"])

    def test_modelos_del_catalogo_llevan_id_y_argumentos(self):
        config = cfg._fundir(json.loads(json.dumps(cfg.DEFECTOS)), {
            "modelos": [
                {"clave": "astra", "modelo_id": "gpt-6-astra", "cliente": "codex",
                 "nivel": "n3", "argumentos": ["-c", "model_reasoning_effort=high"]},
                {"clave": "sol", "modelo_id": "gpt-5.6-sol", "cliente": "codex",
                 "nivel": "n2", "argumentos": ["-c", "model_reasoning_effort=medium"]},
            ]})
        self.assertEqual(preparar.comando(config, clientes.de("codex"), "astra", "P")[:6],
                         ["codex", "exec", "-m", "gpt-6-astra", "-c",
                          "model_reasoning_effort=high"])
        self.assertEqual(preparar.comando(config, clientes.de("codex"), "sol", "P")[:6],
                         ["codex", "exec", "-m", "gpt-5.6-sol", "-c",
                          "model_reasoning_effort=medium"])


if __name__ == "__main__":
    unittest.main()
