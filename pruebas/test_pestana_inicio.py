"""La pestaña Inicio en el board de verdad (v1.3.0): abre antes que el tablero.

Prueba de humo con GTK y pantalla (sin ellas se salta), sobre un vault de mentira: el board
abre en Inicio con el titular y una tarjeta por proyecto; «Nuevo proyecto» de momento avisa;
una tarjeta lleva al mapa y de ahí al tablero con su proyecto elegido; y sin de dónde leer
abre en el tablero, donde está la explicación del primer arranque. La lógica de lo que se enseña se prueba sin
GTK en `test_resumen_inicio.py`.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app, entrevista, inicio  # antes que gi.repository: pide las versiones de GTK 4
    from tareas.app import pestana_inicio
    from gi.repository import Gio, GLib, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def girar(ms=60):
    contexto = GLib.MainContext.default()
    limite = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < limite:
        contexto.iteration(False)


def textos(widget, acumulado=None):
    acumulado = [] if acumulado is None else acumulado
    if isinstance(widget, Gtk.Label) and widget.get_label():
        acumulado.append(widget.get_label())
    hijo = widget.get_first_child()
    while hijo is not None:
        textos(hijo, acumulado)
        hijo = hijo.get_next_sibling()
    return acumulado


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class PestanaInicio(unittest.TestCase):
    apps = 0
    con_vault = True

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        entorno = {"COTEJO_CONFIG": str(raiz / "config.json"), "COTEJO_ESTADO": str(raiz / "estado")}
        if self.con_vault:
            (raiz / "vault" / "01-Proyectos").mkdir(parents=True)
            for nombre, lineas in (("Faro", "- [ ] Uno\n- [ ] Dos #por-validar\n"),
                                   ("Horizonte", "- [ ] Tres\n")):
                (raiz / "vault" / "01-Proyectos" / f"{nombre}.md").write_text(
                    f"---\ntipo: proyecto\n---\n\n# {nombre}\n\n{lineas}", encoding="utf-8")
            entorno["COTEJO_VAULT"] = str(raiz / "vault")
        else:
            entorno["COTEJO_FUENTE"] = "repo"   # una fuente de repos sin ninguno: primer arranque
        entorno.update(self.entorno_extra(raiz))
        parche = mock.patch.dict(os.environ)
        parche.start()
        self.addCleanup(parche.stop)
        for var in ("COTEJO_REPOS", "COTEJO_RAIZ_REPOS", "COTEJO_FUENTE", "COTEJO_VAULT"):
            os.environ.pop(var, None)
        os.environ.update(entorno)
        parche = mock.patch.object(app.App, "poner_lo_del_usuario", return_value=None)
        parche.start()
        self.addCleanup(parche.stop)

        ajustes = Gtk.Settings.get_default()
        antes = ajustes.get_property("gtk-enable-animations")
        ajustes.set_property("gtk-enable-animations", False)
        self.addCleanup(ajustes.set_property, "gtk-enable-animations", antes)

        self.app = app.App()
        PestanaInicio.apps += 1
        self.app.set_application_id(f"io.github.cotejoapp.CotejoPruebaInicio{os.getpid()}n{self.apps}")
        self.app.set_flags(self.app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        self.app.register(None)
        self.addCleanup(self.cerrar)
        self.app.desde_cero = False
        self.app.abrir_board()
        self.board = self.app.board
        girar()

    def entorno_extra(self, raiz):
        """Lo que una subclase añade al entorno antes de abrir el board (p. ej. sus repos)."""
        return {}

    def cerrar(self):
        for monitor in self.app.monitores:
            monitor.cancel()
        if self.app.board is not None:
            self.app.board.destroy()
        self.app.release()


class ConProyectos(PestanaInicio):
    def test_abre_en_inicio_con_el_resumen_y_una_tarjeta_por_proyecto(self):
        b = self.board
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        self.assertTrue(b.botones_pestana[pestana_inicio.INICIO].get_active())
        self.assertFalse(b.banda_proyectos.get_visible())
        self.assertFalse(b.buscador.get_visible())
        todo = textos(b.pestanas.get_child_by_name(pestana_inicio.INICIO))
        self.assertIn("Tienes 2 proyectos y 1 entrega por comprobar", todo)
        self.assertIn("1 por comprobar", todo)
        self.assertIn("sin arquitectura todavía", todo)
        self.assertIn("Empezar un proyecto", todo)
        # Faro (con una entrega por comprobar) primero; «Nuevo proyecto» al final.
        nombres = [t for t in todo if t in ("Faro", "Horizonte")]
        self.assertEqual(nombres, ["Faro", "Horizonte"])
        # La constelación sale con los dos proyectos (sin arquitectura: dos núcleos huecos).
        self.assertTrue(b.area_constelacion.get_visible())
        self.assertEqual([p.nombre for p in b.constelacion.proyectos], ["Faro", "Horizonte"])
        b.poner_constelacion(None)
        self.assertFalse(b.area_constelacion.get_visible())

    def test_nuevo_proyecto_abre_la_entrevista(self):
        b = self.board
        with mock.patch("enrutador.clientes.instalados", return_value=["claude"]):
            b.nuevo_proyecto()
        self.assertEqual(b.pestana_actual(), "entrevista")
        todo = textos(b.pestanas.get_child_by_name("entrevista"))
        for pregunta in ("1. ¿Qué quieres construir?", "2. ¿Quién la va a usar?",
                         "3. ¿Qué tiene que hacer la primera versión?",
                         "4. ¿Dónde la van a usar?", "5. ¿Qué más necesita?",
                         "6. ¿Qué dejamos para después? (opcional)"):
            self.assertIn(pregunta, todo)
        # Los ejemplos van en gris: vacía, no se puede preparar el proyecto de ejemplo.
        self.assertEqual(b.ent_que_es.get_text(), "")
        self.assertEqual(b.ent_que_es.get_placeholder_text(), entrevista.EJEMPLOS["que_es"])
        self.assertTrue(b.ent_que_hace_ejemplo.get_visible())
        self.assertFalse(b.ent_preparar.get_sensitive())
        b.ent_que_hace.get_buffer().set_text("Ver citas")
        self.assertFalse(b.ent_que_hace_ejemplo.get_visible())
        self.assertEqual(b.ent_ver.get_label(), "Ver lo que se le enviará a tu agente")
        self.assertEqual(b.agente_elegido(), "claude")
        self.assertEqual(b.ent_agente_pista.get_label(), "detectado")
        b.cancelar_entrevista()
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def abrir_entrevista(self, agentes=("claude",)):
        with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)):
            self.board.nuevo_proyecto()
        # Llega vacía (los ejemplos son solo el texto en gris): se rellena con ellos.
        b, ej = self.board, entrevista.EJEMPLOS
        b.ent_que_es.set_text(ej["que_es"])
        b.ent_para_quien.set_text(ej["para_quien"])
        b.ent_que_hace.get_buffer().set_text(ej["que_hace"])
        b.ent_fuera.set_text(ej["fuera"])
        return b

    def test_el_formulario_arma_las_respuestas(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Una agenda de citas")
        b.ent_para_quien.set_text("Mi equipo")
        b.ent_que_hace.get_buffer().set_text("Ver citas\nCrear citas")
        b.ent_donde["En el computador, como programa"].set_active(True)
        b.ent_donde["En el celular"].set_active(False)
        b.ent_necesita["Cobrar pagos"].set_active(True)
        b.ent_fuera.set_text("")
        b.ent_carpeta.set_text("/tmp/agenda-citas")
        r = b.respuestas_entrevista()
        self.assertEqual(r, inicio.Respuestas(
            que_es="Una agenda de citas", para_quien="Mi equipo",
            que_hace="Ver citas\nCrear citas", carpeta="/tmp/agenda-citas",
            donde_se_usa="En el navegador, En el computador, como programa",
            necesita="Guardar datos, Cobrar pagos, Enviar avisos (WhatsApp, correo)", fuera=""))

    def test_la_carpeta_sigue_a_la_pregunta_uno_hasta_que_se_toca(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Una tienda de velas")
        self.assertTrue(b.ent_carpeta.get_text().endswith("/Proyectos/tienda-velas"))
        b.ent_carpeta.set_text("/tmp/mia")
        b.ent_que_es.set_text("Otra cosa distinta")
        self.assertEqual(b.ent_carpeta.get_text(), "/tmp/mia")

    def test_ver_lo_que_se_enviara_es_exactamente_armar(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Un blog de recetas")
        b.ent_carpeta.set_text("/tmp/blog-recetas")
        esperado = inicio.armar(b.respuestas_entrevista())
        self.assertEqual(b._texto_de(b.ent_prompt), esperado)
        self.assertIn("Un blog de recetas", esperado)
        # Y se actualiza al cambiar una respuesta.
        b.ent_fuera.set_text("Nada de pagos")
        self.assertEqual(b._texto_de(b.ent_prompt), inicio.armar(b.respuestas_entrevista()))
        self.assertIn("Nada de pagos", b._texto_de(b.ent_prompt))

    def test_con_campos_vacios_no_se_puede_preparar(self):
        b = self.abrir_entrevista()
        for vacio in ("ent_que_es", "ent_carpeta"):
            b.ent_que_es.set_text("Algo")
            b.ent_carpeta.set_text("/tmp/algo")
            self.assertTrue(b.ent_preparar.get_sensitive())
            getattr(b, vacio).set_text("")
            self.assertFalse(b.ent_preparar.get_sensitive(), vacio)
            self.assertTrue(b.ent_error.get_visible())
        b.ent_carpeta.set_text("/tmp/algo")
        b.ent_que_hace.get_buffer().set_text("")
        self.assertFalse(b.ent_preparar.get_sensitive())
        with mock.patch("enrutador.preparar.lanzar") as lanzar:
            self.assertIsNone(b.preparar_proyecto())
        lanzar.assert_not_called()

    def test_el_boton_inicio_sale_de_la_entrevista(self):
        b = self.abrir_entrevista()
        self.assertTrue(b.botones_pestana["inicio"].get_active())
        b.botones_pestana["inicio"].emit("clicked")
        self.assertEqual(b.pestana_actual(), "inicio")

    def test_sin_agente_instalado_no_se_puede_preparar(self):
        b = self.abrir_entrevista(agentes=())
        self.assertIsNone(b.agente_elegido())
        self.assertFalse(b.ent_preparar.get_sensitive())
        self.assertIn("ningún agente", b.ent_agente_pista.get_label())

    def test_preparar_lanza_con_la_carpeta_y_el_agente_elegidos(self):
        b = self.abrir_entrevista(agentes=("claude", "codex"))
        b.ent_agente.set_selected(1)
        b.ent_carpeta.set_text("/tmp/mi-proyecto")
        estado = {"id": "mi-proyecto-abc123", "proyecto": "mi-proyecto"}
        with mock.patch("enrutador.preparar.lanzar", return_value=estado) as lanzar, \
                mock.patch.object(b, "mostrar_preparando") as gancho:
            self.assertEqual(b.preparar_proyecto(), estado)
        (r,), nombrados = lanzar.call_args
        self.assertEqual(r.carpeta, "/tmp/mi-proyecto")
        self.assertEqual(r, inicio.validar(b.respuestas_entrevista()))
        self.assertEqual(nombrados["cliente"], "codex")
        gancho.assert_called_once_with(estado)
        # El aviso de fin se entrega en el hilo de la interfaz, a preparacion_terminada.
        with mock.patch.object(b, "preparacion_terminada") as fin, \
                mock.patch("tareas.app.entrevista.GLib.idle_add") as idle:
            with mock.patch("enrutador.preparar.lanzar", return_value=estado) as lanzar:
                b.preparar_proyecto()
            lanzar.call_args.kwargs["al_terminar"]({"id": "x"})
        idle.assert_called_once_with(fin, {"id": "x"})

    def test_si_no_se_puede_lanzar_se_avisa_y_se_queda(self):
        from enrutador import preparar
        b = self.abrir_entrevista()
        with mock.patch("enrutador.preparar.lanzar",
                        side_effect=preparar.NoSePuede("No encontré «claude»")), \
                mock.patch.object(b, "aviso") as aviso:
            self.assertIsNone(b.preparar_proyecto())
        aviso.assert_called_once_with("No encontré «claude»")
        self.assertEqual(b.pestana_actual(), "entrevista")

    def test_una_tarjeta_lleva_al_mapa_y_de_ahi_al_tablero_con_su_proyecto(self):
        b = self.board
        b.abrir_proyecto("Horizonte")
        girar()
        self.assertEqual(b.pestana_actual(), "mapa")   # sin arquitectura: el mapa lo dice
        self.assertTrue(b.pantalla_mapa.vacio.get_visible())
        b.pantalla_mapa.boton_tablero.emit("clicked")
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.TABLERO)
        self.assertEqual(b.seleccion, "Horizonte")
        self.assertTrue(b.banda_proyectos.get_visible())
        self.assertTrue(b.buscador.get_visible())
        # Y el selector de la cabecera vuelve a Inicio.
        b.botones_pestana[pestana_inicio.INICIO].set_active(True)
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def test_buscar_lleva_al_tablero(self):
        self.app.buscar()
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


class SinFuente(PestanaInicio):
    con_vault = False

    def test_sin_de_donde_leer_abre_en_el_tablero(self):
        self.assertIsNotNone(self.board.fuente.problema)
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


if __name__ == "__main__":
    unittest.main()
