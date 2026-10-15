"""El oro del dot (cotejo-9gsi5m): existe, está completo y los PNG tienen su talla.

No necesita Chromium: solo mira lo que `herramientas/dot_oro.py` dejó en `pruebas/oro/dot/`.
Que regenerarlo dé lo mismo se comprueba a mano con `python3 herramientas/dot_oro.py --comprobar`.
"""

import json
import struct
import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from herramientas import dot_oro

ORO = dot_oro.DESTINO
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"


def talla_png(ruta):
    """(ancho, alto) leídos de la cabecera IHDR, sin depender de ninguna biblioteca de imágenes."""
    datos = ruta.read_bytes()[:24]
    assert datos[:8] == FIRMA_PNG, f"{ruta.name} no es un PNG"
    return struct.unpack(">II", datos[16:24])


class Oro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datos = json.loads((ORO / "oro.json").read_text(encoding="utf-8"))
        cls.muestras = {m["id"]: m for m in cls.datos["muestras"]}

    def test_la_cabecera_dice_lo_que_hay(self):
        self.assertEqual(self.datos["formato"], dot_oro.FORMATO)
        self.assertEqual(self.datos["lienzo"], 200)
        self.assertEqual(self.datos["tallas"], [250, 56, 24])
        self.assertEqual(self.datos["instantes"], [0, 0.3, 0.9, 1.6, 2.4])

    def test_cada_estado_y_la_entrada_tienen_todos_los_instantes(self):
        for estado in dot_oro.ESTADOS + ("entrada",):
            for t in dot_oro.INSTANTES:
                with self.subTest(estado=estado, t=t):
                    self.assertIn(f"{estado}@{t:g}", self.muestras)
        self.assertIn("entrada@0.38", self.muestras)

    def test_piensa_no_esta(self):
        self.assertFalse([i for i in self.muestras if i.startswith("piensa")])
        self.assertNotIn("piensa", {m["estado"] for m in self.muestras.values()})

    def test_hay_transiciones_de_ida_y_de_vuelta(self):
        trans = [m for m in self.muestras.values() if m["tipo"] == "transicion"]
        self.assertTrue(trans)
        for estado in dot_oro.ESTADOS[1:]:
            self.assertTrue([m for m in trans if m["desde"] == "idle" and m["estado"] == estado], estado)
            self.assertTrue([m for m in trans if m["desde"] == estado and m["estado"] == "idle"], estado)
        for m in trans:
            self.assertGreater(m["t"], 0)
            self.assertTrue(m["propiedades"])

    def test_cada_muestra_trae_sus_piezas_con_matriz(self):
        for ident, m in self.muestras.items():
            with self.subTest(muestra=ident):
                self.assertEqual(set(m["piezas"]), set(dot_oro.PIEZAS))
                for nombre, pieza in m["piezas"].items():
                    self.assertEqual(len(pieza["ctm"]), 6, nombre)
                    self.assertIn("opacidad", pieza)
                self.assertTrue(m["piezas"]["boca"]["d"].startswith("path("))

    def test_los_png_estan_y_tienen_la_talla_correcta(self):
        esperados = set()
        for ident, m in self.muestras.items():
            for talla in dot_oro.TALLAS:
                ruta = ORO / f"{m['png']}_{talla}.png"
                esperados.add(ruta.name)
                with self.subTest(muestra=ident, talla=talla):
                    self.assertTrue(ruta.exists(), ruta.name)
                    self.assertEqual(talla_png(ruta), (talla, talla))
        sobran = {f.name for f in ORO.glob("*.png")} - esperados
        self.assertFalse(sobran, f"PNG sin muestra: {sorted(sobran)[:5]}")

    def test_la_entrada_de_verdad_entra(self):
        """En t = 0 el dot está abajo, encogido e invisible. La primera versión del oro no
        llegaba a llamar a `ENTRAR` y la entrada salía idéntica a idle (cotejo-18bc08)."""
        mundo = self.muestras["entrada@0"]["piezas"]["mundo"]
        self.assertEqual(mundo["opacidad"], 0)
        self.assertEqual(mundo["ctm"][0], 0.55)
        self.assertNotEqual(self.muestras["entrada@0.3"]["piezas"]["mundo"]["ctm"],
                            self.muestras["idle@0.3"]["piezas"]["mundo"]["ctm"])

    def test_la_referencia_esta_copiada(self):
        for nombre in ("avatar.html", "avatar.css", "tokens.css"):
            self.assertTrue((dot_oro.REFERENCIA.parent / nombre).exists(), nombre)


if __name__ == "__main__":
    unittest.main()
