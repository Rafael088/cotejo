"""Las capturas se sacan fuera del sandbox, al refrescar el board (cotejo-v40nc1).

El agente de una tarea ya no arranca un navegador: deja la petición con `--captura-desde`, la
entrega se escribe igual y `navegador.capturar_pendientes()` la completa fuera. Todo con fuentes
y un navegador de mentira; la prueba con el sandbox real de Claude vive en
`test_navegador_sandbox.py` y se salta sin `COTEJO_PRUEBA_CLAUDE=1`.
"""

import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI, proyecto

from enrutador import navegador
from tareas import bitacora, capturas

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    HAY_GTK = bool(Gtk.init_check())
except (ImportError, ValueError):
    HAY_GTK = False


def png(ancho, alto):
    def trozo(nombre, datos):
        cuerpo = nombre + datos
        return struct.pack(">I", len(datos)) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo))
    filas = b"".join(b"\x00" + b"\x80" * ancho for _ in range(alto))
    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(filas)) + trozo(b"IEND", b""))


class Pendientes(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Haciéndola #en-curso #agente/opus"))
        self.trabajo = self.vault / "trabajo"
        self.trabajo.mkdir()
        (self.trabajo / "pagina.html").write_text("<html><body>ok</body></html>",
                                                  encoding="utf-8")
        self.id = self.correr("tareas")[1]["tareas"][0]["id"]

    def entregar(self, *extra):
        return self.correr("entregar", self.id, "--evidencia", "hecha",
                           "--repo", str(self.trabajo), *extra)

    def entrega(self):
        """La entrega ya unida con su resultado de capturas, como la lee el board."""
        crudas = [o for o in self.operaciones() if o["operacion"] == "entregar"]
        return bitacora.ultima_entrega(crudas[-1]["id"]) if crudas else None

    def test_entregar_sin_capturas_entrega_igual_y_lo_dice(self):
        codigo, datos = self.entregar()
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")
        self.assertNotIn("capturas_solicitadas", self.entrega())

    def test_captura_desde_solo_deja_la_peticion_y_el_agente_no_saca_png(self):
        codigo, datos = self.entregar("--captura-desde", "pagina.html",
                                      "--captura-desde", "http://localhost:8000/x")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.entrega()["capturas_solicitadas"],
                         ["pagina.html", "http://localhost:8000/x"])
        self.assertNotIn("capturas", self.entrega())
        self.assertIn("fuera del sandbox", datos["nota_para_el_agente"])

    def test_una_url_externa_se_rechaza_al_entregar(self):
        codigo, datos = self.entregar("--captura-desde", "https://ajeno.com/?d=secreto")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no es local", datos["error"])
        self.assertEqual([o for o in self.operaciones() if o["operacion"] == "entregar"], [])
        self.assertEqual(self.correr("tareas")[1]["tareas"][0]["estado"], "en-curso")

    def test_un_symlink_que_sale_del_trabajo_se_rechaza_al_entregar(self):
        (self.trabajo / "enlace.html").symlink_to(self.vault / "config.json")
        codigo, datos = self.entregar("--captura-desde", "enlace.html")
        self.assertNotEqual(codigo, 0)
        self.assertIn("fuera de la carpeta de trabajo", datos["error"])

    def test_una_ruta_con_dos_puntos_que_sale_del_trabajo_se_rechaza_al_entregar(self):
        codigo, datos = self.entregar("--captura-desde", "../config.json")
        self.assertNotEqual(codigo, 0)
        self.assertIn("fuera de la carpeta de trabajo", datos["error"])

    def test_el_board_saca_movil_y_escritorio_y_las_junta_con_la_entrega(self):
        self.entregar("--captura-desde", "pagina.html")

        def sacar(destino, salida, ancho, alto, **resto):
            self.assertTrue(destino.endswith("pagina.html"))
            Path(salida).write_bytes(png(ancho, alto))
            return {"ok": True, "motivo": ""}

        resultado = navegador.capturar_entrega(self.entrega(), trabajo=self.trabajo,
                                               sacar=sacar)
        self.assertEqual([c["tipo"] for c in resultado["capturas"]],
                         ["movil", "escritorio"])
        self.assertEqual(resultado["capturas_avisos"], [])
        # La petición y el resultado son dos líneas; al leer se ven como una entrega sola.
        self.assertEqual(len(bitacora.pendientes_de_captura()), 0)
        self.assertEqual(len(self.entrega()["capturas"]), 2)
        for una in self.entrega()["capturas"]:
            self.assertTrue(Path(una["ruta"]).is_file())
            self.assertTrue(Path(una["ruta"]).is_relative_to(self.bitacora.parent))

    def test_una_captura_fallida_queda_anotada_y_no_reintenta_en_cada_refresco(self):
        self.entregar("--captura-desde", "pagina.html")

        def sacar(*_a, **_k):
            return {"ok": False, "motivo": "no hay navegador"}

        resultado = navegador.capturar_entrega(self.entrega(), trabajo=self.trabajo,
                                               sacar=sacar)
        self.assertEqual(resultado["capturas"], [])
        self.assertEqual(len(resultado["capturas_avisos"]), 2)
        self.assertIn("no hay navegador", resultado["capturas_avisos"][0])
        self.assertEqual(bitacora.pendientes_de_captura(), [])
        self.assertEqual(self.entrega()["capturas_avisos"], resultado["capturas_avisos"])

    def test_un_archivo_fuera_del_trabajo_se_rechaza_al_entregar(self):
        codigo, datos = self.entregar("--captura-desde", str(self.vault / "config.json"))
        self.assertNotEqual(codigo, 0)
        self.assertIn("fuera de la carpeta de trabajo", datos["error"])

    def test_un_archivo_fuera_del_trabajo_no_se_abre_al_capturar(self):
        resultado = self._capturar_pedidos(str(self.vault / "config.json"))
        self.assertEqual(resultado["capturas"], [])
        self.assertIn("fuera de la carpeta de trabajo", resultado["capturas_avisos"][0])

    def _capturar_pedidos(self, *pedidos):
        entrega = {"id": self.id, "cuando": "2026-10-30T00:00:00",
                   "proyecto": "Uno", "capturas_solicitadas": list(pedidos)}
        return navegador.capturar_entrega(
            entrega, trabajo=self.trabajo,
            sacar=lambda *a, **k: self.fail("no debe sacar"))

    def test_una_url_externa_se_rechaza_al_capturar(self):
        resultado = self._capturar_pedidos("https://ajeno.com/?d=secreto")
        self.assertEqual(resultado["capturas"], [])
        self.assertIn("no es local", resultado["capturas_avisos"][0])

    def test_un_symlink_que_sale_del_trabajo_se_rechaza_al_capturar(self):
        (self.trabajo / "enlace.html").symlink_to(self.vault / "config.json")
        resultado = self._capturar_pedidos("enlace.html")
        self.assertEqual(resultado["capturas"], [])
        self.assertIn("fuera de la carpeta de trabajo", resultado["capturas_avisos"][0])

    def test_una_url_localhost_se_acepta_al_capturar(self):
        def sacar(destino, salida, ancho, alto, **resto):
            self.assertEqual(destino, "http://127.0.0.1:8000/")
            Path(salida).write_bytes(png(ancho, alto))
            return {"ok": True, "motivo": ""}

        entrega = {"id": self.id, "cuando": "2026-10-30T00:00:00", "proyecto": "Uno",
                   "capturas_solicitadas": ["http://127.0.0.1:8000/"]}
        resultado = navegador.capturar_entrega(entrega, trabajo=self.trabajo, sacar=sacar)
        self.assertEqual(len(resultado["capturas"]), 2)
        self.assertEqual(resultado["capturas_avisos"], [])

    def test_programar_capturas_completa_en_un_hilo(self):
        self.entregar("--captura-desde", "pagina.html")

        def sacar(destino, salida, ancho, alto, **resto):
            Path(salida).write_bytes(png(ancho, alto))
            return {"ok": True, "motivo": ""}

        with mock.patch.object(navegador, "capturar", sacar), \
                mock.patch.object(navegador, "_carpeta_de_la_entrega",
                                  return_value=self.trabajo):
            hilo = navegador.programar_capturas()
            self.assertIsNotNone(hilo)
            self.assertTrue(navegador.esperar_capturas(timeout=30))
        self.assertEqual(bitacora.pendientes_de_captura(), [])
        self.assertEqual(len(self.entrega()["capturas"]), 2)

    def test_lo_que_ya_estaba_no_se_pierde_al_añadir_las_de_la_peticion(self):
        original = self.trabajo / "mia.png"
        original.write_bytes(png(390, 844))
        self.entregar("--captura", str(original), "--captura-desde", "pagina.html")

        def sacar(destino, salida, ancho, alto, **resto):
            Path(salida).write_bytes(png(ancho, alto))
            return {"ok": True, "motivo": ""}

        resultado = navegador.capturar_entrega(self.entrega(), trabajo=self.trabajo,
                                               sacar=sacar)
        self.assertEqual(len(resultado["capturas"]), 3)
        for una in resultado["capturas"]:
            self.assertTrue(Path(una["ruta"]).is_file())

    def test_una_peticion_igual_no_se_captura_dos_veces(self):
        self.entregar("--captura-desde", "pagina.html")
        entrega = self.entrega()
        llamadas = []

        def sacar(destino, salida, ancho, alto, **resto):
            llamadas.append(salida)
            Path(salida).write_bytes(png(ancho, alto))
            return {"ok": True, "motivo": ""}

        with mock.patch.dict(navegador._CAPTURAS_EN_CURSO,
                             {(entrega["id"], entrega["cuando"]): True}):
            self.assertIsNone(navegador.capturar_entrega(entrega, trabajo=self.trabajo,
                                                         sacar=sacar))
        self.assertEqual(llamadas, [])


class Destinos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        (self.tmp / "pagina.html").write_text("ok", encoding="utf-8")
        (self.tmp / "sub").mkdir()

    def test_acepta_http_local_y_archivo_del_trabajo(self):
        for url in ("http://localhost", "https://localhost:8443/x",
                    "http://127.0.0.1:8000/", "http://[::1]:3000/"):
            with self.subTest(url):
                self.assertEqual(navegador._destino(url, self.tmp), url)
        self.assertEqual(navegador._destino("pagina.html", self.tmp),
                         str((self.tmp / "pagina.html").resolve()))
        self.assertEqual(navegador._destino("sub/../pagina.html", self.tmp),
                         str((self.tmp / "pagina.html").resolve()))
        self.assertEqual(navegador._destino((self.tmp / "pagina.html").as_uri(), self.tmp),
                         str((self.tmp / "pagina.html").resolve()))

    def test_rechaza_hosts_externos_y_esquemas_que_no_son(self):
        for texto in ("https://example.com", "http://localhost.evil.com/",
                      "http://localhost@evil.com/", "http://127.0.0.1.evil.com/",
                      "ftp://x/p", "javascript:alert(1)", "data:text/html,hola",
                      "about:config", "../fuera.html", "%s/pagina.html" % (self.tmp.parent),
                      (self.tmp.parent / "pagina.html").as_uri()):
            with self.subTest(texto):
                with self.assertRaises(ValueError):
                    navegador._destino(texto, self.tmp)

    def test_un_symlink_que_sale_del_trabajo_se_rechaza(self):
        fuera = self.tmp.parent / "fuera.html"
        fuera.write_text("secreto", encoding="utf-8")
        (self.tmp / "enlace.html").symlink_to(fuera)
        with self.assertRaises(ValueError):
            navegador._destino("enlace.html", self.tmp)

    def test_el_perfil_de_captura_lleva_las_prefs(self):
        visto = {}

        class Proceso:
            returncode = 0
            pid = 999999

            def __init__(self, argv, **_resto):
                perfil = Path(argv[argv.index("--profile") + 1])
                visto["userjs"] = (perfil / "user.js").read_text(encoding="utf-8")
                Path(argv[argv.index("--screenshot") + 1]).write_bytes(png(1280, 800))

            def communicate(self, timeout=None):
                return b"", b""

        salida = self.tmp / "captura.png"
        with mock.patch.object(navegador.subprocess, "Popen", Proceso), \
                mock.patch.object(navegador, "_matar"):
            hecho = navegador.capturar("http://localhost:8000/", salida, entorno={},
                                       which=lambda nombre: "/usr/bin/firefox")
        self.assertTrue(hecho["ok"])
        prefs = visto["userjs"]
        for esperada in ('"network.proxy.type", 1',
                         '"network.proxy.http", "127.0.0.1"',
                         '"network.proxy.http_port", 9',
                         '"network.proxy.ssl", "127.0.0.1"',
                         '"network.proxy.ssl_port", 9',
                         '"network.proxy.no_proxies_on", "localhost, 127.0.0.1, [::1]"',
                         '"network.proxy.allow_hijacking_localhost", false',
                         '"network.prefetch-next", false',
                         '"network.dns.disablePrefetch", true',
                         '"network.http.speculative-parallel-limit", 0'):
            with self.subTest(esperada):
                self.assertIn(esperada, prefs)

    def test_el_tope_de_solicitudes_es_la_mitad_que_el_de_capturas(self):
        destinos = capturas.solicitudes([f"p{n}.html" for n in range(capturas.MAXIMO // 2)])
        self.assertEqual(len(destinos), capturas.MAXIMO // 2)
        # Repetidos no cuentan dos veces.
        self.assertEqual(capturas.solicitudes(["a", "a"]), ["a"])
        with self.assertRaises(ValueError):
            capturas.solicitudes([f"p{n}.html" for n in range(capturas.MAXIMO // 2 + 1)])


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede importar el board")
class ElBoardLoPide(unittest.TestCase):
    def test_el_board_delega_en_el_navegador_y_no_lo_hace_ventana(self):
        from tareas.app import aplicacion
        with mock.patch.object(navegador, "programar_capturas") as programar:
            aplicacion.App.programar_capturas()
        programar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
