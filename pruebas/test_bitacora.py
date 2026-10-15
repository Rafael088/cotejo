"""La bitácora: lo que se anota, lo que se lee de vuelta y lo que no debe romperla.

Lo que se prueba aquí no es el formato por el formato: es que el texto libre llegue de quien
lo escribe a quien tiene que leerlo. Una evidencia que no vuelve deja la columna «Para
comprobar» tan ciega como antes, y un motivo de rechazo que no vuelve deja al agente
repitiendo la misma entrega.
"""

import json
import unittest
from unittest import mock

from apoyo import PruebaDeCLI, proyecto


class PruebaDeBitacora(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Una tarea cualquiera",
            "- [ ] Otra tarea más",
        ))

    def anotar(self, operacion, texto_tarea="Una tarea cualquiera", **extra):
        from tareas import bitacora
        uno, tareas = self.tareas_de("Uno")
        tarea = next(t for t in tareas if t.texto == texto_tarea)
        return bitacora.anotar(operacion, uno, tarea, **extra)

    def escribir_lineas(self, *lineas):
        with self.bitacora.open("w", encoding="utf-8") as archivo:
            for linea in lineas:
                archivo.write((linea if isinstance(linea, str)
                               else json.dumps(linea, ensure_ascii=False)) + "\n")

    def ultimas(self):
        from tareas import bitacora
        return bitacora.ultimas()


class Anotar(PruebaDeBitacora):
    def test_anotar_deja_una_linea_json_con_la_tarea_y_lo_extra(self):
        self.assertTrue(self.anotar("entregar", evidencia="128 pruebas, commit abc1234"))
        anotaciones = self.operaciones()
        self.assertEqual(len(anotaciones), 1)
        self.assertEqual(anotaciones[0]["operacion"], "entregar")
        self.assertEqual(anotaciones[0]["texto"], "Una tarea cualquiera")
        self.assertEqual(anotaciones[0]["nota"], "01-Proyectos/Uno.md")
        self.assertEqual(anotaciones[0]["proyecto"], "Uno")
        self.assertEqual(anotaciones[0]["evidencia"], "128 pruebas, commit abc1234")
        self.assertIsInstance(anotaciones[0]["cuando"], int)

    def test_anotar_solo_agrega_nunca_reescribe(self):
        self.anotar("tomar")
        self.anotar("entregar", evidencia="lo primero")
        self.anotar("rechazar", motivo="lo segundo")
        self.assertEqual([a["operacion"] for a in self.operaciones()],
                         ["tomar", "entregar", "rechazar"])

    def test_que_no_se_pueda_escribir_no_revienta_pero_lo_dice(self):
        """La tarea ya está escrita en la nota cuando esto corre: el estado no puede depender
        de que la bitácora llegue al disco. Callarse el fallo sí, perder la tarea no."""
        self.bitacora.parent.chmod(0o500)
        self.addCleanup(self.bitacora.parent.chmod, 0o700)
        self.assertFalse(self.anotar("entregar", evidencia="algo"))


class Ultimas(PruebaDeBitacora):
    def test_sin_archivo_no_hay_nada_y_no_falla(self):
        self.assertEqual(self.ultimas(), {})

    def test_se_queda_con_lo_ultimo_de_cada_tarea(self):
        self.escribir_lineas(
            {"cuando": 1, "operacion": "entregar", "id": "cotejo-aaa", "evidencia": "primera"},
            {"cuando": 2, "operacion": "rechazar", "id": "cotejo-aaa", "motivo": "faltó algo"},
            {"cuando": 3, "operacion": "entregar", "id": "cotejo-bbb", "evidencia": "otra tarea"},
        )
        ultimas = self.ultimas()
        self.assertEqual(ultimas["cotejo-aaa"]["motivo"], "faltó algo")
        self.assertNotIn("evidencia", ultimas["cotejo-aaa"])
        self.assertEqual(ultimas["cotejo-bbb"]["evidencia"], "otra tarea")

    def test_las_anotaciones_sin_texto_libre_no_tapan_a_las_que_lo_tienen(self):
        """Tomar o mover una tarea son historial, pero no tienen nada que enseñar en la carta:
        si contaran, tomar una tarea devuelta borraría el motivo por el que se devolvió."""
        self.escribir_lineas(
            {"cuando": 1, "operacion": "rechazar", "id": "cotejo-aaa", "motivo": "faltó algo"},
            {"cuando": 2, "operacion": "tomar", "id": "cotejo-aaa"},
            {"cuando": 3, "operacion": "mover", "id": "cotejo-aaa", "de": "pendiente", "a": "en-curso"},
        )
        self.assertEqual(self.ultimas()["cotejo-aaa"]["motivo"], "faltó algo")

    def test_una_linea_rota_no_se_lleva_por_delante_al_resto(self):
        self.escribir_lineas(
            {"cuando": 1, "operacion": "entregar", "id": "cotejo-aaa", "evidencia": "buena"},
            "{esto no es json",
            "",
            '"una cadena suelta"',
            "[1, 2, 3]",
            {"cuando": 2, "operacion": "entregar", "evidencia": "sin id, no se puede usar"},
            {"cuando": 3, "operacion": "entregar", "id": "cotejo-bbb", "evidencia": "también buena"},
        )
        self.assertEqual(sorted(self.ultimas()), ["cotejo-aaa", "cotejo-bbb"])

    def test_con_el_archivo_enorme_se_lee_la_cola_y_la_linea_partida_se_descarta(self):
        """El archivo solo crece y esto se llama en cada repintado del board. Se lee la cola,
        que es donde está lo último de cada tarea; la línea que el corte parte a la mitad se
        tira entera en vez de intentar completarla."""
        from tareas import bitacora
        relleno = [{"cuando": i, "operacion": "entregar", "id": f"cotejo-{i}", "evidencia": "x" * 200}
                   for i in range(50)]
        self.escribir_lineas(*relleno,
                             {"cuando": 99, "operacion": "entregar", "id": "cotejo-final",
                              "evidencia": "la última"})
        with mock.patch.object(bitacora, "COLA_BYTES", 1000):
            ultimas = self.ultimas()
        self.assertEqual(ultimas["cotejo-final"]["evidencia"], "la última")
        self.assertLess(len(ultimas), 50)  # lo viejo se queda fuera, que es el trato
        self.assertNotIn("cotejo-0", ultimas)


class DeLaCLIalTablero(PruebaDeBitacora):
    """El camino completo: lo que escribe un verbo es lo que después se lee de vuelta."""

    def test_la_evidencia_de_entregar_es_la_que_se_lee_luego(self):
        tarea = self.una_tarea("Uno")
        self.correr("tomar", tarea.id, "--agente", "opus")
        identificador = self.escanear()[0].tareas[0].id
        codigo, _ = self.correr("entregar", identificador, "--evidencia", "Commit abc1234, 128 en verde")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.ultimas()[identificador]["evidencia"], "Commit abc1234, 128 en verde")

    def test_listar_trae_la_evidencia_de_lo_que_espera_comprobacion(self):
        tarea = self.una_tarea("Uno")
        self.correr("tomar", tarea.id, "--agente", "opus")
        identificador = self.escanear()[0].tareas[0].id
        self.correr("entregar", identificador, "--evidencia", "Lo que hice y cómo se comprueba")
        _, datos = self.correr("tareas", "--estado", "por-validar")
        self.assertEqual(datos["tareas"][0]["evidencia"], "Lo que hice y cómo se comprueba")

    def test_al_tomar_una_tarea_devuelta_viene_el_motivo_del_rechazo(self):
        """Es la mitad que cierra el ciclo: sin el motivo, el agente vuelve a entregar lo mismo."""
        tarea = self.una_tarea("Uno")
        self.correr("tomar", tarea.id, "--agente", "opus")
        identificador = self.escanear()[0].tareas[0].id
        self.correr("entregar", identificador, "--evidencia", "creo que ya está")
        # Rechazarla es cosa del board: devuelve la tarea a pendiente con las mismas funciones
        # de vault.py y anota el motivo. Aquí se reproduce eso para poder tomarla de nuevo.
        from tareas import modelo
        _, tarea_entregada = modelo.buscar(self.escanear(), identificador)
        self.fuente.poner_estado(tarea_entregada, modelo.PENDIENTE)
        self.correr("asignar", identificador, "")
        self.anotar("rechazar", texto_tarea="Una tarea cualquiera",
                    motivo="Las pruebas no cubren el archivo vacío")
        _, datos = self.correr("tomar", identificador, "--agente", "sonnet")
        self.assertEqual(datos["tarea"]["motivo"], "Las pruebas no cubren el archivo vacío")

    def test_una_tarea_sin_anotaciones_no_inventa_claves(self):
        _, datos = self.correr("tareas")
        self.assertNotIn("evidencia", datos["tareas"][0])
        self.assertNotIn("motivo", datos["tareas"][0])


class LoQueNoDebePasar(PruebaDeBitacora):
    def test_la_bitacora_no_vive_dentro_del_vault(self):
        """El texto libre vive fuera del Markdown a propósito. Si algún día acabara dentro,
        las notas del usuario tendrían dos verdades y esta prueba se pone roja."""
        from tareas import bitacora
        self.assertNotIn("bitacora", self.leer_nota("Uno.md"))
        self.assertEqual(bitacora.ARCHIVO.name, "bitacora.jsonl")

    def test_entregar_sigue_exigiendo_evidencia(self):
        tarea = self.una_tarea("Uno")
        self.correr("tomar", tarea.id, "--agente", "opus")
        identificador = self.escanear()[0].tareas[0].id
        with self.assertRaises(SystemExit):  # argparse corta antes de escribir nada
            self.correr("entregar", identificador)
        self.assertEqual(self.ultimas(), {})


if __name__ == "__main__":
    unittest.main()
