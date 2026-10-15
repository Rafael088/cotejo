"""`entregar --resumen`: qué cambió visto desde fuera y cómo probarlo, para quien no programa.

Es una clave que se agrega a la evidencia: sin la bandera todo queda como antes. Se guarda en
la bitácora (donde vive la evidencia de cualquier fuente), sale en el JSON de `entregar`, de
`tareas`/`tomar` y de `comprobar` por la misma vía que `evidencia`, y el MCP la ofrece solo.
"""

import json
import tempfile
import unittest

from apoyo import PruebaDeCLI, proyecto
from test_fuente_repo import PruebaConRepos

from tareas import cli, mcp

RESUMEN = "Ahora el botón Guardar avisa cuando termina. Pruébalo: abre un archivo, pulsa Guardar."


def entregas(prueba):
    return [o for o in prueba.operaciones() if o["operacion"] == "entregar"]


class ConObsidian(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Haciéndola #en-curso #agente/opus"))
        _, datos = self.correr("tareas")
        self.id = datos["tareas"][0]["id"]

    def test_se_guarda_y_sale_en_el_json_de_entregar(self):
        codigo, datos = self.correr("entregar", self.id, "--evidencia", "hecho",
                                    "--resumen", f"  {RESUMEN}  ")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["resumen"], RESUMEN)
        anotada, = entregas(self)
        self.assertEqual(anotada["resumen"], RESUMEN)
        self.assertEqual(anotada["evidencia"], "hecho")      # nada se renombró ni se quitó

    def test_lo_que_lee_el_board_y_comprobar_lo_traen(self):
        self.correr("entregar", self.id, "--evidencia", "hecho", "--resumen", RESUMEN,
                    "--prueba", "python3 -c pass", "--repo", str(self.vault))
        _, tareas = self.correr("tareas")
        self.assertEqual(tareas["tareas"][0]["resumen"], RESUMEN)
        _, comprobada = self.correr("comprobar", tareas["tareas"][0]["id"])
        self.assertEqual(comprobada["tarea"]["resumen"], RESUMEN)

    def test_sin_resumen_todo_sigue_igual(self):
        codigo, datos = self.correr("entregar", self.id, "--evidencia", "hecho")
        self.assertEqual(codigo, 0)
        self.assertNotIn("resumen", datos)
        self.assertNotIn("resumen", entregas(self)[0])

    def test_vacio_se_rechaza_y_no_escribe_nada(self):
        for vacio in ("", "   "):
            with self.assertRaises(SystemExit) as salida:
                self.correr_crudo("entregar", self.id, "--evidencia", "x", "--resumen", vacio)
            self.assertNotEqual(salida.exception.code, 0)
        self.assertEqual(entregas(self), [])
        _, datos = self.correr("tareas")
        self.assertEqual(datos["tareas"][0]["estado"], "en-curso")


class ConRepo(PruebaConRepos):
    def test_en_la_fuente_repo_se_guarda_y_se_lee(self):
        self.correr("tomar", "m1", "--agente", "opus")
        codigo, datos = self.correr("entregar", "m1", "--evidencia", "x", "--resumen", RESUMEN)
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["resumen"], RESUMEN)
        anotada, = entregas(self)
        self.assertEqual(anotada["resumen"], RESUMEN)
        # La línea de la tarea en el repo no cambia: el resumen vive en la bitácora.
        self.assertEqual(self.archivo().splitlines()[2],
                         "- [ ] Comprar café #facil #agente/opus #por-validar ^m1")

    def test_sin_resumen_en_la_fuente_repo(self):
        self.correr("tomar", "m1", "--agente", "opus")
        _, datos = self.correr("entregar", "m1", "--evidencia", "x")
        self.assertNotIn("resumen", datos)


class EnElMCP(unittest.TestCase):
    def test_el_parametro_aparece_solo_y_es_opcional(self):
        entregar = next(t for t in mcp.tools() if t["name"] == "entregar")["inputSchema"]
        self.assertEqual(entregar["properties"]["resumen"]["type"], "string")
        self.assertNotIn("resumen", entregar["required"])
        self.assertEqual(set(entregar["required"]), {"id", "evidencia"})

    def test_el_argv_lo_pasa_a_la_cli(self):
        argv = mcp.argv("entregar", {"id": "x", "evidencia": "e", "resumen": "r"})
        self.assertIn("--resumen=r", argv)


if __name__ == "__main__":
    unittest.main()
