"""Finalizada va siempre plegada: un riel con solo el ícono, y una ventana con las finalizadas (v1.2.4).

Construye `Board.columna` y `Board.dialogo_finalizada` de verdad con un Board falso, sin abrir
ventana. Se salta sin GTK. Además, el CSS del board tiene que cargar sin un solo error de GTK.
"""

import types
import unittest
from unittest import mock

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


def tarea(n, cerrada, texto="v1.2.4 · Banda: una franja"):
    return modelo.Tarea(texto, id=f"cotejo-aaaa{n:02d}", donde="Uno.md", estado="hecha",
                        cerrada=cerrada)


def board_falso(hechas=(), seleccion="Uno", filtro="todas"):
    proyecto = types.SimpleNamespace(nombre="Uno", tareas=[], hechas=list(hechas))
    falso = types.SimpleNamespace(
        columnas={}, ventana_finalizada=None, seleccion=seleccion, filtro="",
        filtro_finalizada=filtro, proyectos_con_tareas=lambda: [proyecto],
        altura_encabezados=Gtk.SizeGroup(mode=Gtk.SizeGroupMode.VERTICAL),
        menu_filtro_finalizada=lambda boton: None, presentar_finalizada=lambda: None,
        al_activar=lambda *a: None, vigilar_teclas=lambda *a: None,
        al_tecla_columna=lambda *a: None, al_entrar_arrastre=lambda *a: None,
        al_salir_arrastre=lambda *a: None, al_soltar=lambda *a: None,
        menu=lambda p, t: Gtk.MenuButton(popover=Gtk.Popover()),
        fila_quieta=lambda hijo: hijo,
        vacio=lambda clave: Gtk.Label(label="vacio"))
    for metodo in ("poner_nombre_riel", "finalizadas_del_filtro", "dialogo_finalizada",
                   "elegir_filtro_finalizada"):
        setattr(falso, metodo, types.MethodType(getattr(app.Board, metodo), falso))
    falso.pintar_columnas = lambda: (falso.ventana_finalizada.repintar()
                                     if falso.ventana_finalizada else None)
    return falso


def finalizada(**kw):
    falso = board_falso(**kw)
    indice = [c for c, _ in modelo.COLUMNAS].index(modelo.HECHA)
    caja = app.Board.columna(falso, indice, modelo.HECHA, dict(modelo.COLUMNAS)[modelo.HECHA])
    return falso, caja


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class RielDeFinalizada(unittest.TestCase):
    def test_riel_siempre_visible_de_52_sin_hexpand(self):
        falso, caja = finalizada()
        f = falso.finalizada
        self.assertTrue(f.riel.get_visible())
        self.assertFalse(f.scroll.get_visible())
        self.assertFalse(f.encabezado.get_visible())
        self.assertFalse(caja.get_hexpand())
        self.assertEqual(caja.get_size_request()[0], 52)
        self.assertEqual(app.comun.ANCHO_RIEL, 52)

    def test_el_riel_tiene_el_icono_y_su_conteo_debajo(self):
        falso, _caja = finalizada()
        partes = list(hijos(falso.finalizada.riel))
        self.assertTrue([h for h in partes if isinstance(h, Gtk.Image)])
        self.assertEqual(falso.finalizada.cuenta_riel.get_text(), "0")

    def test_la_lista_oculta_sigue_contando(self):
        falso, _caja = finalizada()
        _lista, cuenta, _scroll = falso.columnas[modelo.HECHA]
        cuenta.set_label("13")
        self.assertEqual(falso.finalizada.riel.get_tooltip_text(), "Finalizada · 13")
        self.assertEqual(falso.finalizada.cuenta_riel.get_text(), "13")

    def test_ya_no_hay_boton_de_plegar(self):
        falso, _caja = finalizada()
        self.assertFalse(hasattr(app.Board, "alternar_finalizada_plegada"))
        textos = [h.get_label() for h in hijos(falso.finalizada.encabezado)
                  if isinstance(h, Gtk.Button) and h.get_label()]
        self.assertNotIn("▷", textos)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede armar la ventana")
class VentanaDeFinalizada(unittest.TestCase):
    def test_tiene_barra_filtro_y_una_fila_por_finalizada(self):
        falso = board_falso([tarea(1, "2026-10-09"), tarea(2, "2026-10-08")])
        d = falso.dialogo_finalizada()
        self.assertEqual(d.get_title(), "Finalizada")
        self.assertEqual(len([h for h in hijos(d) if isinstance(h, Adw.HeaderBar)]), 1)
        botones = [h.get_label() for h in hijos(d) if isinstance(h, Gtk.ToggleButton) and h.get_label()]
        self.assertEqual(botones, [n for _c, n, _d in modelo.FILTROS_FINALIZADA])
        etiquetas = [h.get_label() for h in hijos(d) if isinstance(h, Gtk.Label)]
        self.assertIn("aaaa01", etiquetas)
        self.assertIn("aaaa02", etiquetas)
        self.assertIn("2026-10-09", etiquetas)
        self.assertEqual(len([h for h in hijos(d) if isinstance(h, Gtk.MenuButton)]), 2)

    def test_marca_el_filtro_actual_y_cambiarlo_lo_guarda(self):
        falso = board_falso([tarea(1, "2026-10-09")], filtro="todas")
        d = falso.dialogo_finalizada()
        activos = [h.get_label() for h in hijos(d) if isinstance(h, Gtk.ToggleButton) and h.get_active()]
        self.assertEqual(activos, ["Todas"])
        hoy = [h for h in hijos(d) if isinstance(h, Gtk.ToggleButton) and h.get_label() == "Hoy"][0]
        with mock.patch.object(app.comun, "guardar_board") as guardar:
            hoy.set_active(True)
        guardar.assert_called_with(filtro_finalizada="hoy")
        self.assertEqual(falso.filtro_finalizada, "hoy")

    def test_sin_finalizadas_enseña_el_vacio(self):
        d = board_falso([]).dialogo_finalizada()
        self.assertIn("vacio", [h.get_label() for h in hijos(d) if isinstance(h, Gtk.Label)])

    def test_con_todos_los_proyectos_enseña_el_proyecto(self):
        d = board_falso([tarea(1, "2026-10-09")], seleccion=app.comun.TODOS).dialogo_finalizada()
        self.assertIn("2026-10-09 · Uno",
                      [h.get_label() for h in hijos(d) if isinstance(h, Gtk.Label)])


@unittest.skipUnless(HAY_GTK, "sin GTK no se puede cargar el CSS")
class CssQueGtkEntiende(unittest.TestCase):
    def test_el_css_del_board_carga_sin_errores(self):
        errores = []
        proveedor = Gtk.CssProvider()
        proveedor.connect("parsing-error",
                          lambda _p, _seccion, error: errores.append(error.message))
        proveedor.load_from_string(app.estilo.CSS)
        self.assertEqual(errores, [])


if __name__ == "__main__":
    unittest.main()
