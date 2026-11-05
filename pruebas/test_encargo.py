"""El encargo orienta al agente sin volver a inflar su contexto."""

import tempfile
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from enrutador import encargo
from tareas import almacen


class _Decision:
    razon = "la tarea está asignada a #agente/sol"

    class nivel:
        modelo = "sol"


class DondeMirar(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name)
        self.almacen = almacen.Almacen(self.repo)
        self.almacen.base.mkdir()

    def tarea(self, texto):
        return {"id": "cotejo-prueba", "proyecto": "Prueba", "texto": texto}

    def test_muestra_hasta_tres_entradas_cuyos_temas_estan_en_la_tarea(self):
        precisa = self.almacen.crear(
            "arquitectura", "Flujo del enrutador", temas=["enrutador", "arquitectura"])
        decision = self.almacen.crear(
            "decision", "Encargos compactos", temas=["enrutador"])
        otra = self.almacen.crear(
            "decision", "Otra decisión del enrutador", temas=["enrutador"])
        cuarta = self.almacen.crear(
            "arquitectura", "Otra arquitectura", temas=["arquitectura"])
        ajena = self.almacen.crear(
            "decision", "Colores del board", temas=["ui"])

        texto = encargo.armar(
            self.tarea("Revisar la arquitectura del enrutador"), _Decision(), self.repo)

        self.assertIn("Dónde mirar", texto)
        encontrados = [e.id for e in (precisa, decision, otra, cuarta) if e.id in texto]
        self.assertEqual(len(encontrados), 3)
        self.assertIn(precisa.id, encontrados)
        self.assertNotIn(ajena.id, texto)
        for entrada_id in encontrados:
            self.assertIn(f"cotejo leer {entrada_id}", texto)

    def test_anade_tres_habitos_y_el_encargo_normal_queda_bajo_mil_tokens(self):
        for numero in range(3):
            self.almacen.crear(
                "decision", f"Decisión {numero}", temas=["enrutador"],
                texto="Una decisión relacionada con el encargo.")

        texto = encargo.armar(
            self.tarea("v1.3.1 · Mejorar el encargo del enrutador"),
            _Decision(), self.repo)

        self.assertEqual(sum(linea in texto for linea in encargo.HABITOS), 3)
        self.assertLessEqual(len(texto) / 4, 1000, texto)

    def test_sin_almacen_no_falla_ni_inventa_donde_mirar(self):
        vacio = self.repo / "sin-cotejo"
        vacio.mkdir()

        texto = encargo.armar(self.tarea("Arreglar el enrutador"), _Decision(), vacio)

        self.assertNotIn("Dónde mirar", texto)
        self.assertEqual(sum(linea in texto for linea in encargo.HABITOS), 3)


if __name__ == "__main__":
    unittest.main()
