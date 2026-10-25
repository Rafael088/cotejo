"""La escala de Windows que GTK no le da al board (cotejo-x968aw).

GTK en Windows redondea la escala a entero y las letras en px no siguen al DPI: al 150 % el
board salía al 100 %. Lo de GTK se salta sin GTK; lo de Windows no se puede correr aquí y se
prueba con el `ctypes` falso.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app  # noqa: F401  (antes que Gtk: pide la versión 4)
    from tareas.app import escala, piezas
    from gi.repository import Gtk
    from tareas.app.estilo import CSS
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False

RAIZ = Path(__file__).resolve().parent.parent


@unittest.skipUnless(HAY_GTK, "sin GTK")
class ElFactor(unittest.TestCase):
    def test_las_escalas_de_windows(self):
        # 96 es el 100 %; 120, 144 y 168 son 125, 150 y 175 %, que GTK deja en 1.
        for dpi, factor in ((96, 1.0), (120, 1.25), (144, 1.5), (168, 1.75)):
            self.assertEqual(escala.calcular_factor(dpi, 1), factor, dpi)

    def test_lo_que_gtk_ya_escalo_no_se_escala_dos_veces(self):
        self.assertEqual(escala.calcular_factor(192, 2), 1.0)   # 200 %: GTK pone 2
        self.assertEqual(escala.calcular_factor(240, 2), 1.25)  # 250 %: GTK pone 2, falta 1,25

    def test_sin_dpi_o_por_debajo_de_96_se_queda_en_1(self):
        for dpi in (None, 0, -5, 72):
            self.assertEqual(escala.calcular_factor(dpi, 1), 1.0, dpi)

    def test_cotejo_escala_lo_fuerza_en_cualquier_sistema(self):
        with mock.patch.dict("os.environ", {"COTEJO_ESCALA": "1.5"}):
            self.assertEqual(escala.forzado(), 1.5)
        for valor in ("", "nada", "0", "-2", "9"):
            with mock.patch.dict("os.environ", {"COTEJO_ESCALA": valor}):
                self.assertIsNone(escala.forzado(), valor)

    def test_la_letra_de_adwaita_va_con_el_mismo_factor(self):
        # En Windows, lo mismo que pone GTK en el modo de un DPI para el sistema: dpi * 1024.
        with mock.patch.object(sys, "platform", "win32"):
            self.assertEqual(escala.dpi_de_letra(1.5, 0), 144 * 1024)
            self.assertEqual(escala.dpi_de_letra(1.0, -1), 96 * 1024)
        # Fuera, sobre el que ya había (el de GNOME con texto grande, por ejemplo).
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(escala.dpi_de_letra(1.5, 100 * 1024), 150 * 1024)
            self.assertEqual(escala.dpi_de_letra(1.5, -1), 144 * 1024)

    def test_fuera_de_windows_no_se_pregunta_el_dpi(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertIsNone(escala.dpi_de(None))

    def test_en_windows_el_de_la_ventana_y_si_no_el_del_sistema(self):
        user32 = types.SimpleNamespace(GetDpiForWindow=lambda hwnd: 144, GetDpiForSystem=lambda: 120)
        falso = types.SimpleNamespace(windll=types.SimpleNamespace(user32=user32),
                                      c_void_p=lambda v: v)
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.dict(sys.modules, {"ctypes": falso}), \
             mock.patch.object(escala, "_hwnd", lambda s: 1234):
            self.assertEqual(escala.dpi_de(object()), 144)
            self.assertEqual(escala.dpi_de(None), 120)

    def test_un_windows_que_no_sabe_responder_no_rompe_el_board(self):
        falso = types.SimpleNamespace(windll=types.SimpleNamespace(user32=types.SimpleNamespace()))
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.dict(sys.modules, {"ctypes": falso}):
            self.assertIsNone(escala.dpi_de(None))


@unittest.skipUnless(HAY_GTK, "sin GTK")
class ElCss(unittest.TestCase):
    def test_multiplica_los_px(self):
        self.assertEqual(escala.escalar_css(".a { font-size: 14px; padding: 4px 12px; }", 1.5),
                         ".a { font-size: 21px; padding: 6px 18px; }")

    def test_los_bordes_de_1px_se_quedan(self):
        css = ".a { border: 1px solid; margin: -1px; outline: 0px; }"
        self.assertEqual(escala.escalar_css(css, 1.5), css)

    def test_no_toca_lo_que_no_es_px(self):
        css = ".a { letter-spacing: -0.01em; line-height: 1.4; opacity: 0.75; transition: 140ms; }"
        self.assertEqual(escala.escalar_css(css, 1.5), css)

    def test_con_factor_1_es_el_mismo(self):
        self.assertIs(escala.escalar_css(CSS, 1), CSS)

    def test_el_css_del_board_escalado_sigue_cargando_sin_errores(self):
        errores = []
        proveedor = Gtk.CssProvider()
        proveedor.connect("parsing-error", lambda _p, _s, error: errores.append(error.message))
        proveedor.load_from_string(escala.escalar_css(CSS, 1.5))
        self.assertEqual(errores, [])

    def test_la_letra_del_board_crece_con_el_factor(self):
        escalado = escala.escalar_css(CSS, 1.5)
        self.assertIn("--k-contenido: 21px;", escalado)
        self.assertIn("--k-etiqueta: 16.5px;", escalado)


@unittest.skipUnless(HAY_GTK, "sin GTK")
class LosIconos(unittest.TestCase):
    def tearDown(self):
        escala.FACTOR = 1.0

    def test_nacen_a_la_escala_de_ahora(self):
        escala.FACTOR = 1.5
        self.assertEqual(piezas.icono("tarea", 16).get_pixel_size(), 24)

    def test_se_reescalan_al_cambiar_de_monitor(self):
        caja = Gtk.Box()
        dentro = Gtk.Box()
        caja.append(dentro)
        uno, otro = piezas.icono("tarea", 16), piezas.icono("tarea", 15)
        dentro.append(uno)
        caja.append(otro)
        ajeno = Gtk.Image(pixel_size=10)   # no es de `icono`: no se toca
        caja.append(ajeno)
        escala.FACTOR = 1.25
        escala.reescalar_iconos(caja)
        self.assertEqual((uno.get_pixel_size(), otro.get_pixel_size(), ajeno.get_pixel_size()),
                         (20, 19, 10))
        escala.FACTOR = 1.0
        escala.reescalar_iconos(caja)
        self.assertEqual((uno.get_pixel_size(), otro.get_pixel_size()), (16, 15))


class ElLanzador(unittest.TestCase):
    def test_pide_el_dpi_de_cada_monitor(self):
        codigo = (RAIZ / "empaquetado" / "windows" / "lanzador.c").read_text(encoding="utf-8")
        self.assertIn('SetEnvironmentVariableW(L"GDK_WIN32_PER_MONITOR_HIDPI", L"1");', codigo)


if __name__ == "__main__":
    unittest.main()
