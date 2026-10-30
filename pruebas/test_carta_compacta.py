"""La carta de Pendiente enseña el nombre corto y su código detrás (v1.3.1).

Construye `Board.carta` de verdad con un Board falso, sin abrir ventana. Se salta sin GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import modelo

try:
    from gi.repository import Gtk, Pango

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


def etiqueta_con(fila, texto):
    return next((h for h in hijos(fila)
                 if isinstance(h, Gtk.Label) and h.get_label() == texto), None)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir la carta")
class CartaCompacta(unittest.TestCase):
    def test_id_corto(self):
        self.assertEqual(app.comun.id_corto("cotejo-8y7t68"), "8y7t68")
        # Sin ^cotejo-…, el id es ruta:línea, y en la carta queda la línea.
        self.assertEqual(app.comun.id_corto("01-Proyectos/Bot Facturacion/Bot.md:45"), "L45")

    def test_pendiente_enseña_el_nombre_y_el_codigo_sin_revelador(self):
        fila = carta("pendiente")
        # Nada se esconde al pasar el ratón: no queda revelador en la carta.
        self.assertFalse([h for h in hijos(fila) if isinstance(h, Gtk.Revealer)])
        nombre = etiqueta_con(fila, "Hacer algo")
        codigo = etiqueta_con(fila, "8y7t68")
        self.assertIsNotNone(nombre)
        self.assertIsNotNone(codigo)
        # El nombre se recorta con elipsis y el código va en mono tenue detrás, en la misma línea.
        self.assertEqual(nombre.get_ellipsize(), Pango.EllipsizeMode.END)
        self.assertIs(nombre.get_parent(), codigo.get_parent())
        self.assertIn("carta-nombre", nombre.get_css_classes())
        self.assertIn("carta-codigo", codigo.get_css_classes())
        # El nombre completo sigue en el tooltip, para cuando no cabe.
        self.assertEqual(nombre.get_tooltip_text(), "v1.2.4 · Hacer algo: con su descripción")

    def test_pendiente_no_enseña_chips(self):
        fila = carta("pendiente")
        self.assertFalse([h for h in hijos(fila) if "chip" in h.get_css_classes()])

    def test_pendiente_ya_no_esconde_el_nombre(self):
        fila = carta("pendiente")
        dentro = [h.get_label() for h in hijos(fila) if isinstance(h, Gtk.Label)]
        self.assertIn("Hacer algo", dentro)

    def test_estilo_del_nombre_y_del_codigo(self):
        self.assertIn(".carta-compacta .carta-nombre", app.estilo.CSS)
        self.assertIn('.carta-compacta .carta-codigo { color: var(--k-tenue); }',
                      app.estilo.CSS)

    def test_las_demas_columnas_son_completas(self):
        for estado in ("haciendo", "por-validar", "hecha"):
            with self.subTest(estado=estado):
                fila = carta(estado)
                self.assertFalse([h for h in hijos(fila) if isinstance(h, Gtk.Revealer)])
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
