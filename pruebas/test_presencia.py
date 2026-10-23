"""El dot en el board (D5): qué estado toca, dónde se para y cuánto dura.

Sin GTK, la máquina de `tareas/presencia.py` (prioridad, ciclos, Alt+← →, anclas por id) y sus
cuentas de geometría. Con GTK y pantalla, el board de verdad sobre un vault de mentira: se
mueven cartas por las columnas, se finaliza una y se devuelve otra, y en cada paso se mira el
estado del dot y dónde está (si no hay pantalla, se salta).
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import dot, presencia

try:
    from tareas import app  # antes que gi.repository: pide las versiones de GTK 4
    from gi.repository import Gdk, Gio, GLib, Gtk
    HAY_GTK = Gtk.init_check() and Gdk.Display.get_default() is not None
except (ImportError, ValueError):
    HAY_GTK = False


class Ciclos(unittest.TestCase):
    def test_salen_de_las_pistas_del_dot(self):
        self.assertEqual(presencia.ciclo("celebra"), 2.4)
        self.assertEqual(presencia.ciclo("falla"), 5.2)
        self.assertEqual(presencia.ciclo("falla"), dot.PISTAS["falla"]["cuerpo"].duracion)

    def test_piensa_no_esta(self):
        self.assertNotIn("piensa", presencia.DURADEROS + presencia.MOMENTOS)


class Prioridad(unittest.TestCase):
    def setUp(self):
        self.p = presencia.Presencia()

    def test_sin_nada_en_juego_esta_en_el_pie(self):
        self.p.ver([], 0)
        vista = self.p.vigente(0)
        self.assertEqual((vista.estado, vista.ancla), ("idle", presencia.PIE))
        self.assertEqual(vista.etiqueta, "Cotejo: nada en juego")

    def test_trabaja_solo_en_la_primera_carta(self):
        self.p.ver(["a", "b", "c"], 0)
        vista = self.p.vigente(0)
        self.assertEqual(vista.estado, "trabaja")
        self.assertEqual(vista.ancla, presencia.Ancla("carta", "a", "en-curso"))
        self.assertEqual(vista.etiqueta, "Cotejo: 3 tareas en curso")

    def test_comprobar_gana_a_trabaja(self):
        self.p.ver(["a"], 2)
        vista = self.p.vigente(0)
        self.assertEqual((vista.estado, vista.ancla), ("comprobar", presencia.COLUMNA_COMPROBAR))
        self.assertEqual(vista.etiqueta, "Cotejo: 2 tareas esperan que las compruebes")
        self.p.ver(["a"], 1)
        self.assertEqual(self.p.vigente(0).etiqueta, "Cotejo: 1 tarea espera que la compruebes")

    def test_celebra_se_pone_encima_un_ciclo_y_vuelve_el_que_duraba(self):
        self.p.ver(["a"], 1)
        self.p.celebrar(10)
        vista = self.p.vigente(10 + 2.3)
        self.assertEqual((vista.estado, vista.ancla), ("celebra", presencia.RIEL))
        self.assertEqual(self.p.vigente(10 + 2.4).estado, "comprobar")
        self.assertIsNone(self.p.momento)

    def test_falla_va_a_la_carta_devuelta_aunque_sea_pendiente(self):
        self.p.ver([], 0)
        self.p.fallar("cotejo-x", "pendiente", 0)
        vista = self.p.vigente(5.1)
        self.assertEqual(vista.estado, "falla")
        self.assertEqual(vista.ancla, presencia.Ancla("carta", "cotejo-x", "pendiente"))
        self.assertEqual(vista.etiqueta, "Cotejo: devolviste una tarea a Pendiente")
        self.assertEqual(self.p.vigente(5.2).estado, "idle")

    def test_un_momento_nuevo_pisa_al_anterior(self):
        self.p.celebrar(0)
        self.p.fallar("x", "en-curso", 1)
        self.assertEqual(self.p.vigente(2).estado, "falla")
        self.assertEqual(self.p.momento.hasta, 1 + 5.2)

    def test_solo_celebra_y_falla_son_de_un_momento(self):
        with self.assertRaises(ValueError):
            self.p.reaccionar("trabaja", presencia.PIE, 0)


class AltFlechas(unittest.TestCase):
    def setUp(self):
        self.p = presencia.Presencia()
        self.p.ver(["a", "b", "c"], 0)

    def test_pasa_a_la_siguiente_y_vuelve_sin_dar_la_vuelta(self):
        self.assertFalse(self.p.pasar(-1))
        self.assertTrue(self.p.pasar(1))
        self.assertEqual(self.p.vigente(0).ancla.clave, "b")
        self.assertTrue(self.p.pasar(1))
        self.assertFalse(self.p.pasar(1))
        self.assertEqual(self.p.carta_en_curso(), "c")
        self.assertTrue(self.p.pasar(-1))
        self.assertEqual(self.p.carta_en_curso(), "b")

    def test_la_elegida_sobrevive_al_repintado_y_si_sale_vuelve_a_la_primera(self):
        self.p.pasar(1)
        self.p.ver(["a", "b", "c", "d"], 0)
        self.assertEqual(self.p.carta_en_curso(), "b")
        self.p.ver(["a", "c"], 0)
        self.assertEqual(self.p.carta_en_curso(), "a")

    def test_sin_cartas_en_curso_no_hace_nada(self):
        self.p.ver([], 0)
        self.assertFalse(self.p.pasar(1))


class Geometria(unittest.TestCase):
    def test_en_el_pie_a_la_derecha_de_la_barra_y_centrado(self):
        x, y = presencia.en_pie((700, 990, 520, 40), (0, 970, 1900, 76))
        self.assertEqual(x, 700 + 520 + presencia.HUECO_PIE)
        self.assertEqual(y, 970 + (76 - 56) / 2)

    def test_en_la_carta_sentado_en_su_borde_y_al_margen_del_menu(self):
        x, y = presencia.en_carta((600, 190, 450, 80))
        self.assertEqual(y, 190 - 28)
        self.assertLessEqual(x + 56, 600 + 450 - presencia.MARGEN_MENU)

    def test_la_carta_esta_a_la_vista_si_su_borde_de_arriba_se_ve(self):
        vista = (600, 74, 450, 500)
        self.assertTrue(presencia.a_la_vista((600, 74, 450, 80), vista))
        self.assertTrue(presencia.a_la_vista((600, 74 - 0.5, 450, 80), vista))   # redondeos
        self.assertFalse(presencia.a_la_vista((600, 74 - 40, 450, 80), vista))   # se fue arriba
        self.assertFalse(presencia.a_la_vista((600, 74 + 480, 450, 80), vista))  # asoma abajo

    def test_en_el_riel_centrado_y_encima_del_icono(self):
        x, y = presencia.en_riel((1600, 140, 52, 800))
        self.assertEqual(x, 1600 + (52 - 56) / 2)
        self.assertLess(y + 56, 140 + 400 - presencia.ICONO_RIEL / 2)

    def test_el_viaje_va_con_viaje_de_dot(self):
        self.assertEqual(presencia.de_camino((0, 0), (100, 50), 0), (0, 0))
        self.assertEqual(presencia.de_camino((0, 0), (100, 50), dot.VIAJE.duracion), (100, 50))
        x, _y = presencia.de_camino((0, 0), (100, 50), dot.VIAJE.duracion / 2)
        self.assertAlmostEqual(x, 100 * dot.viaje(dot.VIAJE.duracion / 2))
        self.assertTrue(presencia.viaje_terminado(0.9))
        self.assertFalse(presencia.viaje_terminado(0.89))


TAREAS = ("Escribir la primera", "Escribir la segunda", "Entregar la tercera",
          "Entregar la cuarta")


def girar(ms, hasta=None):
    """Hace correr el bucle de GTK `ms` milisegundos, o hasta que `hasta()` sea cierto. En el
    CI (Xvfb) un fotograma tarda lo que tarda: se espera a la condición, no a un reloj."""
    contexto = GLib.MainContext.default()
    limite = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < limite:
        if hasta is not None and hasta():
            return True
        contexto.iteration(False)
    return hasta() if hasta is not None else True


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class ConBoardDot(unittest.TestCase):
    """El board de verdad sobre un vault de mentira, con su propio id de aplicación."""

    animaciones = False
    dot_encendido = True     # el dot es opcional: las pruebas del dot lo encienden en la config
    apps = 0

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        (raiz / "vault" / "01-Proyectos").mkdir(parents=True)
        self.config = raiz / "config.json"
        if self.dot_encendido:
            self.config.write_text('{"dot": true}', encoding="utf-8")
        (raiz / "vault" / "01-Proyectos" / "Faro.md").write_text(
            "---\ntipo: proyecto\n---\n\n# Faro\n\n"
            + "".join(f"- [ ] {t}\n" for t in TAREAS), encoding="utf-8")
        entorno = mock.patch.dict(os.environ, {
            "COTEJO_VAULT": str(raiz / "vault"), "COTEJO_CONFIG": str(self.config),
            "COTEJO_ESTADO": str(raiz / "estado")})
        entorno.start()
        self.addCleanup(entorno.stop)
        # Nada de esto toca la bitácora, ni ofrece integrar ramas, ni pone cosas del usuario.
        for objetivo, nombre, valor in ((app.movimientos.bitacora, "anotar", None),
                                        (app.movimientos.revision, "plan_integracion", None),
                                        (app.App, "poner_lo_del_usuario", None)):
            parche = mock.patch.object(objetivo, nombre, return_value=valor)
            parche.start()
            self.addCleanup(parche.stop)

        ajustes = Gtk.Settings.get_default()
        antes = ajustes.get_property("gtk-enable-animations")
        ajustes.set_property("gtk-enable-animations", self.animaciones)
        self.addCleanup(ajustes.set_property, "gtk-enable-animations", antes)

        self.app = app.App()
        # Un id por prueba: el de una app registrada sigue exportado en D-Bus hasta que muere.
        ConBoardDot.apps += 1
        self.app.set_application_id(f"io.github.cotejoapp.CotejoPruebaDot{os.getpid()}n{self.apps}")
        self.app.set_flags(self.app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        self.app.register(None)
        self.addCleanup(self.cerrar)
        self.app.desde_cero = False      # sin el logo: la entrada va al abrir
        self.app.abrir_board()
        self.board = self.app.board
        # El board abre en Inicio (v1.3.0); el dot vive en el tablero y entra al verlo. El
        # tablero se mide un fotograma después de enseñarse: se espera también a su barra.
        self.board.ver_pestana("tablero")
        if self.dot_encendido:
            girar(5000, hasta=lambda: self.board.dot_entrado and self.board.dot.get_mapped()
                  and self.board.barra_del_maestro.get_width() > presencia.TALLA)

    def cerrar(self):
        for monitor in self.app.monitores:
            monitor.cancel()
        if self.app.board is not None:
            self.app.board.destroy()
        self.app.release()

    # --- ayudas ---------------------------------------------------------------------------------

    def fila(self, texto):
        for clave in self.board.orden:
            for fila in self.board.cartas(self.board.columnas[clave][0]):
                if fila.tarea is not None and fila.tarea.texto == texto:
                    return fila
        self.fail(f"no está la carta {texto!r}")

    def mover(self, texto, destino):
        fila = self.fila(texto)
        self.board.mover(fila.proyecto, fila.tarea, destino)
        girar(60)

    def devolver(self, texto, destino):
        """Lo que hace el diálogo «Devolver a…» al confirmar con un motivo."""
        fila = self.fila(texto)
        self.board.al_responder_motivo(None, "devolver", Gtk.Entry(text="le falta la prueba"),
                                       fila.proyecto, fila.tarea, destino)
        girar(60)

    def acabar_momento(self):
        """El ciclo de celebra o falla, sin esperarlo de verdad."""
        momento = self.board.presencia.momento
        self.board.presencia.momento = momento._replace(hasta=0)
        self.board.al_acabar_momento()
        girar(60)

    def donde(self):
        hecho, r = self.board.dot.compute_bounds(self.board.encima)
        return (r.get_x(), r.get_y()) if hecho else None

    def esperado(self, x_y):
        return round(x_y[0]), round(x_y[1])

    def ya_esta(self, ancla, posicion):
        try:
            return self.board.dot_ancla == ancla and self.donde() == self.esperado(posicion())
        except TypeError:        # una caja sin asignar todavía: compute_bounds no la da
            return False

    def caja(self, widget):
        return self.board.caja_en_encima(widget)

    def comprobar(self, estado, ancla, posicion):
        """Estado, ancla y sitio del dot. `posicion` se llama al comprobar: la posición llega
        con la siguiente asignación del overlay, y en el CI se espera a ella."""
        girar(3000, hasta=lambda: self.ya_esta(ancla, posicion))
        self.assertEqual(self.board.dot.get_property("estado"), estado)
        self.assertEqual(self.board.dot_ancla, ancla)
        self.assertEqual(self.donde(), self.esperado(posicion()), self.diagnostico())

    def diagnostico(self):
        """Lo que hace falta para entender un fallo en el CI sin poder mirar la ventana."""
        b = self.board
        partes = [f"ventana {b.get_width()}×{b.get_height()}", f"ancla {b.dot_ancla}"]
        for clave in ("en-curso", "por-validar", "pendiente"):
            lista, _cuenta, scroll = b.columnas[clave]
            partes.append(f"{clave}: scroll {self.caja(scroll)} "
                          f"v={scroll.get_vadjustment().get_value()} cartas "
                          + ", ".join(f"{f.clave}@{self.caja(f)}" for f in b.cartas(lista)))
        return " | ".join(partes)

    def en_pie(self):
        return presencia.en_pie(self.caja(self.board.barra_del_maestro), self.caja(self.board.pie))


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class DotEnElBoard(ConBoardDot):
    # --- la prueba --------------------------------------------------------------------------------

    def test_el_dot_sigue_a_las_cartas(self):
        b = self.board
        ancho_barra = self.caja(b.barra_del_maestro)[2]
        # Entra en el pie, en el overlay y sin tocar la barra del maestro.
        self.assertTrue(b.dot.get_visible())
        self.assertIs(b.dot.get_parent(), b.encima)
        self.assertFalse(b.dot.get_can_target())
        self.comprobar("idle", presencia.PIE, self.en_pie)
        self.assertEqual(self.caja(b.barra_del_maestro)[2], ancho_barra)
        self.assertEqual(b.dot.get_etiqueta(), "Cotejo: nada en juego")

        # Dos a Haciéndola: trabaja, y solo sobre la primera.
        self.mover(TAREAS[0], "en-curso")
        self.mover(TAREAS[1], "en-curso")
        primera, segunda = self.fila(TAREAS[0]), self.fila(TAREAS[1])
        self.comprobar("trabaja", presencia.Ancla("carta", primera.clave, "en-curso"),
                       lambda: presencia.en_carta(self.caja(self.fila(TAREAS[0]))))
        self.assertEqual(b.dot.get_etiqueta(), "Cotejo: 2 tareas en curso")

        # Alt+→ la pasa a la segunda; Alt+← la devuelve. Las flechas solas no son del dot.
        alt = Gdk.ModifierType.ALT_MASK
        self.assertFalse(b.al_tecla_dot(None, Gdk.KEY_Right, 0, 0))
        self.assertFalse(b.al_tecla_dot(None, Gdk.KEY_Right, 0, Gdk.ModifierType.CONTROL_MASK))
        self.assertTrue(b.al_tecla_dot(None, Gdk.KEY_Right, 0, alt))
        girar(60)
        self.comprobar("trabaja", presencia.Ancla("carta", segunda.clave, "en-curso"),
                       lambda: presencia.en_carta(self.caja(self.fila(TAREAS[1]))))
        self.assertTrue(b.al_tecla_dot(None, Gdk.KEY_Left, 0, alt))
        girar(60)
        self.assertEqual(b.dot_ancla.clave, self.fila(TAREAS[0]).clave)

        # Dos a Para comprobar: comprobar gana, al borde de la columna.
        for texto in TAREAS[2:]:
            self.mover(texto, "en-curso")
            self.mover(texto, "por-validar")
        columna = b.columnas["por-validar"][2].get_parent()
        self.comprobar("comprobar", presencia.COLUMNA_COMPROBAR,
                       lambda: presencia.en_columna(self.caja(columna)))
        self.assertEqual(b.dot.get_etiqueta(), "Cotejo: 2 tareas esperan que las compruebes")
        # Con comprobar delante, Alt+→ no se lo queda: sigue siendo de las columnas.
        self.assertFalse(b.al_tecla_dot(None, Gdk.KEY_Right, 0, alt))

        # Finalizar una: celebra sobre el riel, un ciclo, y vuelve comprobar (queda una).
        self.mover(TAREAS[2], "hecha")
        self.comprobar("celebra", presencia.RIEL, lambda: presencia.en_riel(self.caja(b.finalizada.riel)))
        self.acabar_momento()
        self.comprobar("comprobar", presencia.COLUMNA_COMPROBAR,
                       lambda: presencia.en_columna(self.caja(columna)))
        self.assertEqual(b.dot.get_etiqueta(), "Cotejo: 1 tarea espera que la compruebes")

        # Devolver la otra a Pendiente: falla sobre la carta devuelta, en Pendiente.
        self.devolver(TAREAS[3], "pendiente")
        devuelta = self.fila(TAREAS[3])
        self.assertEqual(devuelta.tarea.columna, "pendiente")
        self.comprobar("falla", presencia.Ancla("carta", devuelta.clave, "pendiente"),
                       lambda: presencia.en_carta(self.caja(self.fila(TAREAS[3]))))
        self.assertEqual(b.dot.get_etiqueta(), "Cotejo: devolviste una tarea a Pendiente")
        # Y al acabar el ciclo, lo que duraba: las dos que siguen en curso.
        self.acabar_momento()
        self.comprobar("trabaja", presencia.Ancla("carta", self.fila(TAREAS[0]).clave, "en-curso"),
                       lambda: presencia.en_carta(self.caja(self.fila(TAREAS[0]))))

        # Sin nada en juego vuelve a casa.
        for texto in TAREAS[:2]:
            self.mover(texto, "pendiente")
        self.comprobar("idle", presencia.PIE, self.en_pie)


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class ViajeConAnimaciones(DotEnElBoard):
    """Con animaciones, el dot entra en el pie y viaja con `VIAJE`; no salta."""

    animaciones = True

    def test_el_dot_sigue_a_las_cartas(self):
        b = self.board
        girar(3000, hasta=lambda: not b.dot_entrando)   # la entrada, en el pie
        self.comprobar("idle", presencia.PIE, self.en_pie)
        salida = self.donde()
        self.mover(TAREAS[0], "en-curso")
        self.assertIsNotNone(b.dot_viaje)
        # Se apunta por dónde pasa hasta que llega: no salta, pasa por sitios intermedios.
        vistos = []
        girar(5000, hasta=lambda: vistos.append(self.donde()) or b.dot_viaje is None)
        self.assertIsNone(b.dot_viaje)
        llegada = self.esperado(presencia.en_carta(self.caja(self.fila(TAREAS[0]))))
        self.comprobar("trabaja", b.dot_ancla, lambda: presencia.en_carta(
            self.caja(self.fila(TAREAS[0]))))
        intermedios = {v for v in vistos if v not in (salida, llegada)}
        self.assertTrue(intermedios, f"el dot saltó de {salida} a {llegada} sin viajar")


if __name__ == "__main__":
    unittest.main()
