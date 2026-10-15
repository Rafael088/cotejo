import os
import unittest

from tareas.modelo import Tarea, partes_de_tarea

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PartesDeTarea(unittest.TestCase):
    def test_ejemplos(self):
        self.assertEqual(
            partes_de_tarea("v1.2.4 · CotejoBoard 7.3.2 · Banda de proyectos en vez de la lateral: una franja al 60 %…"),
            ("v1.2.4", "Banda de proyectos en vez de la lateral", "una franja al 60 %…"))
        self.assertEqual(partes_de_tarea("v1.2.4 · Release 1.2.4: subir tareas.__version__, …"),
                         ("v1.2.4", "Release 1.2.4", "subir tareas.__version__, …"))
        v, n, d = partes_de_tarea("Comprar el dominio de Cotejo")
        self.assertEqual((v, n, d), ("", "Comprar el dominio de Cotejo", "Comprar el dominio de Cotejo"))

    def test_contexto_multiple(self):
        self.assertEqual(partes_de_tarea("v1.2.4 · A · F3 · Nombre: desc")[:2], ("v1.2.4", "Nombre"))

    def test_contexto_sin_dos_puntos(self):
        v, n, d = partes_de_tarea("v1.2.4 · CotejoBoard 7.3.2 · Probar el board nuevo con el vault real")
        self.assertEqual((v, n), ("v1.2.4", "Probar el board nuevo con el vault real"))
        self.assertIn("CotejoBoard 7.3.2", d)
        # Sin versión delante, un « · » es parte de la frase.
        self.assertEqual(partes_de_tarea("Leer a · b y seguir")[1], "Leer a · b y seguir")

    def test_tag(self):
        # El tag `#v1.2.5` lo saca la fuente (Obsidian) al campo `version`; aquí llega aparte.
        v, n, d = partes_de_tarea("Arreglar el botón: no responde", "v1.2.5")
        self.assertEqual((v, n, d), ("v1.2.5", "Arreglar el botón", "no responde"))
        t = Tarea(texto="Arreglar el botón: no responde", version="v1.2.5")
        self.assertEqual(t.version_del_texto, "v1.2.5")

    def test_el_campo_gana_al_prefijo_y_el_prefijo_se_quita_igual(self):
        self.assertEqual(partes_de_tarea("v1.2.4 · Hola: mundo", "v1.3")[:2], ("v1.3", "Hola"))

    def test_url_y_comandos(self):
        n = partes_de_tarea("Mirar https://example.com/x y listo")[1]
        self.assertEqual(n, "Mirar https://example.com/x y listo")
        self.assertEqual(partes_de_tarea("init e importar obsidian|notion --aplicar sin más palabras de relleno que alarguen mucho esto")[1][:4], "init")

    def test_largo_y_vacio(self):
        self.assertEqual(partes_de_tarea(""), ("", "", ""))
        self.assertEqual(partes_de_tarea(None), ("", "", ""))
        n = partes_de_tarea("palabra " * 30)[1]
        self.assertLessEqual(len(n), 61)
        self.assertTrue(n.endswith("…"))
        self.assertEqual(partes_de_tarea("x" * 100 + ": desc")[1], "x" * 60 + "…")

    def test_propiedades(self):
        t = Tarea(texto="v1.0.1 · Hola: mundo")
        self.assertEqual((t.version_del_texto, t.nombre_corto, t.descripcion), ("v1.0.1", "Hola", "mundo"))

    def test_tareas_reales(self):
        ruta = os.path.join(RAIZ, ".cotejo", "tareas.md")
        if not os.path.exists(ruta):
            self.skipTest("sin .cotejo/tareas.md")
        n = 0
        for linea in open(ruta, encoding="utf-8"):
            if linea.startswith("- ["):
                texto = linea.split("] ", 1)[1].split(" #", 1)[0].split(" ^", 1)[0]
                nombre = partes_de_tarea(texto)[1]
                self.assertTrue(nombre, texto)
                self.assertLessEqual(len(nombre), 80, texto)
                n += 1
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()
