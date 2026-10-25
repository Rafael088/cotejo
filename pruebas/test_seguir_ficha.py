"""La ficha abierta sigue a la tarea (v1.3.0, cotejo-v66btg).

La decisión (`tareas/seguir_ficha.py`) se prueba sin GTK; la parte de la ventana, con un Board
falso, solo si hay GTK.
"""

import types
import unittest

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import modelo, seguir_ficha

try:
    from tareas import app
    from gi.repository import Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def tarea(id_, estado="pendiente", hecha=False):
    return modelo.Tarea("Algo que hacer", id=id_, estado=estado, hecha=hecha)


def proyecto(*tareas):
    return types.SimpleNamespace(
        nombre="P", tareas=[t for t in tareas if not t.hecha], hechas=[t for t in tareas if t.hecha])


class Decidir(unittest.TestCase):
    def test_sin_cambios_sigue_igual(self):
        t = tarea("cotejo-a1b2c3", "en-curso")
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, t.columna)
        self.assertEqual(seguir_ficha.decidir(abierta, [proyecto(t)], lambda _: False),
                         (seguir_ficha.IGUAL,))

    def test_de_haciendo_a_para_comprobar_con_entrega_abre_la_revision(self):
        antes = tarea("cotejo-a1b2c3", "en-curso")
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, antes.columna)
        ahora = tarea("cotejo-a1b2c3", "por-validar")
        decision = seguir_ficha.decidir(abierta, [proyecto(ahora)], lambda _: True)
        self.assertEqual(decision[0], seguir_ficha.CAMBIA)
        self.assertIs(decision[2], ahora)
        self.assertEqual(decision[3], seguir_ficha.REVISION)

    def test_para_comprobar_sin_entrega_es_detalle_nuevo(self):
        antes = tarea("cotejo-a1b2c3", "en-curso")
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, antes.columna)
        decision = seguir_ficha.decidir(
            abierta, [proyecto(tarea("cotejo-a1b2c3", "por-validar"))], lambda _: False)
        self.assertEqual((decision[0], decision[3]), (seguir_ficha.CAMBIA, seguir_ficha.DETALLE))

    def test_sin_terminar_vuelve_a_pendiente(self):
        antes = tarea("cotejo-a1b2c3", "en-curso")
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, antes.columna)
        decision = seguir_ficha.decidir(
            abierta, [proyecto(tarea("cotejo-a1b2c3", "pendiente"))], lambda _: False)
        self.assertEqual(decision[0], seguir_ficha.CAMBIA)

    def test_la_entrega_llega_estando_ya_en_para_comprobar(self):
        t = tarea("cotejo-a1b2c3", "por-validar")
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, t.columna)
        self.assertEqual(seguir_ficha.decidir(abierta, [proyecto(t)], lambda _: True)[0],
                         seguir_ficha.CAMBIA)

    def test_aprobada_se_encuentra_entre_las_hechas(self):
        antes = tarea("cotejo-a1b2c3", "por-validar")
        abierta = ("cotejo-a1b2c3", seguir_ficha.REVISION, antes.columna)
        hecha = tarea("cotejo-a1b2c3", "por-validar", hecha=True)
        decision = seguir_ficha.decidir(abierta, [proyecto(hecha)], lambda _: False)
        self.assertEqual((decision[0], decision[3]), (seguir_ficha.CAMBIA, seguir_ficha.DETALLE))

    def test_si_la_tarea_ya_no_esta_desaparece(self):
        abierta = ("cotejo-a1b2c3", seguir_ficha.DETALLE, "pendiente")
        self.assertEqual(seguir_ficha.decidir(abierta, [proyecto(tarea("cotejo-otra"))],
                                              lambda _: False), (seguir_ficha.DESAPARECE,))

    def test_el_id_viejo_foco_es_la_misma_tarea(self):
        t = tarea("cotejo-a1b2c3", "en-curso")
        abierta = ("foco-a1b2c3", seguir_ficha.DETALLE, t.columna)
        self.assertEqual(seguir_ficha.decidir(abierta, [proyecto(t)], lambda _: False),
                         (seguir_ficha.IGUAL,))


class Falso:
    """Un Board mínimo: un diálogo que anota si se cerró y las llamadas de la ficha."""

    def __init__(self, proyectos, entrega=False, problema=None):
        self.app = types.SimpleNamespace(proyectos=proyectos)
        self.fuente = types.SimpleNamespace(problema=problema)
        self.entrega = entrega
        self.avisos, self.abiertas = [], []
        self.entrega_de = lambda t: {"operacion": "entregar"} if self.entrega else None
        self.aviso = self.avisos.append
        self.ver_revision = lambda p, t: self.abiertas.append(("revision", t.id)) or object()
        self.ver_detalle = lambda p, t: self.abiertas.append(("detalle", t.id))
        self.seguir_ficha = types.MethodType(app.Board.seguir_ficha, self)


class Cierre:
    def __init__(self):
        self.cerrado = False

    def close(self):
        self.cerrado = True


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el Board")
class SeguirFichaEnLaVentana(unittest.TestCase):
    def abierta(self, falso, columna="en-curso"):
        dialogo = Cierre()
        falso.ficha_abierta = (dialogo, ("cotejo-a1b2c3", seguir_ficha.DETALLE, columna))
        return dialogo

    def test_sin_ficha_no_hace_nada(self):
        falso = Falso([proyecto(tarea("cotejo-a1b2c3"))])
        falso.seguir_ficha()
        self.assertEqual(falso.abiertas, [])

    def test_el_agente_entrega_la_ficha_pasa_a_la_revision(self):
        falso = Falso([proyecto(tarea("cotejo-a1b2c3", "por-validar"))], entrega=True)
        dialogo = self.abierta(falso)
        falso.seguir_ficha()
        self.assertTrue(dialogo.cerrado)
        self.assertEqual(falso.abiertas, [("revision", "cotejo-a1b2c3")])

    def test_termina_sin_entregar_la_ficha_pasa_al_detalle(self):
        falso = Falso([proyecto(tarea("cotejo-a1b2c3", "pendiente"))])
        self.abierta(falso)
        falso.seguir_ficha()
        self.assertEqual(falso.abiertas, [("detalle", "cotejo-a1b2c3")])

    def test_si_la_revision_no_se_puede_armar_cae_al_detalle(self):
        falso = Falso([proyecto(tarea("cotejo-a1b2c3", "por-validar"))], entrega=True)
        falso.ver_revision = lambda p, t: None
        self.abierta(falso)
        falso.seguir_ficha()
        self.assertEqual(falso.abiertas, [("detalle", "cotejo-a1b2c3")])

    def test_la_tarea_desaparece_se_cierra_y_se_avisa(self):
        falso = Falso([proyecto(tarea("cotejo-otra"))])
        dialogo = self.abierta(falso)
        falso.seguir_ficha()
        self.assertTrue(dialogo.cerrado)
        self.assertEqual(falso.abiertas, [])
        self.assertEqual(len(falso.avisos), 1)
        self.assertIsNone(falso.ficha_abierta)

    def test_si_la_fuente_falla_la_ficha_se_queda(self):
        falso = Falso([], problema="no responde")
        dialogo = self.abierta(falso)
        falso.seguir_ficha()
        self.assertFalse(dialogo.cerrado)
        self.assertEqual(falso.avisos, [])

    def test_sin_cambios_no_se_toca(self):
        falso = Falso([proyecto(tarea("cotejo-a1b2c3", "en-curso"))])
        dialogo = self.abierta(falso)
        falso.seguir_ficha()
        self.assertFalse(dialogo.cerrado)


if __name__ == "__main__":
    unittest.main()
