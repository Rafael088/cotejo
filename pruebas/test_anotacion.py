"""Qué enseña la carta de cada tarea, que es la regla con la que se lee el board.

Son dos funciones puras de `tareas/app/comun.py`: deciden, sin tocar GTK, qué anotación se ve
y cómo se fecha. Se prueban aparte porque son la parte que se puede equivocar en silencio —
una carta que no enseña la evidencia se ve exactamente igual que una tarea que nunca la tuvo.

El módulo importa GTK (no abre ventana, solo lo importa): si no está, estas pruebas se saltan
en vez de tumbar la suite entera.
"""

import time
import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

try:
    from tareas.app.comun import anotacion_visible, hace
    HAY_GTK = True
except (ImportError, ValueError):
    HAY_GTK = False


def tarea(estado="pendiente", hecha=False):
    from tareas.modelo import Tarea
    return Tarea("Una tarea", id="cotejo-aaa111", donde="01-Proyectos/Uno.md",
                 estado=estado, agente="opus", hecha=hecha)


def anotacion(**extra):
    base = {"cuando": int(time.time()) - 7200, "operacion": "entregar", "id": "cotejo-aaa111",
            "agente": "opus"}
    base.update(extra)
    return base


@unittest.skipUnless(HAY_GTK, "sin GTK instalado no se puede importar tareas.app")
class QueSeVeEnLaCarta(unittest.TestCase):
    def test_lo_entregado_se_ve_mientras_espera_comprobacion(self):
        clase, titulo, texto = anotacion_visible(
            tarea("por-validar"), anotacion(evidencia="Commit abc1234"))
        self.assertEqual(clase, "entregada")
        self.assertEqual(texto, "Commit abc1234")
        self.assertIn("@opus", titulo)
        self.assertIn("hace 2 h", titulo)

    def test_sin_anotacion_no_se_inventa_nada(self):
        self.assertIsNone(anotacion_visible(tarea("por-validar"), None))

    def test_una_tarea_ya_comprobada_no_arrastra_la_evidencia(self):
        """La evidencia sirve para decidir si se marca; una vez marcada ya hizo su trabajo."""
        self.assertIsNone(anotacion_visible(tarea(hecha=True), anotacion(evidencia="lo que sea")))
        self.assertIsNone(anotacion_visible(tarea(hecha=True), anotacion(motivo="lo que sea")))

    def test_el_motivo_acompana_a_la_tarea_hasta_que_se_vuelva_a_entregar(self):
        for estado in ("pendiente", "en-curso"):
            with self.subTest(estado=estado):
                clase, titulo, texto = anotacion_visible(
                    tarea(estado), anotacion(operacion="rechazar", motivo="Falta la prueba"))
                self.assertEqual(clase, "detenida")
                self.assertEqual(texto, "Falta la prueba")
                self.assertTrue(titulo.startswith("DEVUELTA"))

    def test_bloqueada_por_el_agente_y_devuelta_por_una_persona_no_dicen_lo_mismo(self):
        """Las dos se ven igual, en ámbar, porque las dos piden que alguien mire; pero una la
        paró quien la estaba haciendo y la otra la paró quien la iba a comprobar."""
        _, titulo, _ = anotacion_visible(
            tarea("pendiente"), anotacion(operacion="bloquear", motivo="Falta una clave"))
        self.assertTrue(titulo.startswith("BLOQUEADA"))

    def test_la_evidencia_no_se_queda_pegada_en_otra_columna(self):
        """Fuera de «Para comprobar» ya no hay nada que comprobar: lo que se
        entregó una vez no debe seguir anunciándose en Pendiente."""
        self.assertIsNone(anotacion_visible(tarea("pendiente"), anotacion(evidencia="algo")))
        self.assertIsNone(anotacion_visible(tarea("en-curso"), anotacion(evidencia="algo")))

    def test_una_anotacion_sin_agente_ni_fecha_no_deja_separadores_sueltos(self):
        _, titulo, _ = anotacion_visible(
            tarea("por-validar"), {"evidencia": "algo", "agente": "", "cuando": None})
        self.assertEqual(titulo, "ENTREGADA")


@unittest.skipUnless(HAY_GTK, "sin GTK instalado no se puede importar tareas.app")
class ComoSeFecha(unittest.TestCase):
    def test_los_tramos(self):
        ahora = int(time.time())
        for segundos, esperado in ((0, "recién"), (59, "recién"), (60, "hace 1 min"),
                                   (3600, "hace 60 min"), (5400, "hace 1 h"),
                                   (172800, "hace 2 d")):
            with self.subTest(segundos=segundos):
                self.assertEqual(hace(ahora - segundos), esperado)

    def test_una_fecha_ilegible_no_revienta_la_carta(self):
        self.assertEqual(hace(None), "")
        self.assertEqual(hace("ayer"), "")

    def test_una_fecha_del_futuro_no_cuenta_al_reves(self):
        """Un reloj que se atrasa no debe imprimir «hace -3 min»."""
        self.assertEqual(hace(int(time.time()) + 600), "recién")


if __name__ == "__main__":
    unittest.main()
