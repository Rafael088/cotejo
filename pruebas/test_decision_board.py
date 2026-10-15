"""La carta de una decisión propuesta en CotejoBoard (C5, v1.2 · E2): carta propia en *Para
comprobar*, se abre con la vista de revisión y el único botón que escribe es Aceptar.

Construye los widgets de verdad con un Board falso —solo lo que cada método lee—, sin abrir
ventana, igual que `test_menu_carta.py` y `test_revision.py`. La lógica de aceptar (propuesta→
aceptada, el reemplazo, la versión vieja) ya se prueba sin GTK en `test_decision.py`; aquí solo
se vigila que el board la llame bien y pinte lo que toca.
"""

import tempfile
import types
import unittest
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import decision, modelo
from tareas.almacen import Almacen

try:
    from gi.repository import Gtk

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


def textos(widget):
    return [h.get_label() for h in hijos(widget) if isinstance(h, Gtk.Label)]


class ConAlmacen(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        (self.repo / ".git").mkdir(parents=True)
        self.almacen = Almacen(self.repo)


def board_falso(**extra):
    base = dict(avisos=[], pintadas=0, abiertas=[])
    base.update(extra)
    falso = types.SimpleNamespace(**base)
    falso.aviso = falso.avisos.append
    falso.pintar = lambda: setattr(falso, "pintadas", falso.pintadas + 1)
    # Estáticos: se llaman tal cual, sin `self`.
    falso.con_icono = app.Board.con_icono
    falso.titulo_seccion = app.Board.titulo_seccion
    falso._es_carta = app.Board._es_carta
    # De instancia: atados a `falso` como si fuera el Board de verdad.
    for nombre in ("carta_decision", "al_activar", "cartas", "mover_con_teclado",
                  "aceptar_decision", "panel_decision"):
        setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
    falso.ver_revision_decision = lambda proyecto, alm, entrada: falso.abiertas.append(entrada.id)
    falso.ver_detalle = lambda proyecto, tarea: falso.abiertas.append(("detalle", tarea.id))
    falso.mover = lambda proyecto, tarea, destino: (_ for _ in ()).throw(
        AssertionError("una decisión no se mueve de columna"))
    return falso


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class LaCartaDeUnaDecision(ConAlmacen):

    def test_trae_el_chip_y_el_titulo_y_no_es_una_tarea(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila = falso.carta_decision(None, self.almacen, entrada)
        self.assertIsNone(fila.tarea)
        self.assertEqual(fila.decision, (self.almacen, entrada))
        self.assertEqual(fila.clave, f"decision:{entrada.id}")
        self.assertIn("Decisión propuesta", textos(fila))
        self.assertIn("Usar JWT", textos(fila))

    def test_sin_reemplaza_no_dice_nada_de_reemplazar(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila = falso.carta_decision(None, self.almacen, entrada)
        self.assertFalse(any("Reemplaza" in t for t in textos(fila)))

    def test_con_reemplaza_lo_dice_en_la_carta(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)
        falso = board_falso()
        fila = falso.carta_decision(None, self.almacen, nueva)
        self.assertTrue(any(vieja.id in t for t in textos(fila)))

    def test_no_tiene_menu_de_tres_puntos(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila = falso.carta_decision(None, self.almacen, entrada)
        self.assertIsNone(getattr(fila, "boton_menu", None))


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class AlActivarYElTeclado(ConAlmacen):

    def test_al_activar_una_carta_de_decision_abre_su_revision_y_no_abrir(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila = falso.carta_decision("Uno", self.almacen, entrada)
        falso.al_activar(None, fila)
        self.assertEqual(falso.abiertas, [entrada.id])

    def test_al_activar_una_entrega_abre_su_revision(self):
        tarea = modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="x.md", estado="por-validar")
        falso = board_falso()
        falso.entrega_de = lambda t: {"operacion": "entregar"}
        falso.ver_revision = lambda proyecto, t: falso.abiertas.append(("revision", t.id))
        fila = types.SimpleNamespace(tarea=tarea, decision=None, proyecto=None)
        falso.al_activar(None, fila)
        self.assertEqual(falso.abiertas, [("revision", "cotejo-aaa111")])

    def test_al_activar_cualquier_otra_tarea_abre_su_ficha_y_nunca_la_app(self):
        for estado in ("pendiente", "en-curso", "por-validar", "hecha"):
            hecha = estado == modelo.HECHA
            tarea = modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="x.md",
                                 estado="por-validar" if hecha else estado, hecha=hecha)
            falso = board_falso()
            falso.entrega_de = lambda t: None
            falso.al_activar(None, types.SimpleNamespace(tarea=tarea, decision=None, proyecto=None))
            self.assertEqual(falso.abiertas, [("detalle", "cotejo-aaa111")], estado)

    def test_cartas_cuenta_las_de_decision_pero_no_las_filas_quietas(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila_decision = falso.carta_decision(None, self.almacen, entrada)
        fila_quieta = Gtk.ListBoxRow(child=Gtk.Label(label="encabezado"), activatable=False)
        lista = Gtk.ListBox()
        lista.append(fila_decision)
        lista.append(fila_quieta)
        self.assertEqual(falso.cartas(lista), [fila_decision])

    def test_mover_con_teclado_no_hace_nada_con_una_carta_de_decision(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        fila = falso.carta_decision(None, self.almacen, entrada)
        self.assertTrue(falso.mover_con_teclado(fila, 1))  # no lanza AssertionError de `mover`


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class AceptarDesdeElBoard(ConAlmacen):

    def test_aceptar_avisa_y_repinta(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        falso.aceptar_decision(None, self.almacen, entrada)
        self.assertEqual(self.almacen.leer(entrada.id).estado, "aceptada")
        self.assertEqual(falso.pintadas, 1)
        self.assertIn(f"«{entrada.id}» aceptada", falso.avisos[0])

    def test_aceptar_con_reemplazo_avisa_de_las_dos(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)
        falso = board_falso()
        falso.aceptar_decision(None, self.almacen, nueva)
        self.assertIn(vieja.id, falso.avisos[0])
        self.assertEqual(self.almacen.leer(vieja.id).estado, "reemplazada")

    def test_version_vieja_avisa_y_no_repinta_ni_escribe(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón.")
        falso = board_falso()
        falso.aceptar_decision(None, self.almacen, types.SimpleNamespace(
            id=entrada.id, version="vieja"))
        self.assertEqual(falso.pintadas, 0)
        self.assertEqual(self.almacen.leer(entrada.id).estado, "propuesta")
        self.assertTrue(falso.avisos)

    def test_aceptacion_parcial_avisa_y_repinta_porque_la_nueva_si_quedo_aceptada(self):
        vieja = self.almacen.crear("decision", "Usar sesiones", "Vieja.")
        self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        vieja = self.almacen.leer(vieja.id)
        nueva = self.almacen.crear("decision", "Usar JWT", "Nueva.", reemplaza=vieja.id)
        # La vieja queda reemplazada por otro camino antes de que se acepte la nueva.
        self.almacen.poner_estado(vieja.id, vieja.version, "reemplazada",
                                  campos={"reemplazada_por": "dec-otra"})
        falso = board_falso()
        falso.aceptar_decision(None, self.almacen, nueva)
        self.assertEqual(falso.pintadas, 1)
        self.assertEqual(self.almacen.leer(nueva.id).estado, "aceptada")
        self.assertIn("quedó aceptada", falso.avisos[0])


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden construir los widgets")
class PanelDeDecision(ConAlmacen):

    def test_pinta_titulo_texto_y_lo_que_lo_describe(self):
        entrada = self.almacen.crear("decision", "Usar JWT", "La razón completa.",
                                     temas=["auth"], autor="opus")
        falso = board_falso()
        datos = decision.para_revisar(self.almacen, entrada)
        caja = falso.panel_decision("PROPUESTA", datos)
        vistos = textos(caja)
        self.assertIn("Usar JWT", vistos)
        self.assertTrue(any("La razón completa." in t for t in vistos))
        self.assertTrue(any("opus" in t and "auth" in t for t in vistos))


if __name__ == "__main__":
    unittest.main()
