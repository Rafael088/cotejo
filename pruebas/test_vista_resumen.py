"""La revisión para quien no programa: resumen arriba, frase de pruebas y qué hacer; el diff debajo."""

import types
import unittest
from unittest import mock

from test_revision import board_falso, entrega, hijos, tarea_por_validar

from tareas import modelo, revision

RESUMEN = "Ahora Guardar avisa al terminar. Pruébalo: abre un archivo y pulsa Guardar."

try:
    from gi.repository import Adw, Gtk

    from tareas import app
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


class LaFrase(unittest.TestCase):
    def test_los_tres_casos(self):
        self.assertEqual(revision.frase_pruebas(entrega(pruebas=(0, 0, 0))),
                         "Las 3 pruebas que dejó el agente pasaron.")
        self.assertEqual(revision.frase_pruebas(entrega(pruebas=(0, 1, None))),
                         "2 de 3 pruebas fallaron.")
        self.assertEqual(revision.frase_pruebas(entrega()),
                         "El agente no dejó pruebas que repetir.")

    def test_no_cuela_la_salida(self):
        anotacion = entrega(pruebas=(1,))
        anotacion["pruebas"][0]["salida"] = "Traceback secreto"
        self.assertNotIn("Traceback", revision.frase_pruebas(anotacion))


def abrir(anotacion):
    falso = board_falso(anotacion)
    for nombre in ("ver_revision", "bloque_resumen"):
        clase = app.Board
        setattr(falso, nombre, types.MethodType(getattr(clase, nombre), falso))
    for nombre in ("titulo_seccion", "fila_prueba", "archivo_del_diff", "lineas_del_diff"):
        setattr(falso, nombre, getattr(app.Board, nombre))
    falso.archivo_del_diff = types.MethodType(app.Board.archivo_del_diff, falso)
    falso.abrir_en_herramienta = lambda *a: None
    falso.seccion_en_vivo = lambda _tarea: None
    falso.registrar_ficha = lambda *a: None
    falso.presentados = []
    with mock.patch.object(Adw.Dialog, "present", lambda d, padre: falso.presentados.append(d)), \
            mock.patch("tareas.revision.carpeta_git", lambda *a: None), \
            mock.patch("tareas.revision.diff", lambda *a: []):
        falso.ver_revision(None, tarea_por_validar())
    return falso


def textos(widget):
    return [h.get_label() for h in hijos(widget) if isinstance(h, Gtk.Label)]


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede armar el diálogo")
class LaVista(unittest.TestCase):
    def test_con_resumen_sale_arriba_y_en_orden(self):
        anotacion = entrega(pruebas=(0, 0), archivos=[{"ruta": "a.py", "mas": 1, "menos": 0}])
        anotacion["resumen"] = RESUMEN
        falso = abrir(anotacion)
        t = textos(falso.presentados[0].get_child())
        orden = [t.index(x) for x in (RESUMEN, "Las 2 pruebas que dejó el agente pasaron.",
                                      "QUÉ HACER", "PRUEBAS", "a.py")]
        # el resumen, la frase y «qué hacer» van antes de la evidencia («PRUEBAS» a secas)
        self.assertEqual(orden, sorted(orden))
        self.assertLess(t.index(RESUMEN), t.index("PRUEBAS"))

    def test_los_dos_caminos_reusan_las_acciones_del_board(self):
        anotacion = entrega(pruebas=(0,))
        anotacion["resumen"] = RESUMEN
        falso = abrir(anotacion)
        botones = {}
        for b in hijos(falso.presentados[0].get_child()):
            if isinstance(b, Gtk.Button):
                etiqueta = next((h.get_label() for h in hijos(b) if isinstance(h, Gtk.Label)), None)
                if etiqueta:
                    botones.setdefault(etiqueta, b)    # el de la cabecera es el mismo verbo
        botones["Devolver y decir por qué"].emit("clicked")
        botones["Aprobar"].emit("clicked")
        self.assertEqual(falso.movidas, ["en-curso", modelo.HECHA])

    def test_sin_resumen_queda_como_hoy(self):
        falso = abrir(entrega(pruebas=(0,)))
        t = textos(falso.presentados[0].get_child())
        self.assertNotIn("QUÉ HACER", t)
        self.assertNotIn("QUÉ CAMBIÓ Y CÓMO PROBARLO", t)
        self.assertIn("PRUEBAS", t)

    def test_la_carta_ofrece_revisar_si_solo_hay_resumen(self):
        falso = board_falso({"operacion": "entregar", "evidencia": "hecho", "resumen": RESUMEN})
        caja = falso.revision_en_carta(None, tarea_por_validar())
        self.assertIn("Revisar", textos(caja))
