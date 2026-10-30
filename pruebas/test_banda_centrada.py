"""La banda de proyectos: centrado del chip activo, flechas y cursor solo si desborda."""

import types
import unittest
from unittest import mock

import apoyo  # noqa: F401
try:
    from gi.repository import Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


@unittest.skipUnless(HAY_GTK, "sin GTK")
class PosicionCentrado(unittest.TestCase):
    def test_centro(self):
        # chip de 100 en x=500, banda de 300: 500 + 50 - 150 = 400
        self.assertEqual(app.comun.posicion_centrado(500, 100, 300, 1000), 400)

    def test_extremos(self):
        self.assertEqual(app.comun.posicion_centrado(100, 100, 300, 1000), 0)
        self.assertEqual(app.comun.posicion_centrado(0, 100, 300, 1000), 0)        # nunca negativo
        self.assertEqual(app.comun.posicion_centrado(5000, 100, 300, 1000), 1000)  # nunca pasa del máximo
        self.assertEqual(app.comun.posicion_centrado(100, 100, 300, -5), 0)

    def test_primero_y_ultimo_llegan_al_centro(self):
        banda = 300
        primero = app.comun.posicion_centrado(banda / 2, 80, banda, 10_000)
        self.assertEqual(primero + banda / 2, banda / 2 + 40)  # centro del chip == centro visible


def banda_falsa(proyectos=("A", "B")):
    """Un Board sin ventana con la banda de verdad, pintada con `proyectos`."""
    falso = types.SimpleNamespace(seleccion=proyectos[0] if proyectos else app.comun.TODOS)
    falso.vigilar_teclas = lambda *a: None
    falso.poner_maestro = lambda: None
    falso.poner_botones_flotantes = lambda: None
    falso.clave_chip_enfocado = lambda: None
    falso.proyectos_con_tareas = lambda: [types.SimpleNamespace(nombre=n, tareas=[])
                                          for n in proyectos]
    for nombre in ("crear_banda_proyectos", "flecha_de_banda", "desplazar_banda",
                   "llevar_banda_a", "al_girar_rueda_banda", "banda_desborda",
                   "poner_flechas_banda", "al_empezar_banda", "al_arrastrar_banda",
                   "al_soltar_banda", "al_medir_banda", "centrar_chip_activo",
                   "al_acabar_centrado", "pintar_banda", "filas_banda", "al_elegir_chip",
                   "al_tecla_banda"):
        setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
    falso.banda = falso.crear_banda_proyectos()
    falso.pintar_banda()
    return falso


def chips(falso):
    hijo, todos = falso.chips.get_first_child(), []
    while hijo is not None:
        if isinstance(hijo, Gtk.Button):
            todos.append(hijo)
        hijo = hijo.get_next_sibling()
    return todos


@unittest.skipUnless(HAY_GTK, "sin GTK")
class BandaSinVueltas(unittest.TestCase):
    def test_cada_proyecto_sale_una_sola_vez(self):
        falso = banda_falsa(("A", "B"))
        self.assertEqual([c.clave for c in chips(falso)], [app.comun.TODOS, "A", "B"])

    def test_ya_no_hay_banda_infinita(self):
        for nombre in ("copias_de_banda", "vuelta_de_banda", "COPIAS_BANDA_MIN"):
            self.assertFalse(hasattr(app, nombre), nombre)
        self.assertFalse(hasattr(app.Board, "al_mover_banda"))

    def test_si_todo_cabe_no_hay_flechas_ni_cursor_de_agarrar(self):
        falso = banda_falsa(("A", "B"))
        falso.poner_flechas_banda()
        self.assertFalse(falso.flecha_banda_atras.get_visible())
        self.assertFalse(falso.flecha_banda_adelante.get_visible())
        self.assertIsNone(falso.banda_scroll.get_cursor())

    def test_si_desborda_salen_las_flechas_y_se_apagan_en_el_extremo(self):
        falso = banda_falsa(("A", "B"))
        ajuste = falso.banda_scroll.get_hadjustment()
        ajuste.configure(0, 0, 1000, 10, 100, 300)
        falso.poner_flechas_banda()
        self.assertTrue(falso.flecha_banda_adelante.get_visible())
        self.assertFalse(falso.flecha_banda_atras.get_sensitive())
        self.assertTrue(falso.flecha_banda_adelante.get_sensitive())
        self.assertEqual(falso.banda_scroll.get_cursor().get_name(), "grab")
        ajuste.set_value(700)
        self.assertTrue(falso.flecha_banda_atras.get_sensitive())
        self.assertFalse(falso.flecha_banda_adelante.get_sensitive())

    def test_todos_va_separado_de_los_proyectos(self):
        falso = banda_falsa(("A",))
        segundo = falso.chips.get_first_child().get_next_sibling()
        self.assertIsInstance(segundo, Gtk.Separator)

    def test_alto_del_chip_en_el_css(self):
        self.assertIn("min-height: 36px", app.estilo.CSS)


def _tablero_falso(seleccion="A"):
    """Un Board sin ventana: solo lo que usan el pie y al_elegir_chip."""
    falso = types.SimpleNamespace(
        seleccion=seleccion, botones_chip={},
        finalizadas=types.SimpleNamespace(pila=[], deshacer=lambda: None))
    for nombre in ("crear_pie", "actualizar_deshacer", "al_deshacer", "al_elegir_chip"):
        setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
    falso.pie_ahorro = lambda: Gtk.Label(label="ahorro")
    falso.pie_donar = lambda: Gtk.Label(label="cafe")
    falso.barra_maestro = lambda: Gtk.Box()
    falso.centrar_chip_activo = falso.poner_maestro = lambda *a, **k: None
    falso.poner_botones_flotantes = lambda *a, **k: None
    falso.pintar_columnas = lambda *a, **k: None
    for clave in ("A", "B", "C"):
        falso.botones_chip[clave] = types.SimpleNamespace(
            clave=clave, add_css_class=lambda c: None, remove_css_class=lambda c: None)
    return falso


@unittest.skipUnless(HAY_GTK, "sin GTK")
class PieEnTresZonas(unittest.TestCase):
    def test_estructura(self):
        falso = _tablero_falso()
        pie = falso.crear_pie()
        self.assertIsInstance(pie, Gtk.CenterBox)
        self.assertIs(pie.get_start_widget(), falso.pie_izquierda)
        self.assertIs(pie.get_center_widget(), falso.pie_centro)
        self.assertIs(pie.get_end_widget(), falso.pie_derecha)
        self.assertEqual(falso.pie_izquierda.get_margin_start(), app.comun.MARGEN_TABLERO_LADOS)
        self.assertEqual(falso.pie_derecha.get_margin_end(), app.comun.MARGEN_TABLERO_LADOS)
        self.assertEqual(falso.pie_centro.get_first_child().get_size_request()[0], 520)
        self.assertTrue(falso.boton_deshacer.get_visible())


@unittest.skipUnless(HAY_GTK, "sin GTK")
class DeshacerEnElPie(unittest.TestCase):
    def setUp(self):
        self.t = _tablero_falso("A")
        self.t.crear_pie()
        parche = mock.patch.object(app.comun, "guardar_board", lambda **k: None)
        parche.start()
        self.addCleanup(parche.stop)

    def test_siempre_visible_y_apagado_sin_nada_que_deshacer(self):
        self.assertTrue(self.t.boton_deshacer.get_visible())
        self.assertFalse(self.t.boton_deshacer.get_sensitive())
        self.assertEqual(self.t.boton_deshacer.get_tooltip_text(),
                         "Deshacer la última tarea finalizada (Ctrl Z)")

    def test_con_algo_en_la_pila_se_enciende_y_deshace(self):
        deshecho = []
        self.t.finalizadas.pila.append(object())
        self.t.finalizadas.deshacer = lambda: deshecho.append(True)
        self.t.actualizar_deshacer()
        self.assertTrue(self.t.boton_deshacer.get_sensitive())
        self.t.al_deshacer()
        self.assertEqual(deshecho, [True])

    def test_cambiar_de_proyecto_no_toca_el_deshacer(self):
        self.t.al_elegir_chip(self.t.botones_chip["B"])
        self.assertEqual(self.t.seleccion, "B")
        self.assertFalse(self.t.boton_deshacer.get_sensitive())


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAY_GTK, "sin GTK")
class MarcaDePorComprobar(unittest.TestCase):
    """El número verde sin pastilla, y el chip abierto sin verde para que el número se lea."""

    def regla(self, selector):
        inicio = app.estilo.CSS.index(selector + " {")
        return app.estilo.CSS[inicio:app.estilo.CSS.index("}", inicio)]

    def test_aviso_sin_pastilla(self):
        regla = self.regla(".aviso-chip")
        self.assertIn("color: var(--k-senal)", regla)
        self.assertNotIn("background", regla)
        self.assertNotIn(".banda-chip.activo .aviso-chip", app.estilo.CSS)

    def test_contador_de_para_comprobar_sin_pastilla(self):
        regla = self.regla(".cuenta-columna.en-cotejo")
        self.assertIn("color: var(--k-senal)", regla)
        self.assertIn("background: transparent", regla)

    def test_chip_abierto_sin_verde(self):
        self.assertNotIn("senal", self.regla(".banda-chip.activo"))
