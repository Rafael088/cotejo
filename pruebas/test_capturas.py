"""Las capturas de la entrega (cotejo-0e17vu): `entregar --captura` las copia y valida, el
encargo las pide, y la ficha y la revisión las enseñan grandes. Todo con fuentes temporales."""

import json
import struct
import types
import unittest
import zlib
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI, proyecto

from tareas import capturas
from enrutador import armado, encargo

try:
    from tareas import app
    from gi.repository import Adw, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def png(ancho, alto):
    """Un PNG válido (gris) del tamaño pedido, sin Pillow."""
    def trozo(nombre, datos):
        cuerpo = nombre + datos
        return struct.pack(">I", len(datos)) + cuerpo + struct.pack(">I", zlib.crc32(cuerpo))
    filas = b"".join(b"\x00" + b"\x80" * ancho for _ in range(alto))
    return (capturas.FIRMA + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(filas)) + trozo(b"IEND", b""))


class Entregando(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Haciéndola #en-curso #agente/opus"))
        self.fuera = self.vault / "trabajo"
        self.fuera.mkdir()
        self.id = self.correr("tareas")[1]["tareas"][0]["id"]

    def archivo(self, nombre, contenido):
        ruta = self.fuera / nombre
        ruta.write_bytes(contenido)
        return str(ruta)

    def entrega(self):
        return [o for o in self.operaciones() if o["operacion"] == "entregar"][-1]

    def test_copia_las_capturas_y_las_anota_con_su_tipo(self):
        movil = self.archivo("m.png", png(390, 844))
        escritorio = self.archivo("e.png", png(1280, 800))
        codigo, _ = self.correr("entregar", self.id, "--evidencia", "x",
                                "--captura", movil, "--captura", escritorio)
        self.assertEqual(codigo, 0)
        guardadas = self.entrega()["capturas"]
        self.assertEqual([c["tipo"] for c in guardadas], ["movil", "escritorio"])
        self.assertEqual((guardadas[0]["ancho"], guardadas[0]["alto"]), (390, 844))
        for c in guardadas:
            self.assertTrue(Path(c["ruta"]).is_file())
            self.assertTrue(Path(c["ruta"]).is_relative_to(self.bitacora.parent))
        # Es una copia: borrar el original (el worktree se borra al aprobar) no la toca.
        Path(movil).unlink()
        self.assertEqual(len(capturas.de_la_entrega(self.entrega())), 2)

    def test_sin_captura_la_entrega_queda_como_siempre(self):
        self.correr("entregar", self.id, "--evidencia", "x")
        self.assertNotIn("capturas", self.entrega())

    def test_rechaza_lo_que_no_es_png_sin_escribir_nada(self):
        falso = self.archivo("falso.png", b"<html>no soy un png</html>")
        with self.assertRaises(SystemExit):
            self.correr("entregar", self.id, "--evidencia", "x", "--captura", falso)
        self.assertEqual([o for o in self.operaciones() if o["operacion"] == "entregar"], [])
        _, datos = self.correr("tareas")
        self.assertEqual(datos["tareas"][0]["estado"], "en-curso")

    def test_rechaza_las_que_no_existen_y_las_demasiado_pesadas(self):
        with self.assertRaises(SystemExit):
            self.correr("entregar", self.id, "--evidencia", "x",
                        "--captura", str(self.fuera / "no-esta.png"))
        grande = self.archivo("grande.png", png(10, 10) + b"\0" * capturas.BYTES_MAX)
        with self.assertRaises(SystemExit):
            self.correr("entregar", self.id, "--evidencia", "x", "--captura", grande)

    def test_hay_un_tope_de_capturas(self):
        varias = [self.archivo(f"{n}.png", png(100 + n, 100)) for n in range(capturas.MAXIMO + 1)]
        argumentos = [a for ruta in varias for a in ("--captura", ruta)]
        codigo, datos = self.correr("entregar", self.id, "--evidencia", "x", *argumentos)
        self.assertNotEqual(codigo, 0)
        self.assertEqual([o for o in self.operaciones() if o["operacion"] == "entregar"], [])

    def test_el_tipo_sale_del_ancho(self):
        self.assertEqual(capturas.tipo(390), "movil")
        self.assertEqual(capturas.tipo(600), "movil")
        self.assertEqual(capturas.tipo(1280), "escritorio")


class Encargo(unittest.TestCase):
    def test_con_navegador_el_encargo_pide_capturas(self):
        texto = encargo.cierre("cotejo-abc123", navegador_disponible=True)
        self.assertIn("--captura", texto)
        self.assertIn("390×844", texto)
        self.assertIn("1280×800", texto)
        self.assertNotIn("{id}", texto)

    def test_sin_navegador_no_pide_capturas_pide_avisar(self):
        texto = encargo.cierre("cotejo-abc123", navegador_disponible=False)
        self.assertNotIn("--captura", texto)
        self.assertIn("instalar Firefox", texto)
        self.assertIn("cotejo entregar cotejo-abc123", texto)   # el cierre de siempre sigue

    def test_la_deteccion_se_hace_al_armar_no_al_importar(self):
        from enrutador import navegador
        with mock.patch.object(navegador, "elegir", return_value=(None, None, "no hay")):
            self.assertNotIn("--captura", encargo.cierre("t-1"))
            self.assertIn("instalar Firefox", armado.nota_sandbox())
        with mock.patch.object(navegador, "elegir", return_value=("firefox", "/usr/bin/firefox", "")):
            self.assertIn("--captura", encargo.cierre("t-1"))
            self.assertEqual(armado.nota_sandbox(), armado.NOTA_SANDBOX)


class NotaDelSandbox(unittest.TestCase):
    def test_con_firefox_da_la_linea_de_captura(self):
        nota = armado.nota_sandbox(disponible=True)
        self.assertIn("firefox --headless", nota)
        self.assertIn("enrutador.navegador", nota)

    def test_sin_firefox_no_da_un_comando_que_va_a_fallar(self):
        nota = armado.nota_sandbox(disponible=False)
        self.assertNotIn("firefox --headless", nota)
        self.assertNotIn("enrutador.navegador", nota)
        self.assertIn("no hay un navegador", nota)
        self.assertIn("instalar Firefox", nota)
        self.assertIn("sandbox", nota)    # lo demás de la nota sigue ahí


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se pueden armar las ventanas")
class EnElBoard(unittest.TestCase):
    def setUp(self):
        import tempfile
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        carpeta = Path(temporal.name)
        self.entrega = {"operacion": "entregar", "evidencia": "x", "capturas": []}
        for n, (tipo, ancho, alto) in enumerate((("movil", 390, 844), ("escritorio", 1280, 800))):
            ruta = carpeta / f"{n}-{tipo}.png"
            ruta.write_bytes(png(ancho, alto))
            self.entrega["capturas"].append({"ruta": str(ruta), "tipo": tipo,
                                             "ancho": ancho, "alto": alto})

    def etiquetas(self, widget):
        encontradas = []
        pendientes = [widget]
        while pendientes:
            w = pendientes.pop()
            if isinstance(w, Adw.Dialog):
                pendientes.append(w.get_child())
                continue
            if isinstance(w, Gtk.Label):
                encontradas.append(w.get_label())
            if isinstance(w, Gtk.Picture):
                encontradas.append("<imagen>")
            hijo = w.get_first_child()
            while hijo is not None:
                pendientes.append(hijo)
                hijo = hijo.get_next_sibling()
        return encontradas

    def test_la_seccion_ensena_las_imagenes_con_su_rotulo(self):
        from tareas.app.vista_capturas import seccion_capturas
        caja = seccion_capturas(self.entrega, None)
        textos = self.etiquetas(caja)
        self.assertEqual(textos.count("<imagen>"), 2)
        self.assertIn("Móvil · 390×844", textos)
        self.assertIn("Escritorio · 1280×800", textos)

    def test_sin_capturas_no_hay_seccion(self):
        from tareas.app.vista_capturas import seccion_capturas
        self.assertIsNone(seccion_capturas({"operacion": "entregar"}, None))
        self.assertIsNone(seccion_capturas(None, None))

    def test_la_ficha_las_enseña_en_una_entregada(self):
        from test_detalle_de_tarea import dialogo
        d, _, _ = dialogo("por-validar", bitacora={"cotejo-agcea3": self.entrega})
        self.assertEqual(self.etiquetas(d).count("<imagen>"), 2)

    def test_la_ficha_sin_capturas_no_cambia(self):
        from test_detalle_de_tarea import dialogo
        d, _, _ = dialogo("por-validar", bitacora={"cotejo-agcea3": {"operacion": "entregar",
                                                                  "evidencia": "x"}})
        self.assertNotIn("<imagen>", self.etiquetas(d))


if __name__ == "__main__":
    unittest.main()
