"""«Ver mi app» y «Abrir la carpeta» en el board de verdad (v1.3.0, cotejo-vn4qd2).

Con GTK y pantalla (sin ellas se salta), sobre el proyecto de prueba del mapa. Nunca se abre
un navegador ni el gestor de archivos (el lanzador de Gio va sustituido) ni se arranca un
proceso: `Servidores` es uno de mentira y el hilo corre en línea. Lo de verdad —procesos,
puertos, deducción— se prueba sin GTK en `test_ver_app.py`.
"""

import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base
from test_mapa import proyecto_de_prueba

if base.HAY_GTK:
    from tareas import como_se_abre, servidor_app
    from tareas.app import ver_app


class ServidoresFalsos:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.abiertos, self.parados, self.todos = [], [], 0
        self.vivos = set()

    def abrir(self, nombre, plan):
        self.abiertos.append((nombre, plan))
        if self.resultado.corriendo:
            self.vivos.add(nombre)
        return self.resultado

    def vivo(self, nombre):
        return nombre in self.vivos

    def parar(self, nombre):
        self.parados.append(nombre)
        return self.vivos.discard(nombre) is None

    def parar_todos(self):
        self.todos += 1
        self.vivos.clear()


@unittest.skipUnless(base.HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class VerMiApp(base.PestanaInicio):
    con_vault = False

    def entorno_extra(self, raiz):
        self.carpeta = proyecto_de_prueba(raiz / "repos")
        return {"COTEJO_REPOS": str(self.carpeta)}

    def setUp(self):
        super().setUp()
        for parche in (mock.patch.object(ver_app, "correr_aparte", lambda f: f()),
                       mock.patch.object(ver_app.Gio.AppInfo, "launch_default_for_uri")):
            self.lanzador = parche.start()
            self.addCleanup(parche.stop)
        self.avisos = []
        self.board.aviso = lambda texto, *a, **k: self.avisos.append((texto, k))

    def esperar_aviso(self, n=2):
        """El resultado llega por `GLib.idle_add`: se gira hasta que haya `n` avisos (≤ 3 s)."""
        for _ in range(50):
            if len(self.avisos) >= n:
                return
            base.girar()

    def poner(self, resultado):
        self.board.servidores = ServidoresFalsos(resultado)
        return self.board.servidores

    def test_el_mapa_lleva_los_botones_y_parar_solo_con_la_app_en_marcha(self):
        b = self.board
        b.abrir_proyecto("barberia")
        base.girar()
        p = b.pantalla_mapa
        self.assertEqual([p.boton_ver_app.get_label(), p.boton_carpeta.get_label()],
                         ["Ver mi app", "Abrir la carpeta"])
        self.assertFalse(p.boton_parar.get_visible())

        (self.carpeta / "index.html").write_text("<h1>hola</h1>", encoding="utf-8")
        falsos = self.poner(servidor_app.Resultado(
            True, "Abrí tu app en el navegador.", abrir="http://127.0.0.1:9/index.html",
            corriendo=True))
        p.boton_ver_app.emit("clicked")
        self.esperar_aviso()
        nombre, plan = falsos.abiertos[0]
        self.assertEqual(nombre, "barberia")
        # La carpeta principal del proyecto, y lo deducido de su index.html.
        self.assertEqual(plan.carpeta, str(self.carpeta))
        self.assertEqual(plan.como.tipo, "pagina")
        self.lanzador.assert_called_once_with("http://127.0.0.1:9/index.html", None)
        self.assertEqual(self.avisos[-1][0], "Abrí tu app en el navegador.")
        self.assertEqual(self.avisos[-1][1].get("boton"), "Parar")
        self.assertTrue(p.boton_parar.get_visible())

        p.boton_parar.emit("clicked")
        base.girar()
        self.assertEqual(falsos.parados, ["barberia"])
        self.assertFalse(p.boton_parar.get_visible())

    def test_sin_saber_como_abrirla_lo_dice_en_llano_y_no_arranca_nada(self):
        b = self.board
        falsos = self.poner(servidor_app.Resultado(True, "no"))
        b.abrir_proyecto("barberia")
        base.girar()
        b.pantalla_mapa.boton_ver_app.emit("clicked")
        base.girar()
        self.assertEqual(falsos.abiertos, [])
        self.assertEqual(self.avisos[-1][0], como_se_abre.SIN_ANOTAR)
        self.lanzador.assert_not_called()

    def test_si_no_arranca_ofrece_ver_lo_que_dijo(self):
        (self.carpeta / "index.html").write_text("x", encoding="utf-8")
        self.poner(servidor_app.Resultado(False, "Tu app no arrancó.", log="/x/barberia.log"))
        self.board.ver_mi_app("barberia")
        self.esperar_aviso()
        texto, extra = self.avisos[-1]
        self.assertEqual((texto, extra.get("boton")), ("Tu app no arrancó.", "Ver lo que dijo"))
        self.lanzador.assert_not_called()
        extra["al_pulsar"]()
        self.lanzador.assert_called_once_with("file:///x/barberia.log", None)

    def test_abrir_la_carpeta_abre_la_principal(self):
        b = self.board
        b.abrir_proyecto("barberia")
        base.girar()
        b.pantalla_mapa.boton_carpeta.emit("clicked")
        uri = self.lanzador.call_args.args[0]
        self.assertEqual(Path(uri.removeprefix("file://")), self.carpeta)

    def test_las_tarjetas_del_inicio_llevan_los_dos_botones(self):
        b = self.board
        b.ver_pestana("inicio")
        base.girar()
        tarjeta = b.inicio_tarjetas.get_first_child().get_child()
        botones = {}
        hijo = tarjeta.botones_app.get_first_child()
        while hijo is not None:
            botones[hijo.get_label()] = hijo
            hijo = hijo.get_next_sibling()
        self.assertEqual(list(botones), ["Ver mi app", "Abrir la carpeta"])
        with mock.patch.object(b, "abrir_proyecto") as abrir_mapa:
            botones["Abrir la carpeta"].emit("clicked")
        abrir_mapa.assert_not_called()      # el botón no es la tarjeta: no lleva al mapa
        uri = self.lanzador.call_args.args[0]
        self.assertEqual(Path(uri.removeprefix("file://")), self.carpeta)

    def test_cerrar_el_board_para_las_apps(self):
        falsos = self.poner(servidor_app.Resultado(True, "x"))
        self.board.emit("close-request")
        self.assertEqual(falsos.todos, 1)


if __name__ == "__main__":
    unittest.main()
