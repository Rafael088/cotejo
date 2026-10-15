"""La ficha de una tarea (la ventana de detalle), y Pendiente agrupada por versión (7.3.3).

Arma la ventana de verdad con un Board falso, sin presentarla. Se salta sin GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import modelo

try:
    from tareas import app
    from gi.repository import Adw, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def hijos(widget):
    # Un Adw.Dialog no enseña sus hijos por get_first_child: se entra por get_child().
    if isinstance(widget, Adw.Dialog):
        yield from hijos(widget.get_child())
        return
    yield widget
    hijo = widget.get_first_child()
    while hijo is not None:
        yield from hijos(hijo)
        hijo = hijo.get_next_sibling()


def dialogo(estado, texto="v1.2.4 · Banda de proyectos: una franja al 60 %", bitacora=None):
    movidas, asignadas = [], []
    falso = types.SimpleNamespace(
        agentes=("opus", "sonnet", "persona"), alias_persona=("persona",),
        app=types.SimpleNamespace(bitacora=bitacora or {}),
        al_asignar=lambda p, t, agente, pop: asignadas.append(agente),
        mover=lambda p, t, destino: movidas.append(destino))
    for nombre in ("selector_de_agente", "lista_de_agentes", "opcion"):
        setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
    falso.dato_de_detalle = app.Board.dato_de_detalle
    hecha = estado == modelo.HECHA
    tarea = modelo.Tarea(texto, id="cotejo-agcea3", donde="Cotejo.md",
                         estado="por-validar" if hecha else estado, hecha=hecha,
                         agente="sonnet", dificultad="medio")
    d = app.Board.dialogo_detalle(falso, types.SimpleNamespace(nombre="Cotejo"), tarea)
    return d, movidas, asignadas


def botones(d):
    return {getattr(b, "texto", None) or b.get_label(): b for b in hijos(d)
            if isinstance(b, Gtk.Button) and (getattr(b, "texto", None) or b.get_label())}


def etiquetas(d):
    return [h.get_label() for h in hijos(d) if isinstance(h, Gtk.Label)]


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede armar la ventana")
class VentanaDeDetalle(unittest.TestCase):
    def test_tiene_la_barra_con_el_boton_de_cerrar(self):
        d, _, _ = dialogo("pendiente")
        barras = [h for h in hijos(d) if isinstance(h, Adw.HeaderBar)]
        self.assertEqual(len(barras), 1)
        self.assertTrue(barras[0].get_show_end_title_buttons())
        self.assertTrue(d.get_can_close())

    def test_ensena_id_version_nombre_y_descripcion(self):
        d, _, _ = dialogo("pendiente")
        for esperado in ("agcea3", "v1.2.4", "Banda de proyectos", "una franja al 60 %", "sonnet",
                         "Media", "Cotejo.md"):
            self.assertIn(esperado, etiquetas(d))

    def test_el_id_sale_una_sola_vez(self):
        d, _, _ = dialogo("pendiente")
        self.assertEqual(etiquetas(d).count("agcea3"), 1)

    def test_sin_dos_puntos_el_texto_sale_una_vez_y_entero(self):
        largo = ("Cambiar la URL vieja en config.js, install.sh e install.ps1 por la del dominio "
                 "propio y dejar DOMINIO por defecto al publicar la web")
        d, _, _ = dialogo("pendiente", texto=largo)
        textos = etiquetas(d)
        self.assertIn(largo, textos)
        self.assertFalse(any(t.endswith("…") for t in textos if t))

    def test_pendiente_se_puede_pasar_a_haciendola(self):
        d, movidas, _ = dialogo("pendiente")
        b = botones(d)
        self.assertNotIn("Devolver a Pendiente", b)
        b["Pasar a Haciéndola"].emit("clicked")
        self.assertEqual(movidas, ["en-curso"])

    def test_haciendola_avanza_o_vuelve_pero_nunca_a_finalizada(self):
        d, movidas, _ = dialogo("en-curso")
        b = botones(d)
        b["Pasar a Para comprobar"].emit("clicked")
        b["Devolver a Pendiente"].emit("clicked")
        self.assertEqual(movidas, ["por-validar", "pendiente"])
        self.assertFalse(any("Finalizada" in nombre for nombre in b))

    def test_no_ofrece_abrir_la_tarea_en_su_app(self):
        for estado in ("pendiente", "en-curso", "por-validar", "hecha"):
            d, _, _ = dialogo(estado)
            self.assertFalse(any("Abrir" in nombre for nombre in botones(d)), estado)

    def test_el_modelo_se_cambia_desde_la_ficha(self):
        d, _, asignadas = dialogo("pendiente")
        selector = [h for h in hijos(d) if isinstance(h, Gtk.MenuButton)]
        self.assertEqual(len(selector), 1)
        opciones = [h for h in hijos(selector[0].get_popover())
                    if isinstance(h, Gtk.Button) and "menu-item" in h.get_css_classes()]
        opciones[0].emit("clicked")
        self.assertEqual(asignadas, ["opus"])

    def test_en_finalizada_el_modelo_no_se_cambia(self):
        d, _, _ = dialogo("hecha")
        self.assertFalse([h for h in hijos(d) if isinstance(h, Gtk.MenuButton)])
        self.assertIn("sonnet", etiquetas(d))

    def test_la_anotacion_sale_entera(self):
        motivo = "Falta la prueba de Windows. " * 12
        d, _, _ = dialogo("pendiente", bitacora={"cotejo-agcea3": {"motivo": motivo,
                                                                   "operacion": "devolver"}})
        self.assertIn(motivo.strip(), etiquetas(d))


@unittest.skipUnless(HAY_GTK, "sin GTK no se importa app")
class PendientePorVersion(unittest.TestCase):
    def test_de_la_mas_proxima_a_la_mas_lejana_y_sin_version_al_final(self):
        textos = ["Comprar el dominio", "v1.2.5 · B: x", "v1.2.4 · A: x", "v1.10.0 · C: x",
                  "v1.2.4 · D: x"]
        tareas = [modelo.Tarea(t) for t in textos]
        orden = [t.texto for t in app.comun.ordenar_por_version(tareas)]
        self.assertEqual(orden, ["v1.2.4 · A: x", "v1.2.4 · D: x", "v1.2.5 · B: x",
                                 "v1.10.0 · C: x", "Comprar el dominio"])


if __name__ == "__main__":
    unittest.main()
