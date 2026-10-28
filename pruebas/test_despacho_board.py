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

from enrutador import bitacora as despachos_bitacora, capacidad, despacho_board
from tareas import lanzados, preparacion, retomar, worktrees

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
        # Ningún cliente falso se queda vivo al terminar (uno frenado por `lanzar_vivo` también
        # se para aquí, sin importar si la prueba lo soltó o no).
        self.addCleanup(lambda: [despacho_board.detener(i) for i in lanzados.todos()])
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

    def lanzar_vivo(self, tarea_id, **kwargs):
        """`lanzar` con el cliente falso frenado (espera a `FALSO_ESPERA_HASTA`): el estado
        «trabajando» que devuelve no depende de que el proceso no haya acabado aún de salir.
        Suéltalo con `soltar()` cuando ya no importe (o déjalo: el cleanup lo detiene)."""
        self.freno = self.fuera / "soltar"
        with mock.patch.dict(os.environ, {"FALSO_ESPERA_HASTA": str(self.freno)}):
            return self.lanzar(tarea_id, **kwargs)

    def soltar(self):
        """Deja salir al cliente falso frenado por `lanzar_vivo`."""
        self.freno.write_text("ya")


@unittest.skipUnless(HAY_GIT, "sin git")
class Lanzar(ConClienteFalso):
    def test_con_modelo_se_toma_se_aisla_y_se_lanza_con_su_cliente(self):
        terminado = []
        estado = self.lanzar_vivo("cotejo-asig", al_terminar=terminado.append)
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

        self.soltar()
        self.assertTrue(esperar(lambda: terminado), "el cliente falso no terminó")
        # Terminó sin entregar (cotejo-o253bs): vuelve a Pendiente, pausada para retomarla.
        self.assertEqual(terminado[0]["estado"], lanzados.DETENIDO)
        self.assertEqual(terminado[0]["fin"]["como"], lanzados.FIN_SIN_ENTREGAR)
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

    def test_la_ruta_de_despachos_se_resuelve_al_usar_y_no_al_importar(self):
        """cotejo-lr1vj6: calcularla al importar dejaba a las pruebas que cambian
        `COTEJO_ESTADO` después escribiendo en el archivo real de la persona."""
        with mock.patch.object(despachos_bitacora, "ARCHIVO", None), \
                mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.fuera)}):
            self.assertEqual(despachos_bitacora.ruta(), self.fuera / "despachos.jsonl")
            despachos_bitacora.anotar(tarea="cotejo-de-mentira")
            anotado = self.fuera / "despachos.jsonl"
            self.assertIn("cotejo-de-mentira", anotado.read_text(encoding="utf-8"))

    def test_el_terminado_va_a_la_bitacora_del_lanzamiento_aunque_la_ruta_cambie(self):
        """El hilo que vigila se queda con la ruta del lanzamiento: si la leyera al despertar,
        una prueba ya la habría devuelto a la de la persona y el «terminado» caería allí."""
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            terminado = []
            self.lanzar("cotejo-asig", al_terminar=terminado.append)
        with mock.patch.object(despachos_bitacora, "ARCHIVO",
                               Path("/proc/no-se-puede/despachos.jsonl")):
            despacho_board.detener("cotejo-asig", "lo pidió la prueba")
            self.assertTrue(esperar(lambda: terminado))
        self.assertEqual(self.despachados()[-1]["fase"], "terminado")

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
        self.assertEqual(self.lanzar_vivo("cotejo-asig")["estado"], lanzados.TRABAJANDO)
        self.assertEqual(lanzados.en_espera(), {})

    def test_lanzar_de_todos_modos_se_salta_la_capacidad_solo_esa_vez(self):
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        with self.assertRaises(despacho_board.SinHueco) as error:
            self.lanzar("cotejo-asig")
        # El aviso dice qué hacer, en llano, y nombra el botón.
        self.assertIn("Cierra algo", str(error.exception))
        self.assertIn("Lanzar de todos modos", str(error.exception))
        estado = self.lanzar_vivo("cotejo-asig", forzar=True)
        self.assertEqual(estado["estado"], lanzados.TRABAJANDO)
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


@unittest.skipUnless(HAY_GIT, "sin git")
class PausarYRetomar(ConClienteFalso):
    """Devolver a Pendiente pausa y conserva; volver a Haciendo lanza uno nuevo que retoma
    (cotejo-z7ma7r). El board mueve la línea; aquí se mueve a mano, como lo haría él."""

    def setUp(self):
        super().setUp()
        for parche in (mock.patch.object(worktrees, "REGISTRO", self.fuera / "estado" / "wt-reg"),
                       mock.patch.object(worktrees, "BASE", self.fuera / "wt")):
            parche.start()
            self.addCleanup(parche.stop)

    def a_pendiente(self, marca):
        """Lo que escribe el board al devolverla: quita `#en-curso` y deja el modelo."""
        nota = self.leer_nota("Uno.md").replace(f"#en-curso #agente/sonnet ^{marca}",
                                                f"#agente/sonnet ^{marca}")
        self.escribir_nota("Uno.md", nota)

    def test_pausar_conserva_y_volver_a_lanzar_retoma_con_la_nota(self):
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            terminado = []
            primero = self.lanzar("cotejo-asig", al_terminar=terminado.append)
            registro = lanzados.leer("cotejo-asig")
            self.assertTrue(esperar(lambda: "git status" in Path(registro["log"]).read_text()))
            # Pausar: el proceso se para y queda `detenido`; nada más se toca.
            estado = despacho_board.pausar("cotejo-asig")
            self.assertEqual(estado["estado"], lanzados.DETENIDO)
            self.assertTrue(esperar(lambda: terminado), "el agente no se paró")
            self.assertEqual(despacho_board.estado("cotejo-asig")["estado"], lanzados.DETENIDO)
            ruta = Path(registro["worktree"]["ruta"])
            self.assertTrue(ruta.is_dir())
            self.assertIn("cotejo/cotejo-asig", git(self.repo, "branch", "--list"))
            base = worktrees.de_tarea("cotejo-asig")["desde"]

            # El agente había dejado un commit y un archivo sin commitear.
            (ruta / "hecho.txt").write_text("listo\n")
            git(ruta, "add", "hecho.txt")
            git(ruta, "commit", "-q", "-m", "Primera mitad del arreglo")
            (ruta / "a-medias.txt").write_text("falta\n")
            self.a_pendiente("cotejo-asig")
            self.assertIn("#agente/sonnet ^cotejo-asig", self.leer_nota("Uno.md"))
            self.argv_falso.unlink()

            # Volver a Haciendo: otro agente, el mismo worktree, encargo + nota de retomar.
            segundo = self.lanzar_vivo("cotejo-asig")
        self.assertEqual(segundo["estado"], lanzados.TRABAJANDO)
        self.assertNotEqual(segundo["pid"], primero["pid"])
        self.assertIn("#en-curso #agente/sonnet ^cotejo-asig", self.leer_nota("Uno.md"))
        self.assertTrue(esperar(self.argv_falso.exists))
        self.assertTrue(esperar(lambda: self.argv_falso.read_text().endswith("}")))
        lanzado = json.loads(self.argv_falso.read_text())
        self.assertEqual(Path(lanzado["cwd"]).resolve(), ruta.resolve())
        prompt = lanzado["argv"][-1]
        self.assertIn("cotejo entregar cotejo-asig", prompt)            # el encargo
        self.assertIn(retomar.TITULO, prompt)                            # y la nota, después
        self.assertLess(prompt.index("cotejo entregar"), prompt.index(retomar.TITULO))
        self.assertIn("Primera mitad del arreglo", prompt)
        self.assertIn("?? a-medias.txt", prompt)
        self.assertIn("> Voy a mirar el repo.", prompt)
        self.assertIn("> → Bash: git status", prompt)
        self.assertIn("lo devolvieron a Pendiente", prompt)
        # La base de la rama no se movió al reutilizar el worktree.
        self.assertEqual(worktrees.de_tarea("cotejo-asig")["desde"], base)

        registro = lanzados.leer("cotejo-asig")
        self.assertEqual(registro["lanzamientos"], 2)
        self.assertEqual(registro["base"], base)
        r = registro["reanudacion"]
        self.assertEqual((r["vez"], r["anterior"], r["commits"], r["sin_commitear"]),
                         (2, "sonnet", 1, 1))
        self.assertTrue(registro["prompt"].endswith(r["nota"]))
        self.assertNotIn(retomar.TITULO, registro["encargo"])
        e = despacho_board.estado("cotejo-asig")
        self.assertIn("retomándola", lanzados.situacion(e))
        self.assertIn("Es una reanudación (vez 2)", retomar.resumen(e["reanudacion"]))
        self.assertIn("1 commit y 1 cambio sin commitear", retomar.resumen(e["reanudacion"]))

        # Pausar y retomar otra vez no apila notas: el encargo es el de siempre.
        despacho_board.pausar("cotejo-asig")
        self.a_pendiente("cotejo-asig")
        tercero = self.lanzar_vivo("cotejo-asig")
        prompt = lanzados.leer("cotejo-asig")["prompt"]
        self.assertEqual(prompt.count(retomar.TITULO), 1)
        self.assertEqual(lanzados.leer("cotejo-asig")["reanudacion"]["vez"], 3)
        self.assertEqual(tercero["estado"], lanzados.TRABAJANDO)

    def test_la_primera_vez_no_es_una_reanudacion(self):
        self.lanzar("cotejo-asig")
        registro = lanzados.leer("cotejo-asig")
        self.assertIsNone(registro["reanudacion"])
        self.assertNotIn(retomar.TITULO, registro["prompt"])
        self.assertEqual(registro["prompt"], registro["encargo"])

    def test_pausada_y_sin_hueco_no_pierde_lo_del_lanzamiento_anterior(self):
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.lanzar("cotejo-asig")
        despacho_board.pausar("cotejo-asig")
        self.a_pendiente("cotejo-asig")
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        with self.assertRaises(despacho_board.SinHueco):
            self.lanzar("cotejo-asig")
        registro = lanzados.leer("cotejo-asig")
        self.assertEqual(registro["fase"], lanzados.EN_ESPERA)
        self.assertTrue(retomar.es_retomable(registro))
        self.configurar()
        self.lanzar("cotejo-asig")
        self.assertIn("lo devolvieron a Pendiente", lanzados.leer("cotejo-asig")["prompt"])

    def test_pausar_lo_que_termino_sin_entregar_y_lo_que_nunca_se_lanzo(self):
        terminado = []
        self.lanzar("cotejo-asig", al_terminar=terminado.append)
        self.assertTrue(esperar(lambda: terminado))
        self.assertEqual(despacho_board.pausar("cotejo-asig")["estado"], lanzados.DETENIDO)
        self.assertIsNone(despacho_board.pausar("cotejo-nunca"))


class QuitarDeEspera(unittest.TestCase):
    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": carpeta.name})
        parche.start()
        self.addCleanup(parche.stop)

    def test_borra_el_registro_de_espera_y_nada_mas(self):
        lanzados.poner_en_espera({"id": "cotejo-esp", "proyecto": "Faro"}, "sonnet", "sin hueco")
        self.assertIn("cotejo-esp", lanzados.en_espera())
        self.assertTrue(lanzados.quitar_de_espera("cotejo-esp"))
        self.assertEqual(lanzados.en_espera(), {})
        self.assertIsNone(lanzados.leer("cotejo-esp"))
        self.assertFalse(lanzados.quitar_de_espera("cotejo-esp"))

    def test_si_ya_se_lanzo_antes_vuelve_a_detenida_con_su_motivo_de_entonces(self):
        lanzados.guardar({"id": "cotejo-esp", "fase": lanzados.DETENIDO, "motivo": "la paré",
                          "pid": 7, "log": "/tmp/x.log"})
        lanzados.poner_en_espera({"id": "cotejo-esp"}, "sonnet", "sin hueco")
        self.assertTrue(lanzados.quitar_de_espera("cotejo-esp"))
        registro = lanzados.leer("cotejo-esp")
        self.assertEqual((registro["fase"], registro["motivo"]), (lanzados.DETENIDO, "la paré"))
        self.assertNotIn("motivo_antes", registro)
        self.assertEqual(lanzados.en_espera(), {})

    def test_no_toca_una_lanzada_o_inexistente(self):
        lanzados.guardar({"id": "cotejo-viv", "fase": lanzados.LANZADO, "pid": 1, "log": "x"})
        self.assertFalse(lanzados.quitar_de_espera("cotejo-viv"))
        self.assertEqual(lanzados.leer("cotejo-viv")["fase"], lanzados.LANZADO)
        self.assertFalse(lanzados.quitar_de_espera("cotejo-nada"))


class NotaDeRetomar(unittest.TestCase):
    def test_sin_git_ni_log_dice_lo_que_hay_y_no_falla(self):
        with tempfile.TemporaryDirectory() as carpeta:
            log = Path(carpeta) / "x.log"
            log.write_text("viejo\n" + json.dumps({"type": "assistant", "message": {
                "content": [{"type": "text", "text": "Quedé en el parser."}]}}) + "\n")
            registro = {"id": "x", "modelo": "haiku", "log": str(log), "log_desde": 6,
                        "trabajo": carpeta, "pid": 1}
            texto = retomar.nota(registro, motivo="se paró a mano")
        self.assertIn(retomar.TITULO, texto)
        self.assertIn("(haiku)", texto)
        self.assertIn("se paró a mano", texto)
        self.assertIn("> Quedé en el parser.", texto)
        self.assertNotIn("viejo", texto)            # lo de antes de su lanzamiento, no
        self.assertNotIn("Commits", texto)          # no es un repo: no se inventa nada
        self.assertEqual(retomar.nota(None).count(retomar.TITULO), 1)
        self.assertFalse(retomar.es_retomable({"fase": "en-espera"}))


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
