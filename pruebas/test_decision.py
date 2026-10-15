"""Aceptar una decisión propuesta (C5, v1.2): propuesta→aceptada, el reemplazo de la vieja,
la versión vieja rechazada y que no se pueda aceptar lo que no es una decisión propuesta.

Todo corre contra un `Almacen` de mentira, igual que `test_almacen.py`: esto es la lógica que
llama CotejoBoard, sin GTK, así que se prueba sin pantalla y sin ningún verbo de CLI ni tool de
MCP (esos los vigila `pruebas/test_cli.py::Contrato`).
"""

import tempfile
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import decision
from tareas.almacen import Almacen, EntradaCambiada, NoSeEdita


class PruebaConAlmacen(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        (self.repo / ".git").mkdir(parents=True)
        self.almacen = Almacen(self.repo)


class Propuestas(PruebaConAlmacen):

    def test_solo_salen_las_que_estan_propuesta(self):
        propuesta = self.almacen.crear("decision", "Usar JWT", "Texto.")
        aceptada = self.almacen.crear("decision", "Otra", "Texto.")
        self.almacen.poner_estado(aceptada.id, aceptada.version, "aceptada")
        ids = {e.id for e in decision.propuestas(self.almacen)}
        self.assertEqual(ids, {propuesta.id})


class ParaRevisar(PruebaConAlmacen):

    def test_sin_reemplaza_sale_reemplaza_en_none(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "Lo decidimos así.")
        datos = decision.para_revisar(self.almacen, entrada)
        self.assertEqual(datos["id"], entrada.id)
        self.assertEqual(datos["titulo"], "Usar JWT")
        self.assertIn("Lo decidimos así.", datos["texto"])
        self.assertIsNone(datos["reemplaza"])

    def test_con_reemplaza_trae_el_texto_de_la_vieja(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "La vieja razón.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "La nueva razón.",
                                   reemplaza=vieja.id)
        datos = decision.para_revisar(self.almacen, nueva)
        self.assertEqual(datos["reemplaza"]["id"], vieja.id)
        self.assertEqual(datos["reemplaza"]["titulo"], "Usar sesiones")
        self.assertIn("La vieja razón.", datos["reemplaza"]["texto"])
        self.assertEqual(datos["reemplaza"]["estado"], "aceptada")

    def test_si_la_vieja_ya_no_existe_reemplaza_sale_en_none_sin_romper(self):
        nueva = self.almacen.crear("decision", "Usar JWT", "Texto.", reemplaza="dec-zzzz")
        datos = decision.para_revisar(self.almacen, nueva)
        self.assertIsNone(datos["reemplaza"])


class Aceptar(PruebaConAlmacen):

    def test_propuesta_pasa_a_aceptada(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "Texto.")
        aceptada, reemplazada = decision.aceptar(self.almacen, entrada.id, entrada.version)
        self.assertEqual(aceptada.estado, "aceptada")
        self.assertIsNone(reemplazada)
        de_nuevo = self.almacen.leer(entrada.id)
        self.assertEqual(de_nuevo.estado, "aceptada")

    def test_con_reemplaza_la_vieja_queda_reemplazada(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)

        aceptada, reemplazada = decision.aceptar(self.almacen, nueva.id, nueva.version)

        self.assertEqual(aceptada.estado, "aceptada")
        self.assertEqual(reemplazada.id, vieja.id)
        self.assertEqual(reemplazada.estado, "reemplazada")
        self.assertEqual(reemplazada.datos.get("reemplazada_por"), aceptada.id)
        vieja_otra_vez = self.almacen.leer(vieja.id)
        self.assertEqual(vieja_otra_vez.estado, "reemplazada")

    def test_version_vieja_se_rechaza_sin_escribir(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "Texto.")
        with self.assertRaises(EntradaCambiada):
            decision.aceptar(self.almacen, entrada.id, "versionvieja")
        self.assertEqual(self.almacen.leer(entrada.id).estado, "propuesta")

    def test_no_se_acepta_lo_que_ya_esta_aceptada(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "Texto.")
        aceptada = self.almacen.poner_estado(entrada.id, entrada.version, "aceptada")
        with self.assertRaises(NoSeEdita):
            decision.aceptar(self.almacen, aceptada.id, aceptada.version)

    def test_no_se_acepta_lo_que_ya_esta_reemplazada(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)
        decision.aceptar(self.almacen, nueva.id, nueva.version)
        vieja = self.almacen.leer(vieja.id)  # ya «reemplazada»
        with self.assertRaises(NoSeEdita):
            decision.aceptar(self.almacen, vieja.id, vieja.version)

    def test_no_se_acepta_una_entrada_que_no_es_decision(self):
        problema = self.almacen.crear("problema", "Algo falla", "Texto.")
        with self.assertRaises(decision.NoEsDecision):
            decision.aceptar(self.almacen, problema.id, problema.version)

    def test_aceptacion_parcial_si_la_vieja_cambio_entre_medias(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)
        # La vieja queda reemplazada por otro camino justo antes de aceptar la nueva (otra
        # decisión la reemplazó mientras tanto): ya no está «aceptada».
        self.almacen.poner_estado(vieja.id, vieja.version, "reemplazada",
                                  campos={"reemplazada_por": "dec-otra"})

        with self.assertRaises(decision.AceptacionParcial) as contexto:
            decision.aceptar(self.almacen, nueva.id, nueva.version)
        self.assertEqual(contexto.exception.aceptada.id, nueva.id)
        # La nueva sí quedó aceptada aunque la vieja no se pudo mover.
        self.assertEqual(self.almacen.leer(nueva.id).estado, "aceptada")


if __name__ == "__main__":
    unittest.main()
