"""Bug 7 del 30-oct: crear → recargar → elegir modelo → despachar, sin volver atrás.

El registro de cotejo-axmjty mostraba un veto «fisico» por la palabra «celular»:
la tarea se movía como humana aunque pedía construir una web. El maestro y el
agente de trabajo son clientes falsos; las escrituras y el despacho son reales.
"""

import os
import unittest
from unittest import mock

from test_despacho_board import ConClienteFalso, HAY_GIT
from enrutador import cotejo, despacho_board
from tareas import lanzados


TEXTO = ("Crear la web ligera que muestre el menú en el celular, leyendo los datos "
         "del archivo JSON (HTML, CSS y JS; sin backend)")


@unittest.skipUnless(HAY_GIT, "sin git")
class TareaDelMaestro(ConClienteFalso):
    def test_creada_por_el_maestro_se_despacha_sin_devolverla_a_pendiente(self):
        with mock.patch.dict(os.environ, {"FALSO_CREAR": TEXTO, "FALSO_PROYECTO": "Uno",
                                          "FALSO_RESPUESTA": "Apunté la web del menú."}), \
                mock.patch("enrutador.clientes.shutil.which", return_value="/usr/bin/x"):
            codigo, respuesta = self.correr("maestro", "--proyecto", "Uno",
                                            "--pedido", "apunta la web del menú",
                                            "--cliente", "claude")
        self.assertEqual(codigo, 0, respuesta)
        self.assertTrue(respuesta["ok"], respuesta)

        # Una lectura nueva, como la recarga del board al terminar el turno.
        _, tareas = self.tareas_de("Uno")
        nueva = next(t for t in tareas if t.texto == TEXTO)
        self.assertEqual((nueva.columna, nueva.agente), ("pendiente", ""))
        # El primer arrastre debe preguntar el modelo, nunca moverla como humana.
        with self.assertRaises(despacho_board.FaltaModelo):
            self.lanzar(nueva.id)
        self.assertIsNone(lanzados.leer(nueva.id))
        self.assertEqual(cotejo.Cotejo().tarea(nueva.id)["estado"], "pendiente")

        codigo, asignada = self.correr("asignar", nueva.id, "haiku")
        self.assertEqual(codigo, 0, asignada)
        estado = self.lanzar_vivo(nueva.id)
        self.assertEqual(estado["estado"], lanzados.TRABAJANDO)
        self.assertEqual(estado["modelo"], "haiku")
        self.assertIsInstance(estado["pid"], int)
        actual = cotejo.Cotejo().tarea(nueva.id)
        self.assertEqual((actual["estado"], actual["agente"]), ("en-curso", "haiku"))
        operaciones = [o["operacion"] for o in self.operaciones() if o.get("id") == nueva.id]
        # «crear» lo anotó el subproceso en su estado; aquí no hubo ningún «mover».
        self.assertEqual(operaciones, ["asignar", "tomar"])


if __name__ == "__main__":
    unittest.main()
