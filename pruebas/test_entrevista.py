"""La entrevista de «Nuevo proyecto» sin GTK (tareas/entrevista.py): del formulario a Respuestas."""

import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import entrevista, inicio


class Entrevista(unittest.TestCase):
    def test_nombre_y_carpeta_sugeridos(self):
        self.assertEqual(entrevista.nombre_sugerido(entrevista.EJEMPLOS["que_es"]),
                         "clientes-barberia-reserven-turno")
        self.assertEqual(entrevista.nombre_sugerido("¡Añejo! Café"), "anejo-cafe")
        self.assertEqual(entrevista.nombre_sugerido(""), "proyecto-nuevo")
        self.assertEqual(entrevista.carpeta_sugerida("Una tienda", casa="/casa/x"),
                         "/casa/x/Proyectos/tienda")

    def test_los_ejemplos_y_las_opciones_por_defecto_son_validos(self):
        e = entrevista.EJEMPLOS
        marcadas = lambda ops: [t for t, m in ops if m]  # noqa: E731
        r = entrevista.respuestas(e["que_es"], e["para_quien"], e["que_hace"],
                                  marcadas(entrevista.DONDE), marcadas(entrevista.NECESITA),
                                  e["fuera"], "/tmp/proyectos/demo")
        self.assertEqual(r.donde_se_usa, "En el celular, En el navegador")
        prompt, motivo = entrevista.prompt_o_error(r)
        self.assertEqual(motivo, "")
        self.assertEqual(prompt, inicio.armar(r))
        self.assertEqual(entrevista.rellenadas(r), 6)

    def test_sin_marcar_nada_el_prompt_usa_lo_de_sin_respuesta(self):
        r = entrevista.respuestas("Algo", "", "Hacer cosas", [], [], "", "/tmp/algo")
        self.assertEqual(r.donde_se_usa, "")
        prompt, _ = entrevista.prompt_o_error(r)
        self.assertIn(inicio.SIN_RESPUESTA["donde_se_usa"], prompt)
        self.assertEqual(entrevista.rellenadas(r), 2)

    def test_campos_obligatorios_vacios_dan_un_motivo_y_no_un_prompt(self):
        for campo in ("que_es", "que_hace", "carpeta"):
            args = dict(que_es="Algo", para_quien="", que_hace="Cosas", donde=[], necesita=[],
                        fuera="", carpeta="/tmp/algo")
            args[campo] = ""
            prompt, motivo = entrevista.prompt_o_error(entrevista.respuestas(**args))
            self.assertEqual(prompt, "")
            self.assertIn("no puede ir vacío", motivo)
        prompt, motivo = entrevista.prompt_o_error(
            entrevista.respuestas("Algo", "", "Cosas", [], [], "", "relativa/ruta"))
        self.assertIn("absoluta", motivo)


if __name__ == "__main__":
    unittest.main()
