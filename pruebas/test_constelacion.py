"""La constelación de proyectos del Inicio (v1.3.0, cotejo-7wc9hb).

Tres capas, de abajo arriba:

- La geometría y los colores sin GTK (`tareas/constelacion.py`): dónde cae cada núcleo y cada
  pieza, que el verde sea solo para lo que espera comprobación y que quieta no se mueva.
- El dibujo de verdad con cairo, sobre una superficie en memoria y con los colores del tema de
  fábrica: el píxel de cada pieza es el de su estado.
- El widget y el board (con GTK y pantalla; si no, se saltan): con las animaciones apagadas no
  hay reloj de fotogramas, y el Inicio pinta la constelación con los proyectos que lee de una
  fuente de repos de prueba, con sus piezas de arquitectura.
"""

import math
import os
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import cairo

from tareas import almacen, temas
from tareas import constelacion as c

try:
    from tareas import app  # antes que gi.repository: pide las versiones de GTK 4
    from tareas.app import constelacion as widget_constelacion
    from tareas.app import pestana_inicio
    from gi.repository import Gio, GLib, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False

COLORES = temas.cargar("oscuro")["colores"]

PIEZAS = """# Mapa

## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Horarios | La lista de turnos libres | HTML | t-dos |
| hace | Reservar | Aparta el turno | JS | t-uno |
| guarda | Turnos | Cada reserva | Sheets | t-cuatro |
| conecta | Avisos | Recordatorio por WhatsApp | API | |
"""


def proyecto(nombre, estados):
    return types.SimpleNamespace(nombre=nombre, estados=list(estados))


def color_de(token):
    r, g, b, _ = temas.color(COLORES[token])
    return r, g, b


def pixel(superficie, x, y):
    """(r, g, b) en 0-255 del píxel (x, y) de una superficie ARGB32 (premultiplicada, opaca)."""
    datos = superficie.get_data()
    i = int(y) * superficie.get_stride() + int(x) * 4
    b, g, r = datos[i], datos[i + 1], datos[i + 2]
    return r, g, b


def cerca(uno, otro, margen=12):
    return all(abs(a - b) <= margen for a, b in zip(uno, otro))


class Colores(unittest.TestCase):
    def test_el_verde_es_solo_para_lo_que_espera_comprobacion(self):
        for estado, e in c.ESTILOS.items():
            usa_senal = "senal" in (e["relleno"], e["trazo"])
            self.assertEqual(usa_senal, estado == "por-comprobar", estado)
        self.assertNotIn("senal", (c.LINEA, c.NUCLEO, c.NUCLEO_VACIO, c.FONDO))

    def test_un_estado_desconocido_no_sale_en_verde(self):
        self.assertIs(c.estilo("raro"), c.ESTILOS["falta"])

    def test_cada_estado_de_la_arquitectura_tiene_estilo_y_nombre(self):
        from tareas import arquitectura
        self.assertEqual(set(c.ESTILOS), set(arquitectura.ESTADOS))
        self.assertEqual(set(c.ESTADOS_LEYENDA), set(arquitectura.ESTADOS))

    def test_los_tokens_existen_en_el_tema(self):
        usados = {c.LINEA, c.NUCLEO, c.NUCLEO_VACIO, c.FONDO}
        for e in c.ESTILOS.values():
            usados |= {e["trazo"], e["relleno"] or c.FONDO}
        self.assertLessEqual(usados, set(temas.TOKENS))


class Geometria(unittest.TestCase):
    def test_un_nucleo_por_proyecto_y_un_punto_por_pieza(self):
        nucleos = c.disponer([proyecto("a", ["hecho", "falta"]), proyecto("b", [])], 800)
        self.assertEqual([n.nombre for n in nucleos], ["a", "b"])
        self.assertEqual([p.estado for p in nucleos[0].puntos], ["hecho", "falta"])
        self.assertFalse(nucleos[1].con_arquitectura)

    def test_filas_de_cuatro_como_mucho_y_la_ultima_centrada(self):
        nucleos = c.disponer([proyecto(str(i), ["hecho"]) for i in range(6)], 1000)
        self.assertEqual(c.columnas_para(6, 1000), 4)
        self.assertEqual(c.alto_para(6, 1000), 2 * c.ALTO_FILA)
        filas = {round(n.celda[1]) for n in nucleos}
        self.assertEqual(filas, {0, c.ALTO_FILA})
        segunda = [n for n in nucleos if n.celda[1] > 0]
        self.assertAlmostEqual((segunda[0].x + segunda[1].x) / 2, 500)

    def test_estrecho_pone_menos_por_fila(self):
        self.assertEqual(c.columnas_para(4, 450), 2)
        self.assertEqual(c.columnas_para(4, 100), 1)
        self.assertEqual(c.alto_para(0, 800), 0)

    def test_todo_cae_dentro_de_su_celda(self):
        for ancho in (220, 500, 1080):
            estados = ["hecho", "en-curso", "por-comprobar", "falta"] * 4
            for nucleo in c.disponer([proyecto(str(i), estados) for i in range(5)], ancho):
                x0, y0, celda, alto = nucleo.celda
                for punto in nucleo.puntos:
                    for t in (0, 1.3, 7.9):
                        x, y = c.posicion(nucleo, punto, t, quieto=False)
                        self.assertTrue(x0 <= x <= x0 + celda, (ancho, x, nucleo.celda))
                        self.assertTrue(y0 <= y <= y0 + alto, (ancho, y, nucleo.celda))

    def test_quieta_no_se_mueve_y_animada_si(self):
        [nucleo] = c.disponer([proyecto("a", ["hecho", "falta", "en-curso"])], 600)
        punto = nucleo.puntos[1]
        quieta = {c.posicion(nucleo, punto, t, quieto=True) for t in (0, 0.5, 3, 11)}
        self.assertEqual(len(quieta), 1)
        animada = {c.posicion(nucleo, punto, t, quieto=False) for t in (0, 0.5, 3, 11)}
        self.assertGreater(len(animada), 1)
        # Se mece, no se va: como mucho DERIVA radianes alrededor de su ángulo.
        x0, y0 = quieta.pop()
        for x, y in animada:
            self.assertLess(math.hypot(x - x0, y - y0), punto.radio * c.DERIVA * 1.01 + 1e-9)

    def test_tocar_una_celda_da_su_nucleo(self):
        nucleos = c.disponer([proyecto("a", []), proyecto("b", [])], 600)
        self.assertEqual(c.nucleo_en(nucleos, 10, 10).nombre, "a")
        self.assertEqual(c.nucleo_en(nucleos, 590, 100).nombre, "b")
        self.assertIsNone(c.nucleo_en(nucleos, 300, c.ALTO_FILA + 5))

    def test_descripcion_para_el_lector_de_pantalla(self):
        texto = c.descripcion([proyecto("faro", ["hecho", "por-comprobar", "falta"]),
                               proyecto("nuevo", [])])
        self.assertIn("faro, 1 de 3 piezas hechas, 1 esperan que las compruebes", texto)
        self.assertIn("nuevo, sin arquitectura todavía", texto)


class Dibujo(unittest.TestCase):
    """Con cairo de verdad: cada pieza sale del color de su estado."""

    def pintar(self, proyectos, ancho=600, t=0.0, quieto=True):
        nucleos = c.disponer(proyectos, ancho)
        alto = c.alto_para(len(proyectos), ancho)
        sup = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
        cr = cairo.Context(sup)
        cr.set_source_rgba(*c.rgba(COLORES, c.FONDO))
        cr.paint()
        pintadas = c.dibujar(cr, nucleos, COLORES, t, quieto)
        sup.flush()
        return sup, nucleos, pintadas

    def test_cada_pieza_del_color_de_su_estado(self):
        estados = ["hecho", "en-curso", "por-comprobar", "falta"]
        sup, [nucleo], pintadas = self.pintar([proyecto("faro", estados)])
        self.assertEqual(pintadas, 4)
        senal = color_de("senal")
        for punto in nucleo.puntos:
            x, y = c.posicion(nucleo, punto)
            centro = pixel(sup, x, y)
            if punto.estado == "hecho":
                self.assertTrue(cerca(centro, color_de("texto")), centro)
            elif punto.estado == "por-comprobar":
                self.assertTrue(cerca(centro, senal), centro)
            else:   # en curso y falta son anillos: por dentro, el fondo
                self.assertTrue(cerca(centro, color_de(c.FONDO)), (punto.estado, centro))
        # El núcleo, del color del texto.
        self.assertTrue(cerca(pixel(sup, nucleo.x, nucleo.y), color_de("texto")))

    def test_sin_nada_por_comprobar_no_hay_verde(self):
        sup, _, _ = self.pintar([proyecto("a", ["hecho", "en-curso", "falta"] * 3),
                                 proyecto("b", [])])
        senal = color_de("senal")
        verdes = sum(1 for y in range(0, sup.get_height(), 2) for x in range(0, sup.get_width(), 2)
                     if cerca(pixel(sup, x, y), senal, 30))
        self.assertEqual(verdes, 0)

    def test_un_proyecto_sin_arquitectura_es_un_nucleo_hueco(self):
        sup, [nucleo], pintadas = self.pintar([proyecto("nuevo", [])])
        self.assertEqual(pintadas, 0)
        self.assertTrue(cerca(pixel(sup, nucleo.x, nucleo.y), color_de(c.FONDO)))


def girar(ms=60):
    contexto = GLib.MainContext.default()
    limite = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < limite:
        contexto.iteration(False)


def con_animaciones(prueba, activas):
    ajustes = Gtk.Settings.get_default()
    antes = ajustes.get_property("gtk-enable-animations")
    ajustes.set_property("gtk-enable-animations", activas)
    prueba.addCleanup(ajustes.set_property, "gtk-enable-animations", antes)
    return ajustes


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no hay widget")
class Widget(unittest.TestCase):
    def setUp(self):
        self.ajustes = con_animaciones(self, False)
        self.tocados = []
        self.ventana = Gtk.Window(default_width=800, default_height=400)
        self.addCleanup(self.ventana.destroy)
        caja, self.dibujo = widget_constelacion.caja_constelacion(lambda: COLORES,
                                                                  self.tocados.append)
        self.ventana.set_child(caja)
        self.dibujo.poner([proyecto("faro", ["hecho", "por-comprobar"]), proyecto("nuevo", [])])

    def test_con_las_animaciones_apagadas_no_hay_reloj(self):
        self.ventana.present()
        girar(200)
        self.assertTrue(self.dibujo.get_mapped())
        self.assertGreater(self.dibujo.fotogramas, 0)
        self.assertEqual(self.dibujo.piezas_pintadas, 2)
        self.assertFalse(self.dibujo.animada())
        quietos = self.dibujo.fotogramas
        girar(300)
        self.assertLessEqual(self.dibujo.fotogramas - quietos, 1)   # nada de pedir fotogramas

    def test_encenderlas_pone_el_reloj_y_apagarlas_lo_quita(self):
        self.ventana.present()
        girar(100)
        self.ajustes.set_property("gtk-enable-animations", True)
        girar(50)
        self.assertTrue(self.dibujo.animada())
        self.ajustes.set_property("gtk-enable-animations", False)
        girar(50)
        self.assertFalse(self.dibujo.animada())

    def test_oculta_no_anima_aunque_esten_encendidas(self):
        self.ajustes.set_property("gtk-enable-animations", True)
        self.ventana.present()
        girar(100)
        self.assertTrue(self.dibujo.animada())
        self.ventana.set_visible(False)
        girar(50)
        self.assertFalse(self.dibujo.animada())

    def test_pide_el_alto_de_sus_filas_y_tocar_un_nucleo_lo_abre(self):
        self.ventana.present()
        girar(100)
        self.assertEqual(self.dibujo.get_height(), c.ALTO_FILA)
        nucleo = self.dibujo.nucleos[1]
        self.dibujo._al_soltar(None, 1, nucleo.x, nucleo.y)
        self.assertEqual(self.tocados, ["nuevo"])


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class EnElInicio(unittest.TestCase):
    """El board de verdad sobre una fuente de repos de prueba con un proyecto con arquitectura."""

    apps = 0

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        repo = raiz / "faro"
        (repo / ".cotejo").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".cotejo" / "tareas.md").write_text(
            "- [ ] Uno ^t-uno\n- [ ] Dos #por-validar ^t-dos\n- [ ] Cuatro #en-curso ^t-cuatro\n",
            encoding="utf-8")
        alm = almacen.Almacen(repo)
        entrada = alm.crear("proyecto", "faro")
        alm.reescribir(almacen.ID_PROYECTO, entrada.version, texto="## Objetivo\n\nReservas.\n",
                       campos={"version": "0.1.0"})
        alm.crear("arquitectura", "Mapa", PIEZAS)

        parche = mock.patch.dict(os.environ)
        parche.start()
        self.addCleanup(parche.stop)
        for var in ("COTEJO_RAIZ_REPOS", "COTEJO_VAULT"):
            os.environ.pop(var, None)
        os.environ.update({"COTEJO_CONFIG": str(raiz / "config.json"),
                           "COTEJO_ESTADO": str(raiz / "estado"),
                           "COTEJO_FUENTE": "repo", "COTEJO_REPOS": str(repo)})
        parche = mock.patch.object(app.App, "poner_lo_del_usuario", return_value=None)
        parche.start()
        self.addCleanup(parche.stop)
        con_animaciones(self, False)

        self.app = app.App()
        EnElInicio.apps += 1   # un id por app: con un bus de sesión, dos iguales chocan
        self.app.set_application_id(
            f"io.github.cotejoapp.CotejoPruebaConstelacion{os.getpid()}n{self.apps}")
        self.app.set_flags(self.app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        self.app.register(None)
        self.addCleanup(self.cerrar)
        self.app.desde_cero = False
        self.app.abrir_board()
        self.board = self.app.board
        girar(200)

    def cerrar(self):
        for monitor in self.app.monitores:
            monitor.cancel()
        if self.app.board is not None:
            self.app.board.destroy()
        self.app.release()

    def test_pinta_los_proyectos_reales_con_sus_piezas(self):
        b = self.board
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        self.assertTrue(b.area_constelacion.get_visible())
        dibujo = b.constelacion
        self.assertEqual([p.nombre for p in dibujo.proyectos], ["faro"])
        [nucleo] = dibujo.nucleos
        self.assertEqual([p.estado for p in nucleo.puntos],
                         ["por-comprobar", "falta", "en-curso", "falta"])
        self.assertGreater(dibujo.fotogramas, 0)
        self.assertEqual(dibujo.piezas_pintadas, 4)
        self.assertFalse(dibujo.animada())
        # Repintar el Inicio reutiliza la misma constelación.
        b.inicio_al_dia = False
        b.pintar_inicio()
        self.assertIs(b.constelacion, dibujo)

    def test_tocar_el_nucleo_abre_el_proyecto(self):
        with mock.patch.object(self.board, "abrir_proyecto") as abrir:
            # El widget guardó el método al crearse: se reemplaza donde se llama.
            self.board.constelacion._al_tocar = self.board.abrir_proyecto
            nucleo = self.board.constelacion.nucleos[0]
            self.board.constelacion._al_soltar(None, 1, nucleo.x, nucleo.y)
        abrir.assert_called_once_with("faro")


if __name__ == "__main__":
    unittest.main()
