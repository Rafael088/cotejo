"""Lanzar desde el board (v1.3.0, cotejo-7xsjb8), sin GTK: `enrutador/despacho_board.py` y el
registro de `tareas/lanzados.py`.

Nunca se lanza un agente de verdad: el «cliente» es `cliente_falso.py`, que escribe unas líneas
como las de `claude -p --output-format stream-json` y termina. La máquina tampoco se mide: la
foto de `capacidad` es inventada, para que lo que cabe no dependa de quién corre las pruebas.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import capacidad, despacho_board
from tareas import lanzados, preparacion

FALSO = str(Path(__file__).resolve().parent / "cliente_falso.py")
HAY_GIT = shutil.which("git") is not None
FOTO_CON_HUECO = {"sistema": "linux", "cpus": 8, "carga": 0.5, "memoria_total_mb": 16000,
                  "memoria_disponible_mb": 12000, "swap_total_mb": 0, "swap_libre_mb": 0,
                  "agentes": []}


def git(carpeta, *args):
    return subprocess.run(["git", "-C", str(carpeta), "-c", "user.name=Prueba",
                           "-c", "user.email=p@p", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def esperar(condicion, segundos=10):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.05)
    return False


class ConClienteFalso(PruebaDeEnrutador):
    """Un vault con un proyecto cuyo repo es de verdad (para su worktree) y la config apuntada
    al cliente falso, sin systemd-run."""

    def setUp(self):
        super().setUp()
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.fuera = Path(fuera.name)
        self.repo = self.fuera / "repo"
        self.repo.mkdir()
        if HAY_GIT:
            git(self.repo, "init", "-q", "-b", "main")
            (self.repo / "LEEME").write_text("hola\n")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-q", "-m", "base")
        self.argv_falso = self.fuera / "argv.json"
        for parche in (mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.fuera / "estado"),
                                                    "FALSO_ARGV": str(self.argv_falso)}),
                       mock.patch.object(preparacion, "CARPETA",
                                         self.fuera / "estado" / "preparaciones"),
                       mock.patch.object(capacidad, "leer", return_value=dict(FOTO_CON_HUECO))):
            parche.start()
            self.addCleanup(parche.stop)
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo de los tags #agente/sonnet ^cotejo-asig",
            "- [ ] Revisar el contrato con el abogado #agente/persona ^cotejo-hum",
            "- [ ] Mejorar el mensaje de error del parser ^cotejo-sin",
            "- [ ] Ya la hace alguien #en-curso #agente/opus ^cotejo-curso"))
        self.configurar()

    def configurar(self, **extra):
        ajustes = {"proyectos": {"Uno": str(self.repo)},
                   "motores": {"headless": {"comando": [sys.executable, FALSO],
                                            "aislar": False}}}
        ajustes.update(extra)
        self.escribir_config(ajustes)

    def lanzar(self, tarea_id, **kwargs):
        return despacho_board.lanzar(tarea_id, **kwargs)


@unittest.skipUnless(HAY_GIT, "sin git")
class Lanzar(ConClienteFalso):
    def test_con_modelo_se_toma_se_aisla_y_se_lanza_con_su_cliente(self):
        terminado = []
        estado = self.lanzar("cotejo-asig", al_terminar=terminado.append)
        self.assertEqual(estado["estado"], lanzados.TRABAJANDO)
        self.assertEqual(estado["modelo"], "sonnet")
        self.assertIsInstance(estado["pid"], int)

        # La tarea quedó Haciéndola a nombre del modelo.
        self.assertIn("#en-curso #agente/sonnet ^cotejo-asig", self.leer_nota("Uno.md"))
        # El registro guarda lo que hace falta para seguirla, pararla o retomarla.
        registro = lanzados.leer("cotejo-asig")
        for clave in ("pid", "programa", "host", "log", "cliente", "modelo", "worktree",
                      "directorio", "comando", "prompt"):
            self.assertTrue(registro.get(clave), clave)
        self.assertEqual(registro["cliente"], "claude")
        self.assertEqual(registro["worktree"]["rama"], "cotejo/cotejo-asig")
        self.assertTrue(Path(registro["worktree"]["ruta"]).is_dir())

        self.assertTrue(esperar(lambda: terminado), "el cliente falso no terminó")
        self.assertEqual(terminado[0]["estado"], lanzados.TERMINADO)
        self.assertEqual(terminado[0]["codigo"], 0)

        # Se lanzó en su worktree, con su modelo, el encargo de siempre y el mismo cotejo.
        lanzado = json.loads(self.argv_falso.read_text())
        self.assertEqual(Path(lanzado["cwd"]).resolve(), Path(registro["worktree"]["ruta"]).resolve())
        argv = lanzado["argv"]
        self.assertEqual(argv[:3], ["-p", "--model", "sonnet"])
        self.assertIn("stream-json", argv)
        self.assertIn("acceptEdits", argv)
        self.assertEqual(argv[-2], "--")
        self.assertIn("cotejo-asig", argv[-1])
        self.assertIn("cotejo entregar cotejo-asig", argv[-1])
        self.assertTrue(lanzado["path"].split(os.pathsep)[0].endswith(os.path.join("agente", "bin")))

        # Lo que escribió el agente está en su log, y se lee en llano.
        seguimiento = lanzados.Seguimiento("cotejo-asig")
        texto = "\n".join(seguimiento.nuevas())
        for dicho in ("— Empezó con falso", "Voy a mirar el repo.", "→ Bash: git status",
                      "— Terminó: Listo."):
            self.assertIn(dicho, texto)
        self.assertEqual(seguimiento.nuevas(), [])

        # Las dos mitades en la bitácora de despachos, con su motor.
        fases = [(d.get("fase"), d.get("motor")) for d in self.despachados()]
        self.assertEqual(fases, [("lanzado", "board"), ("terminado", "board")])

    def test_sin_modelo_no_se_toma_y_trae_la_propuesta_con_su_porque(self):
        with self.assertRaises(despacho_board.FaltaModelo) as error:
            self.lanzar("cotejo-sin")
        self.assertTrue(error.exception.propuesta)
        self.assertTrue(error.exception.razon)
        self.assertIn(error.exception.propuesta, str(error.exception))
        self.assertIn("- [ ] Mejorar el mensaje de error del parser ^cotejo-sin",
                      self.leer_nota("Uno.md"))
        self.assertIsNone(lanzados.leer("cotejo-sin"))
        self.assertFalse(self.argv_falso.exists())
        self.assertEqual(self.despachados()[-1]["rechazo"], "falta_modelo")

    def test_n0_no_se_lanza(self):
        with self.assertRaises(despacho_board.EsDeUnaPersona):
            self.lanzar("cotejo-hum")
        self.assertIn("#agente/persona ^cotejo-hum", self.leer_nota("Uno.md"))
        self.assertNotIn("#en-curso #agente/persona", self.leer_nota("Uno.md"))
        self.assertIsNone(lanzados.leer("cotejo-hum"))
        self.assertFalse(self.argv_falso.exists())
        self.assertEqual(self.despachados()[-1]["rechazo"], "veto")

    def test_sin_hueco_no_se_lanza_y_queda_en_espera_con_el_motivo(self):
        # Un agente pesa más de lo que la máquina tiene libre: `capacidad` dice 0.
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        with self.assertRaises(despacho_board.SinHueco) as error:
            self.lanzar("cotejo-asig")
        self.assertIn("memoria", str(error.exception))
        self.assertIn("en espera", str(error.exception))
        # Sigue en Pendiente, sin tomar, y anotada en espera con el motivo.
        self.assertIn("- [ ] Arreglar el parseo de los tags #agente/sonnet ^cotejo-asig",
                      self.leer_nota("Uno.md"))
        self.assertFalse(self.argv_falso.exists())
        e = despacho_board.estado("cotejo-asig")
        self.assertEqual(e["estado"], lanzados.EN_ESPERA)
        self.assertEqual(lanzados.en_espera(), {"cotejo-asig": str(error.exception)})
        self.assertIn("En espera", lanzados.situacion(e))
        self.assertEqual(self.despachados()[-1]["rechazo"], "capacidad")

        # Con hueco otra vez, moverla la lanza y deja de estar en espera.
        self.configurar()
        self.assertEqual(self.lanzar("cotejo-asig")["estado"], lanzados.TRABAJANDO)
        self.assertEqual(lanzados.en_espera(), {})

    def test_lo_que_no_esta_pendiente_no_se_lanza(self):
        with self.assertRaises(despacho_board.NoSePuede):
            self.lanzar("cotejo-curso")
        self.assertFalse(self.argv_falso.exists())

    def test_sin_el_cliente_instalado_no_se_toma(self):
        self.configurar(motores={"headless": {"comando": ["no-existe-este-cliente"],
                                              "aislar": False}})
        with self.assertRaises(despacho_board.NoSePuede) as error:
            self.lanzar("cotejo-asig")
        self.assertIn("no-existe-este-cliente", str(error.exception))
        self.assertIn("- [ ] Arreglar el parseo de los tags #agente/sonnet ^cotejo-asig",
                      self.leer_nota("Uno.md"))

    def test_detener_para_el_agente_sin_tocar_la_tarea(self):
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            terminado = []
            self.lanzar("cotejo-asig", al_terminar=terminado.append)
        estado = despacho_board.detener("cotejo-asig", "lo pidió la persona")
        self.assertEqual(estado["estado"], lanzados.DETENIDO)
        self.assertTrue(esperar(lambda: terminado))
        # Volver no pisa el «detenido», y la tarea sigue donde estaba.
        self.assertEqual(despacho_board.estado("cotejo-asig")["estado"], lanzados.DETENIDO)
        self.assertIn("#en-curso #agente/sonnet ^cotejo-asig", self.leer_nota("Uno.md"))
        self.assertIsNone(despacho_board.detener("cotejo-nunca"))


class Legible(unittest.TestCase):
    def test_stream_json_en_llano_y_lo_demas_tal_cual(self):
        self.assertEqual(lanzados.legible("compilando…"), "compilando…")
        self.assertIsNone(lanzados.legible("   "))
        self.assertIsNone(lanzados.legible(json.dumps({"type": "user", "message": {}})))
        self.assertEqual(lanzados.legible(json.dumps(
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "a.py"}}]}})),
            "→ Edit: a.py")
        self.assertEqual(lanzados.legible(json.dumps(
            {"type": "result", "is_error": True, "result": "sin cuota"})),
            "— Terminó con un error: sin cuota")


class SeguimientoParcial(unittest.TestCase):
    def test_una_linea_a_medias_espera_a_la_siguiente_vuelta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            log = Path(carpeta) / "x.log"
            log.write_bytes(b"primera\nsegu")
            registro = {"id": "x", "log": str(log), "ts": 1, "log_desde": 0}
            s = lanzados.Seguimiento("x")
            self.assertEqual(s.nuevas(registro), ["primera"])
            with log.open("ab") as archivo:
                archivo.write(b"nda\n")
            self.assertEqual(s.nuevas(registro), ["segunda"])
            # Otro lanzamiento (otro ts) empieza donde empezó él.
            with log.open("ab") as archivo:
                archivo.write(b"tercera\n")
            otro = dict(registro, ts=2, log_desde=log.stat().st_size - len(b"tercera\n"))
            self.assertEqual(s.nuevas(otro), ["tercera"])


if __name__ == "__main__":
    unittest.main()
