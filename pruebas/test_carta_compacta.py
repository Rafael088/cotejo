"""La carta de Pendiente es compacta (id corto + título) y se expande al acercarse (v1.2.4).

Construye `Board.carta` de verdad con un Board falso, sin abrir ventana. Se salta sin GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import modelo

try:
    from gi.repository import GLib, Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def hijos(widget):
    hijo = widget.get_first_child()
    while hijo is not None:
        yield hijo
        yield from hijos(hijo)
        hijo = hijo.get_next_sibling()


def carta(estado, agente="opus"):
    falso = types.SimpleNamespace(
        alias_persona=(), app=types.SimpleNamespace(bitacora={}),
        fuente=types.SimpleNamespace(accion_abrir="Abrir la nota"),
        menu=lambda p, t: Gtk.MenuButton(popover=Gtk.Popover()),
        arrastrable=lambda f: None, anotacion=lambda t: None,
        revision_en_carta=lambda p, t: Gtk.Label(label="revision"))
    falso.chip_agente = types.MethodType(app.Board.chip_agente, falso)
    falso.motivo_en_espera = types.MethodType(app.Board.motivo_en_espera, falso)
    falso.detalles_de_carta = types.MethodType(app.Board.detalles_de_carta, falso)
    tarea = modelo.Tarea("v1.2.4 · Hacer algo: con su descripción", id="cotejo-8y7t68", donde="Uno.md",
                         estado="en-curso" if estado == "haciendo" else
                         "por-validar" if estado == "por-validar" else "pendiente",
                         hecha=estado == "hecha", agente=agente, dificultad="media")
    proyecto = types.SimpleNamespace(nombre="Uno")
    return app.Board.carta(falso, proyecto, tarea)


def revelador(fila):
    return next((h for h in hijos(fila) if isinstance(h, Gtk.Revealer)), None)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir la carta")
class CartaCompacta(unittest.TestCase):
    def test_id_corto(self):
        self.assertEqual(app.comun.id_corto("cotejo-8y7t68"), "8y7t68")
        # Sin ^cotejo-…, el id es ruta:línea, y en la carta queda la línea.
        self.assertEqual(app.comun.id_corto("01-Proyectos/Bot Facturacion/Bot.md:45"), "L45")

    def test_pendiente_es_compacta(self):
        fila = carta("pendiente")
        rev = revelador(fila)
        self.assertIsNotNone(rev)
        self.assertFalse(rev.get_reveal_child())
        etiquetas = [h.get_label() for h in hijos(fila) if isinstance(h, Gtk.Label)]
        self.assertIn("8y7t68", etiquetas)
        # Los chips (agente, dificultad) viven dentro del revelador.
        self.assertTrue(any(isinstance(h, Gtk.Label) for h in hijos(rev)))

    def controlador(self, fila, tipo):
        lista = fila.observe_controllers()
        return next(lista.get_item(i) for i in range(lista.get_n_items())
                    if isinstance(lista.get_item(i), tipo))

    def test_puntero_expande_y_la_salida_cede_tras_1500ms(self):
        fila = carta("pendiente")
        rev = revelador(fila)
        mov = self.controlador(fila, Gtk.EventControllerMotion)
        mov.emit("enter", 1.0, 1.0)
        self.assertTrue(rev.get_reveal_child())
        mov.emit("leave")
        self.assertTrue(rev.get_reveal_child())  # aún no cede
        self.assertTrue(rev.estado_revelador["espera"])
        self.assertEqual(app.comun.SALIDA_CARTA_MS, 1500)
        mov.emit("enter", 1.0, 1.0)  # vuelve: la espera se cancela
        self.assertFalse(rev.estado_revelador["espera"])
        mov.emit("leave")
        fila.emit("destroy")  # al refrescar: no queda ningún temporizador vivo
        self.assertFalse(rev.estado_revelador["espera"])

    def en_ventana(self):
        """La carta dentro de una ventana real, con el foco puesto en ella."""
        fila = carta("pendiente")
        lista = Gtk.ListBox()
        lista.append(fila)
        ventana = Gtk.Window(child=lista)
        self.addCleanup(ventana.destroy)
        ventana.present()
        contexto = GLib.MainContext.default()
        for _ in range(50):
            contexto.iteration(False)
        return fila, ventana

    def poner_foco(self, fila):
        fila.grab_focus()
        contexto = GLib.MainContext.default()
        for _ in range(50):
            contexto.iteration(False)

    def test_foco_sin_focus_visible_no_revela(self):
        fila, ventana = self.en_ventana()
        ventana.set_focus_visible(False)
        self.poner_foco(fila)
        self.assertTrue(self.controlador(fila, Gtk.EventControllerFocus).contains_focus())
        self.assertFalse(revelador(fila).estado_revelador["foco"])

    def test_foco_con_focus_visible_revela_y_ceder_al_ir_al_ratón(self):
        fila, ventana = self.en_ventana()
        ventana.set_focus_visible(True)
        self.poner_foco(fila)
        rev = revelador(fila)
        self.assertTrue(rev.estado_revelador["foco"])
        self.assertTrue(rev.get_reveal_child())
        # Pasar al ratón apaga focus-visible: la carta cede (tras la espera de salida).
        ventana.set_focus_visible(False)
        self.assertTrue(rev.estado_revelador["espera"])
        self.assertFalse(rev.estado_revelador["foco"])

    def test_foco_que_llega_solo_tras_cerrar_no_revela(self):
        fila, ventana = self.en_ventana()
        ventana.set_focus_visible(True)
        ventana.set_focus_visible(False)  # el ratón manda
        self.poner_foco(fila)  # el diálogo se cierra y devuelve el foco a la carta
        self.assertFalse(revelador(fila).estado_revelador["foco"])

    def test_sin_animaciones_duracion_cero(self):
        original = app.piezas.animaciones_activas
        app.piezas.animaciones_activas = lambda: False
        try:
            fila = carta("pendiente")
            revelador(fila)
            self.controlador(fila, Gtk.EventControllerMotion).emit("enter", 1.0, 1.0)
            self.assertEqual(revelador(fila).get_transition_duration(), 0)
        finally:
            app.piezas.animaciones_activas = original

    def test_las_demas_columnas_son_completas(self):
        for estado in ("haciendo", "por-validar", "hecha"):
            with self.subTest(estado=estado):
                fila = carta(estado)
                self.assertIsNone(revelador(fila))
                etiquetas = [h.get_label() for h in hijos(fila) if isinstance(h, Gtk.Label)]
                # 7.3.3: todas llevan el id y el nombre corto a la vista.
                self.assertIn("8y7t68", etiquetas)
                self.assertIn("Hacer algo", etiquetas)
                # Haciéndola se queda en id y nombre; Para comprobar enseña versión y descripción.
                completa = estado != "haciendo"
                self.assertEqual("con su descripción" in etiquetas, completa)
                self.assertEqual("v1.2.4" in etiquetas, completa)
                self.assertEqual("revision" in etiquetas, estado == "por-validar")

    def test_haciendola_enseña_el_chip_del_agente(self):
        chips = [h for h in hijos(carta("haciendo")) if "chip-agente" in h.get_css_classes()]
        self.assertEqual(len(chips), 1)
        self.assertIn("opus", [h.get_label() for h in hijos(chips[0])
                               if isinstance(h, Gtk.Label)])
        # Solo el agente: ni dificultad ni otro chip.
        todos = [h for h in hijos(carta("haciendo")) if "chip" in h.get_css_classes()]
        self.assertEqual(len(todos), 1)

    def test_haciendola_sin_agente_no_enseña_chips(self):
        fila = carta("haciendo", agente="")
        self.assertFalse([h for h in hijos(fila) if "chip" in h.get_css_classes()])

    def test_pendiente_no_enseña_chips(self):
        fila = carta("pendiente")
        self.assertFalse([h for h in hijos(fila) if "chip" in h.get_css_classes()])

    def test_pendiente_solo_esconde_el_nombre(self):
        fila = carta("pendiente")
        dentro = [h.get_label() for h in hijos(revelador(fila)) if isinstance(h, Gtk.Label)]
        self.assertEqual(dentro, ["Hacer algo"])

    def test_nombre_accesible_con_agente_y_dificultad(self):
        original = app.cartas.etiquetar
        dados = []
        app.cartas.etiquetar = lambda widget, texto: dados.append(texto)
        try:
            for estado in ("pendiente", "haciendo"):
                carta(estado)
        finally:
            app.cartas.etiquetar = original
        for nombre in dados:
            self.assertIn("Hacer algo", nombre)
            self.assertIn("opus", nombre)
            self.assertIn("media", nombre)
        self.assertEqual(len(dados), 2)


if __name__ == "__main__":
    unittest.main()
