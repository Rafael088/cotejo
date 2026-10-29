"""El fin y el rechazo de un agente lanzado desde el board (v1.3.0, cotejo-o253bs), sin GTK.

De punta a punta con el cliente falso (`cliente_falso.py`), que nunca llama a un modelo: cuando
entrega lo hace de verdad, con un commit en su worktree y el `cotejo entregar` que el board le
puso en el PATH. Por eso la bitácora y el registro de worktrees de esta prueba son los de
`COTEJO_ESTADO`: los mismos que ve ese `cotejo` en otro proceso.

Lo que se vigila: el que entrega queda en Para comprobar con sus mensajes guardados; el que
termina o muere sin entregar vuelve a Pendiente con el motivo en llano y el worktree; devolver
con motivo de Para comprobar a Haciendo lanza uno nuevo en el mismo worktree con el encargo, la
entrega anterior y lo que se pidió cambiar; nunca hay dos vivos y nada se relanza solo.
"""

import json
import os
import signal
import time
import unittest
from pathlib import Path
from unittest import mock

from test_despacho_board import HAY_GIT, ConClienteFalso, esperar

from enrutador import cotejo as f, despacho_board
from tareas import ahorro, bitacora, estado, lanzados, retomar, worktrees

ID = "cotejo-asig"


def vive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # Un hijo ya muerto que nadie recogió sigue en la tabla: para esto cuenta como muerto.
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as archivo:
            return archivo.read().split(") ")[-1][:1] != "Z"
    except OSError:
        return True


@unittest.skipUnless(HAY_GIT, "sin git")
class FinYRechazo(ConClienteFalso):
    def setUp(self):
        super().setUp()
        estado_dir = self.fuera / "estado"
        self.bitacora = estado_dir / "bitacora.jsonl"     # la que lee `operaciones()`
        for objetivo, atributo, valor in (
                (bitacora, "ARCHIVO", estado_dir / "bitacora.jsonl"),
                (estado, "ARCHIVO", estado_dir / "estado.json"),
                (ahorro, "ARCHIVO", estado_dir / "ahorro.json"),
                (worktrees, "REGISTRO", estado_dir / "worktrees"),
                (worktrees, "BASE", estado_dir / "wt")):
            parche = mock.patch.object(objetivo, atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.addCleanup(despacho_board.esperar_vigilantes)
        self.addCleanup(lambda: [despacho_board.detener(i) for i in lanzados.todos()])

    # --- ayudas -----------------------------------------------------------------------------

    def lanzar_con(self, **entorno):
        terminado = []
        with mock.patch.dict(os.environ, {k: str(v) for k, v in entorno.items()}):
            primero = self.lanzar(ID, al_terminar=terminado.append)
        return primero, terminado

    def columna(self):
        return f.Cotejo().tarea(ID)["estado"]

    def linea(self):
        return next(l for l in self.leer_nota("Uno.md").splitlines() if f"^{ID}" in l)

    def ultima(self, operacion):
        return [a for a in self.operaciones() if a.get("operacion") == operacion][-1]

    def mover_a_haciendo(self, motivo):
        """Lo que escribe el board al devolverla: la línea a Haciendo y el «rechazar»."""
        llamadas = []

        def mover():
            llamadas.append(1)
            fuente = self.fuente
            for uno in fuente.escanear(incluir_hechas=True):
                for tarea in uno.tareas:
                    if tarea.id == ID:
                        actual = fuente.poner_estado(tarea, "en-curso")
                        bitacora.anotar("rechazar", uno, actual, de="por-validar",
                                        a="en-curso", motivo=motivo)
                        return True
            return False
        mover.llamadas = llamadas
        return mover

    def entregada(self, **entorno):
        """Lanza un agente que entrega y espera a que vuelva."""
        primero, terminado = self.lanzar_con(FALSO_ENTREGAR=ID, **entorno)
        return primero, terminado

    def argv(self):
        self.assertTrue(esperar(lambda: self.argv_falso.exists()
                                and self.argv_falso.read_text().endswith("}")))
        return json.loads(self.argv_falso.read_text())

    # --- el fin -----------------------------------------------------------------------------

    def test_el_que_entrega_queda_en_para_comprobar_con_sus_mensajes(self):
        primero, terminado = self.entregada()
        self.assertTrue(esperar(lambda: terminado, 30), "el agente no volvió")
        self.assertEqual(self.columna(), "por-validar")
        entrega = bitacora.ultima_entrega(ID)
        self.assertEqual(entrega["resumen"], "Arreglé el parseo.")
        registro = lanzados.leer(ID)
        self.assertEqual(registro["fase"], lanzados.TERMINADO)
        self.assertEqual(registro["fin"]["como"], lanzados.FIN_ENTREGO)
        self.assertIn("entregó", lanzados.situacion(terminado[0]))
        # Su proceso se cerró solo y sus mensajes siguen en su log.
        self.assertFalse(vive(primero["pid"]))
        texto = "\n".join(lanzados.Seguimiento(ID).nuevas())
        for dicho in ("Voy a mirar el repo.", "Entregué (código 0).", "— Terminó: Listo."):
            self.assertIn(dicho, texto)
        # Ni se devolvió ni se tocó su worktree.
        self.assertFalse([a for a in self.operaciones() if a.get("operacion") == "soltar"])
        self.assertTrue(Path(registro["worktree"]["ruta"]).is_dir())

    def test_el_que_termina_sin_entregar_vuelve_a_pendiente_y_no_se_relanza(self):
        primero, terminado = self.lanzar_con()
        self.assertTrue(esperar(lambda: terminado, 20))
        # Pendiente, con su modelo, y el motivo en llano con lo último que dijo.
        self.assertEqual(self.columna(), "pendiente")
        self.assertIn("#agente/sonnet", self.linea())
        soltada = self.ultima("soltar")
        self.assertIn("El agente terminó sin entregar", soltada["motivo"])
        self.assertIn("«Voy a mirar el repo.»", soltada["motivo"])
        self.assertIn("Listo.", soltada["motivo"])
        self.assertEqual(f.Cotejo().tarea(ID)["motivo"], soltada["motivo"])
        # Pausada, con su worktree y su rama para retomarla.
        registro = lanzados.leer(ID)
        self.assertEqual(registro["fase"], lanzados.DETENIDO)
        self.assertEqual(registro["motivo"], despacho_board.SIN_ENTREGAR)
        self.assertEqual(registro["fin"]["como"], lanzados.FIN_SIN_ENTREGAR)
        self.assertTrue(Path(registro["worktree"]["ruta"]).is_dir())
        self.assertIsNotNone(worktrees.de_tarea(ID))
        self.assertIn("terminó sin entregar", lanzados.situacion(terminado[0]))
        # Nada la relanza sola, ni el refresco del board.
        self.assertEqual(despacho_board.recoger(), [])
        time.sleep(0.5)
        self.assertEqual(lanzados.leer(ID)["pid"], primero["pid"])
        self.assertEqual(lanzados.leer(ID)["lanzamientos"], 1)
        self.assertEqual(len([d for d in self.despachados() if d.get("fase") == "lanzado"]), 1)

        # Pasarla a Haciendo la retoma (z7ma7r) sabiendo por qué se paró el anterior.
        self.argv_falso.unlink()
        self.lanzar(ID)
        prompt = self.argv()["argv"][-1]
        self.assertIn(retomar.TITULO, prompt)
        self.assertIn(despacho_board.SIN_ENTREGAR, prompt)

    def test_el_que_sale_con_error_lo_dice_en_el_motivo(self):
        _, terminado = self.lanzar_con(FALSO_CODIGO=3)
        self.assertTrue(esperar(lambda: terminado, 20))
        self.assertEqual(self.columna(), "pendiente")
        self.assertIn("código 3", self.ultima("soltar")["motivo"])

    def test_el_que_muere_con_el_board_cerrado_se_recoge_una_vez(self):
        procesos = []
        with mock.patch.object(despacho_board, "vigilar",
                               lambda proceso, *a, **k: procesos.append(proceso)):
            primero, _ = self.lanzar_con(FALSO_ESPERA=30)
        proceso = procesos[0]
        registro = lanzados.leer(ID)
        self.assertTrue(esperar(lambda: "git status" in Path(registro["log"]).read_text()))
        # Mientras vive, recoger no lo toca.
        self.assertEqual(despacho_board.recoger(), [])
        self.assertEqual(self.columna(), "en-curso")
        os.kill(proceso.pid, signal.SIGKILL)
        proceso.wait()
        self.assertEqual(despacho_board.estado(ID)["estado"], lanzados.MURIO)

        self.assertEqual(despacho_board.recoger(), [ID])
        self.assertEqual(self.columna(), "pendiente")
        motivo = self.ultima("soltar")["motivo"]
        self.assertIn("El agente terminó sin entregar", motivo)
        self.assertIn("se cerró sin que nadie lo viera", motivo)
        self.assertIn("«→ Bash: git status»", motivo)
        registro = lanzados.leer(ID)
        self.assertEqual((registro["fase"], registro["fin"]["como"]),
                         (lanzados.DETENIDO, lanzados.FIN_SIN_ENTREGAR))
        self.assertTrue(Path(registro["worktree"]["ruta"]).is_dir())
        # Una sola vez: otra recogida no escribe nada.
        antes = len(self.operaciones())
        self.assertEqual(despacho_board.recoger(), [])
        self.assertEqual(len(self.operaciones()), antes)
        self.assertEqual(lanzados.leer(ID)["pid"], primero["pid"])

    def test_si_lo_bloqueo_el_fin_no_lo_toca(self):
        procesos = []
        with mock.patch.object(despacho_board, "vigilar",
                               lambda proceso, *a, **k: procesos.append(proceso)):
            self.lanzar_con()
        procesos[0].wait()
        codigo, _ = self.correr("bloquear", ID, "--motivo", "falta acceso")
        self.assertEqual(codigo, 0)
        self.assertEqual(despacho_board.recoger(), [ID])
        self.assertEqual(lanzados.leer(ID)["fin"]["como"], lanzados.FIN_OTRO)
        self.assertFalse([a for a in self.operaciones() if a.get("operacion") == "soltar"])

    # --- el rechazo -------------------------------------------------------------------------

    def test_rechazar_lanza_uno_nuevo_en_el_mismo_worktree_con_lo_que_se_pidio_cambiar(self):
        primero, terminado = self.entregada()
        self.assertTrue(esperar(lambda: terminado, 30))
        self.assertEqual(self.columna(), "por-validar")
        ruta = Path(lanzados.leer(ID)["worktree"]["ruta"])
        self.argv_falso.unlink()

        mover = self.mover_a_haciendo("Falta el caso del archivo vacío.")
        segundos = []
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "1.5"}):
            segundo = despacho_board.rechazar(ID, "Falta el caso del archivo vacío.", mover,
                                              al_terminar=segundos.append)
        self.assertEqual(mover.llamadas, [1])
        self.assertEqual(segundo["estado"], lanzados.TRABAJANDO)
        self.assertNotEqual(segundo["pid"], primero["pid"])
        self.assertEqual(self.columna(), "en-curso")
        self.assertIn("#agente/sonnet", self.linea())
        lanzado = self.argv()
        self.assertEqual(Path(lanzado["cwd"]).resolve(), ruta.resolve())
        prompt = lanzado["argv"][-1]
        # El encargo, la nota de retomar y, al final, lo que se pidió cambiar con la entrega.
        for dicho in ("cotejo entregar cotejo-asig", retomar.TITULO, retomar.TITULO_RECHAZO,
                      "Falta el caso del archivo vacío.", "Resumen: Arreglé el parseo.",
                      "Evidencia: commit del falso", "Commit: ", "Arreglo del falso"):
            self.assertIn(dicho, prompt)
        self.assertLess(prompt.index(retomar.TITULO), prompt.index(retomar.TITULO_RECHAZO))
        # El motivo va una vez, en su sitio, no repetido por el encargo.
        self.assertEqual(prompt.count("Falta el caso del archivo vacío."), 1)
        registro = lanzados.leer(ID)
        self.assertEqual(registro["lanzamientos"], 2)
        self.assertEqual(registro["worktree"]["ruta"], str(ruta))
        self.assertEqual(registro["reanudacion"]["rechazo"], "Falta el caso del archivo vacío.")
        self.assertIn("Se la devolvieron desde Para comprobar",
                      retomar.resumen(registro["reanudacion"]))
        self.assertNotIn(retomar.TITULO_RECHAZO, registro["encargo"])

        # Si este tampoco entrega, vuelve a Pendiente (con su worktree) y no se lanza un tercero.
        self.assertTrue(esperar(lambda: segundos, 15))
        self.assertEqual(self.columna(), "pendiente")
        self.assertEqual(lanzados.leer(ID)["fin"]["como"], lanzados.FIN_SIN_ENTREGAR)
        self.assertTrue(ruta.is_dir())
        self.assertEqual(despacho_board.recoger(), [])
        self.assertEqual(lanzados.leer(ID)["lanzamientos"], 2)

    def test_rechazar_con_el_anterior_vivo_lo_para_y_nunca_hay_dos(self):
        primero, terminado = self.entregada(FALSO_ESPERA_FIN=30)
        self.assertTrue(esperar(lambda: self.columna() == "por-validar", 30))
        self.assertTrue(vive(primero["pid"]))         # entregó, pero sigue vivo
        mover = self.mover_a_haciendo("Otra cosa.")
        segundos = []
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            segundo = despacho_board.rechazar(ID, "Otra cosa.", mover,
                                              al_terminar=segundos.append)
        self.assertTrue(esperar(lambda: not vive(primero["pid"])), "el anterior sigue vivo")
        self.assertTrue(vive(segundo["pid"]))
        self.assertTrue(esperar(lambda: terminado, 15))
        # El hilo del anterior volvió y no la tomó por una que terminó sin entregar.
        time.sleep(0.3)
        self.assertEqual(self.columna(), "en-curso")
        self.assertEqual(lanzados.leer(ID)["pid"], segundo["pid"])
        self.assertEqual(lanzados.leer(ID)["fase"], lanzados.LANZADO)
        self.assertFalse([a for a in self.operaciones() if a.get("operacion") == "soltar"])

    def test_rechazar_sin_hueco_la_deja_en_pendiente_con_el_rechazo_guardado(self):
        _, terminado = self.entregada()
        self.assertTrue(esperar(lambda: terminado, 30))
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        with self.assertRaises(despacho_board.SinHueco) as error:
            despacho_board.rechazar(ID, "Falta el caso vacío.", self.mover_a_haciendo("x"))
        self.assertIn("La devolví a Pendiente", str(error.exception))
        self.assertEqual(self.columna(), "pendiente")
        self.assertIn("#agente/sonnet", self.linea())
        registro = lanzados.leer(ID)
        self.assertEqual(registro["fase"], lanzados.EN_ESPERA)
        self.assertEqual(registro["rechazo"]["motivo"], "Falta el caso vacío.")
        # Con hueco, pasarla a Haciendo lleva lo que se pidió cambiar.
        self.configurar()
        self.argv_falso.unlink()
        self.lanzar(ID)
        prompt = self.argv()["argv"][-1]
        self.assertIn(retomar.TITULO_RECHAZO, prompt)
        self.assertIn("Falta el caso vacío.", prompt)

    def poner_estado(self, tarea_id, estado):
        for uno in self.fuente.escanear(incluir_hechas=True):
            for tarea in uno.tareas:
                if tarea.id == tarea_id:
                    return self.fuente.poner_estado(tarea, estado)
        self.fail(tarea_id)

    def test_rechazar_una_de_una_persona_no_mueve_ni_lanza(self):
        self.poner_estado("cotejo-hum", "por-validar")
        mover = self.mover_a_haciendo("x")
        self.assertIsNone(despacho_board.rechazar("cotejo-hum", "x", mover))
        self.assertEqual(mover.llamadas, [])
        self.assertIsNone(lanzados.leer("cotejo-hum"))

    def test_rechazar_una_asignada_que_no_lanzo_el_board_tambien_lanza_a_su_agente(self):
        # Entregada por otro camino (`despachar`, a mano): en Para comprobar, sin registro.
        self.poner_estado(ID, "por-validar")
        self.assertIsNone(lanzados.leer(ID))
        mover = self.mover_a_haciendo("Falta el caso vacío.")
        segundos = []
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "1"}):
            estado = despacho_board.rechazar(ID, "Falta el caso vacío.", mover,
                                             al_terminar=segundos.append)
        self.assertEqual(mover.llamadas, [1])
        self.assertEqual(estado["estado"], lanzados.TRABAJANDO)
        self.assertEqual(estado["modelo"], "sonnet")
        self.assertEqual(self.columna(), "en-curso")
        self.assertIn("#agente/sonnet", self.linea())
        prompt = self.argv()["argv"][-1]
        self.assertIn("cotejo entregar cotejo-asig", prompt)
        self.assertIn(retomar.TITULO_RECHAZO, prompt)
        self.assertNotIn(retomar.TITULO, prompt.replace(retomar.TITULO_RECHAZO, ""))
        self.assertEqual(prompt.count("Falta el caso vacío."), 1)
        registro = lanzados.leer(ID)
        self.assertEqual(registro["rechazo"]["motivo"], "Falta el caso vacío.")
        self.assertEqual(registro["reanudacion"]["rechazo"], "Falta el caso vacío.")
        self.assertTrue(esperar(lambda: segundos, 15))

    def test_rechazar_sin_hueco_una_que_no_lanzo_el_board_guarda_el_rechazo(self):
        self.poner_estado(ID, "por-validar")
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        with self.assertRaises(despacho_board.SinHueco):
            despacho_board.rechazar(ID, "Falta el caso vacío.", self.mover_a_haciendo("x"))
        self.assertEqual(self.columna(), "pendiente")
        self.assertEqual(lanzados.leer(ID)["rechazo"]["motivo"], "Falta el caso vacío.")
        self.configurar()
        self.lanzar(ID)
        prompt = self.argv()["argv"][-1]
        self.assertIn(retomar.TITULO_RECHAZO, prompt)
        self.assertIn("Falta el caso vacío.", prompt)


class RechazoVigente(unittest.TestCase):
    def test_una_entrega_nueva_lo_deja_atras(self):
        r = retomar.rechazo("Falta X.", {"resumen": "hice", "cuando": 100}, ahora=200)
        self.assertEqual(r["entrega"], ["Resumen: hice"])
        self.assertIs(retomar.rechazo_vigente({"rechazo": r}, {"cuando": 150}), r)
        self.assertIs(retomar.rechazo_vigente({"rechazo": r}, {"cuando": 200}), r)
        self.assertIsNone(retomar.rechazo_vigente({"rechazo": r}, {"cuando": 201}))
        self.assertIsNone(retomar.rechazo_vigente({}, None))


if __name__ == "__main__":
    unittest.main()
