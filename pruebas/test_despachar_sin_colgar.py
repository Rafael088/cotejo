"""`despachar` no deja tareas colgadas (cotejo-fyj565).

Visto probando el borrador 1.2.4 en un HOME vacío: `--motor sesion` sin `claude` tomaba la
tarea y respondía «Instancia abierta» con ok:false; un `claude` instalado pero sin sesión
(«Not logged in») dejaba la tarea «Haciéndola» a nombre del modelo y sin motivo; y el motivo de
ese fallo se quedaba pegado al despacho siguiente, que sí funcionaba, como si la tarea hubiera
vuelto atrás por el trabajo.

Todo se corre con el verbo entero y con el PATH de verdad cambiado —uno vacío, o uno con un
`claude` de mentira que sale con error—, no con `shutil.which` parcheado: es el PATH lo que
decide qué encuentra cada motor.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import verbos

SOLO_LINUX = unittest.skipUnless(sys.platform.startswith("linux"),
                                 "el cliente falso es un script sh")


class DespacharSinColgar(PruebaDeEnrutador):

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/sonnet ^cotejo-col"))
        self.bin = Path(tempfile.mkdtemp(dir=self.vault.parent))
        # Sin systemd-run de por medio: aquí se mira qué pasa con la tarea, no el aislamiento.
        self.escribir_config({"motores": {"headless": {"aislar": False}}})

    def con_path(self, *carpetas):
        """El PATH solo con estas carpetas (además de /bin para el sh de los scripts)."""
        parche = mock.patch.dict(os.environ, {"PATH": os.pathsep.join(
            [str(c) for c in carpetas] + ["/bin"])})
        parche.start()
        self.addCleanup(parche.stop)

    def cliente_claude(self, codigo, texto):
        cliente = self.bin / "claude"
        cliente.write_text(f"#!/bin/sh\necho '{texto}' >&2\nexit {codigo}\n", encoding="utf-8")
        cliente.chmod(0o755)

    def linea(self):
        return next(l for l in self.leer_nota("Uno.md").splitlines() if "cotejo-col" in l)

    # --- (1) sin el cliente, no se toma ------------------------------------------

    def test_sesion_sin_claude_no_toma_la_tarea(self):
        self.con_path(self.bin)   # una carpeta vacía: no hay claude
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "sesion")
        self.assertEqual(codigo, verbos.ERROR, datos)
        self.assertIn("No encontré «claude»", datos["error"])
        self.assertIn("sigue pendiente", datos["salida"])
        self.assertNotIn("Instancia abierta", str(datos))
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])
        self.assertEqual(self.despachados()[-1]["rechazo"], "motor")

    def test_headless_sin_cliente_tampoco(self):
        self.con_path(self.bin)
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "headless")
        self.assertEqual(codigo, verbos.ERROR, datos)
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])

    # --- (2) el cliente está pero falla: vuelve a Pendiente con el motivo ---------

    @SOLO_LINUX
    def test_headless_que_falla_suelta_la_tarea_con_lo_que_dijo_el_cliente(self):
        self.cliente_claude(1, "Not logged in · Please run /login")
        self.con_path(self.bin)
        codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "headless")
        self.assertEqual(codigo, verbos.ERROR, datos)
        self.assertTrue(datos["tomada"])
        self.assertTrue(datos["ejecutado"])
        self.assertFalse(datos["ok"])
        self.assertTrue(datos["soltada"])
        self.assertEqual(datos["tarea"]["estado"], "pendiente")
        self.assertIn("Se soltó", datos["nota_para_el_agente"])
        # Pendiente, sin #en-curso, y con la asignación que puso la persona.
        self.assertNotIn("#en-curso", self.linea())
        self.assertIn("#agente/sonnet", self.linea())
        soltar = self.operaciones()[-1]
        self.assertEqual(soltar["operacion"], "soltar")
        self.assertIn("Not logged in", soltar["motivo"])
        _, listado = self.correr("tareas")
        tarea, = [t for t in listado["tareas"] if t["id"] == "cotejo-col"]
        self.assertIn("Not logged in", tarea["motivo"])
        self.assertTrue(self.despachados()[-1]["soltada"])

    @SOLO_LINUX
    def test_sesion_que_falla_tampoco_dice_instancia_abierta(self):
        self.cliente_claude(1, "Not logged in · Please run /login")
        self.con_path(self.bin)
        codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "sesion")
        self.assertEqual(codigo, verbos.ERROR, datos)
        self.assertTrue(datos["soltada"])
        self.assertNotIn("Instancia abierta", datos["nota_para_el_agente"])
        self.assertNotIn("#en-curso", self.linea())

    @SOLO_LINUX
    def test_el_motivo_se_recorta(self):
        self.cliente_claude(1, "x" * 5000)
        self.con_path(self.bin)
        self.correr("despachar", "cotejo-col", "--motor", "headless")
        self.assertLess(len(self.operaciones()[-1]["motivo"]), 600)

    def test_si_el_cliente_la_entrego_antes_de_fallar_no_se_suelta(self):
        # Un cliente que entrega y después sale con error: la entrega se respeta. El cliente
        # es un `ejecutar` de mentira que entrega por la CLI de verdad antes de fallar.
        from enrutador import motor
        from enrutador.motores import claude_cli
        self.cliente_claude(0, "")   # para que `comprobar` lo encuentre en el PATH
        self.con_path(self.bin)

        def entrega_y_falla(_motor, _encargo):
            self.assertEqual(self.correr("entregar", "cotejo-col", "--evidencia", "hecho")[0], 0)
            return motor.Resultado(False, ["claude"], 3, error="se cayó al salir")

        with mock.patch.object(claude_cli.ClaudeCLI, "ejecutar", entrega_y_falla):
            codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "headless")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertFalse(datos["soltada"])
        self.assertIn("No se soltó", datos["nota_para_el_agente"])
        self.assertEqual(self.operaciones()[-1]["operacion"], "entregar")

    # --- (3) el motivo de un despacho fallido no se pega al siguiente -----------

    @SOLO_LINUX
    def test_tras_un_despacho_que_si_funciona_el_encargo_no_dice_que_volvio_atras(self):
        self.cliente_claude(1, "Not logged in · Please run /login")
        self.con_path(self.bin)
        self.correr("despachar", "cotejo-col", "--motor", "headless")
        codigo, datos = self.correr("despachar", "cotejo-col", "--motor", "agente")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertNotIn("volvió atrás", datos["salida"])
        self.assertNotIn("Not logged in", datos["salida"])
        _, listado = self.correr("tareas")
        tarea, = [t for t in listado["tareas"] if t["id"] == "cotejo-col"]
        self.assertNotIn("motivo", tarea)

    @SOLO_LINUX
    def test_el_motivo_de_un_rechazo_de_verdad_si_sigue_en_el_encargo(self):
        # Lo que se descarta es lo que dijo el cliente, no lo que dijo una persona antes.
        from tareas import bitacora, modelo
        proyecto_, tarea = modelo.buscar(self.escanear(), "cotejo-col")
        bitacora.anotar("rechazar", proyecto_, tarea, motivo="Falta el caso del archivo vacío")
        self.cliente_claude(1, "Not logged in")
        self.con_path(self.bin)
        self.correr("despachar", "cotejo-col", "--motor", "headless")
        _, datos = self.correr("despachar", "cotejo-col", "--motor", "agente")
        self.assertIn("volvió atrás", datos["salida"])
        self.assertIn("Falta el caso del archivo vacío", datos["salida"])
        self.assertNotIn("Not logged in", datos["salida"])

    # --- (4) con el motor por defecto, la nota dice que ya está tomada ------------

    def test_con_motor_agente_la_nota_dice_que_esta_tomada_y_como_devolverla(self):
        codigo, datos = self.correr("despachar", "cotejo-col")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertEqual(datos["motor"], "agente")
        nota = datos["nota_para_el_agente"]
        self.assertIn("ya quedó tomada", nota)
        self.assertIn("persona", nota)
        self.assertIn("cotejo bloquear cotejo-col", nota)


class UltimasTrasSoltar(unittest.TestCase):
    """La regla de `bitacora.ultimas()` sin vault: un `tomar` descarta el motivo de `soltar`."""

    def ultimas(self, *lineas):
        import json
        from tareas import bitacora
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / "bitacora.jsonl"
            archivo.write_text("".join(json.dumps(l) + "\n" for l in lineas), encoding="utf-8")
            with mock.patch.object(bitacora, "ARCHIVO", archivo):
                return bitacora.ultimas()

    def test_tomar_tras_soltar_recupera_lo_de_antes(self):
        ultimas = self.ultimas(
            {"operacion": "rechazar", "id": "cotejo-a", "motivo": "faltó algo"},
            {"operacion": "soltar", "id": "cotejo-a", "motivo": "Not logged in"},
            {"operacion": "soltar", "id": "cotejo-a", "motivo": "Not logged in otra vez"},
            {"operacion": "tomar", "id": "cotejo-a"},
        )
        self.assertEqual(ultimas["cotejo-a"]["motivo"], "faltó algo")

    def test_tomar_tras_soltar_sin_nada_antes_lo_deja_limpio(self):
        ultimas = self.ultimas(
            {"operacion": "soltar", "id": "cotejo-a", "motivo": "Not logged in"},
            {"operacion": "tomar", "id": "cotejo-a"},
        )
        self.assertNotIn("cotejo-a", ultimas)

    def test_mientras_sigue_pendiente_el_motivo_de_soltar_se_ve(self):
        ultimas = self.ultimas(
            {"operacion": "tomar", "id": "cotejo-a"},
            {"operacion": "soltar", "id": "cotejo-a", "motivo": "Not logged in"},
        )
        self.assertEqual(ultimas["cotejo-a"]["motivo"], "Not logged in")


if __name__ == "__main__":
    unittest.main()
