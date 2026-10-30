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
                                      "--captura-desde", "https://example.com/x")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.entrega()["capturas_solicitadas"],
                         ["pagina.html", "https://example.com/x"])
        self.assertNotIn("capturas", self.entrega())
        self.assertIn("fuera del sandbox", datos["nota_para_el_agente"])

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

    def test_un_archivo_fuera_del_trabajo_no_se_abre(self):
        self.entregar("--captura-desde", str(self.vault / "config.json"))
        resultado = navegador.capturar_entrega(self.entrega(), trabajo=self.trabajo,
                                               sacar=lambda *a, **k: self.fail("no debe sacar"))
        self.assertEqual(resultado["capturas"], [])
        self.assertIn("fuera de la carpeta de trabajo", resultado["capturas_avisos"][0])

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

    def test_acepta_http_y_archivo_del_trabajo(self):
        self.assertEqual(navegador._destino("https://example.com", self.tmp),
                         "https://example.com")
        self.assertEqual(navegador._destino("pagina.html", self.tmp),
                         str((self.tmp / "pagina.html").resolve()))
        self.assertEqual(navegador._destino("sub/../pagina.html", self.tmp),
                         str((self.tmp / "pagina.html").resolve()))

    def test_rechaza_lo_que_no_es_http_ni_archivo(self):
        for texto in ("ftp://x/p", "javascript:alert(1)", "../fuera.html", "%s/pagina.html"
                      % (self.tmp.parent)):
            with self.subTest(texto):
                with self.assertRaises(ValueError):
                    navegador._destino(texto, self.tmp)

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
