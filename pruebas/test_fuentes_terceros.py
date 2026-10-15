"""`empaquetado/windows/fuentes_terceros.py` (H11): el archivo de fuentes de terceros, sin red.

Como en `test_empaquetado_windows.py`, un "espejo" de MSYS2 en una carpeta (`file://`) hace de
`FUENTES`: ahí se publican unos `.src.tar.zst` de mentira y se comprueba que `armar` baja solo
los de los paquetes LGPL/GPL, arma el `.tar` final con `LEEME.txt` y `SHA256SUMS`, y que los
otros (p. ej. MIT) se quedan fuera.
"""

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AQUI = RAIZ / "empaquetado" / "windows"

_spec = importlib.util.spec_from_file_location("fuentes_terceros", AQUI / "fuentes_terceros.py")
fuentes_terceros = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fuentes_terceros)
construir = fuentes_terceros.construir


def _tar_gz(archivos):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for ruta, datos in archivos.items():
            info = tarfile.TarInfo(ruta)
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
    return buffer.getvalue()


PAQUETES_TXT = (
    "mingw-w64-ucrt-x86_64-glib2-2.90.0-1-any.pkg.tar.zst  sha256:aa  "
    "licencia:spdx:LGPL-2.1-or-later  fuente:mingw-w64-glib2-2.90.0-1.src.tar.zst\n"
    "mingw-w64-ucrt-x86_64-gmp-6.3.0-2-any.pkg.tar.zst  sha256:bb  "
    "licencia:LGPL3 AND GPL  fuente:mingw-w64-gmp-6.3.0-2.src.tar.zst\n"
    "mingw-w64-ucrt-x86_64-libffi-3.4-1-any.pkg.tar.zst  sha256:cc  "
    "licencia:spdx:MIT  fuente:mingw-w64-libffi-3.4-1.src.tar.zst\n"
)


class ElArchivoDeFuentes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.paquetes_txt = self.tmp / "PAQUETES.txt"
        self.paquetes_txt.write_text(PAQUETES_TXT, encoding="utf-8")
        self.fuentes = self.tmp / "fuentes"
        self.fuentes.mkdir()
        for nombre in ("mingw-w64-glib2-2.90.0-1.src.tar.zst", "mingw-w64-gmp-6.3.0-2.src.tar.zst"):
            (self.fuentes / nombre).write_bytes(_tar_gz({f"{nombre}/PKGBUILD": b"# de mentira"}))
        self.salida = self.tmp / "salida"

    def test_lee_solo_los_paquetes_lgpl_o_gpl(self):
        elegidos = fuentes_terceros.leer_paquetes_gpl(self.paquetes_txt)
        self.assertEqual(set(elegidos), {"mingw-w64-glib2-2.90.0-1.src.tar.zst",
                                         "mingw-w64-gmp-6.3.0-2.src.tar.zst"})
        self.assertNotIn("mingw-w64-libffi-3.4-1.src.tar.zst", elegidos)

    def test_una_linea_que_no_entiende_falla_con_el_numero(self):
        roto = self.tmp / "roto.txt"
        roto.write_text("esto no es una línea de PAQUETES.txt\n", encoding="utf-8")
        with self.assertRaises(fuentes_terceros.ErrorDeFuentes) as error:
            fuentes_terceros.leer_paquetes_gpl(roto)
        self.assertIn("roto.txt:1", str(error.exception))

    def test_sin_ningun_paquete_gpl_falla_claro(self):
        solo_mit = self.tmp / "solo_mit.txt"
        solo_mit.write_text(
            "mingw-w64-ucrt-x86_64-libffi-3.4-1-any.pkg.tar.zst  sha256:cc  "
            "licencia:spdx:MIT  fuente:mingw-w64-libffi-3.4-1.src.tar.zst\n", encoding="utf-8")
        with self.assertRaises(fuentes_terceros.ErrorDeFuentes):
            fuentes_terceros.armar(solo_mit, "9.9.9", self.salida, self.fuentes.as_uri(),
                                   self.tmp / "cache")

    def test_arma_el_tar_con_leeme_y_sha256sums(self):
        tar_final = fuentes_terceros.armar(self.paquetes_txt, "9.9.9", self.salida,
                                           self.fuentes.as_uri(), self.tmp / "cache")
        self.assertEqual(tar_final, self.salida / "Cotejo-9.9.9-fuentes-terceros.tar")
        with tarfile.open(tar_final) as tar:
            nombres = {Path(n).name for n in tar.getnames()}
            self.assertEqual(nombres, {
                "mingw-w64-glib2-2.90.0-1.src.tar.zst",
                "mingw-w64-gmp-6.3.0-2.src.tar.zst", "SHA256SUMS", "LEEME.txt"})
            # libffi (MIT) no entra: no es ni LGPL ni GPL.
            self.assertFalse(any("libffi" in n for n in tar.getnames()))
            prefijo = "Cotejo-9.9.9-fuentes-terceros/"
            sha256sums = tar.extractfile(prefijo + "SHA256SUMS").read().decode()
            leeme = tar.extractfile(prefijo + "LEEME.txt").read().decode()
        self.assertIn("9.9.9", leeme)
        self.assertIn("mingw-w64-gmp-6.3.0-2.src.tar.zst", leeme)
        for nombre in ("mingw-w64-glib2-2.90.0-1.src.tar.zst", "mingw-w64-gmp-6.3.0-2.src.tar.zst"):
            esperado = hashlib.sha256((self.fuentes / nombre).read_bytes()).hexdigest()
            self.assertIn(f"{esperado}  {nombre}", sha256sums)
        # Repetirlo no deja basura de la corrida anterior ni falla por que ya exista la carpeta.
        fuentes_terceros.armar(self.paquetes_txt, "9.9.9", self.salida, self.fuentes.as_uri(),
                               self.tmp / "cache")
        self.assertEqual(list(self.salida.glob("Cotejo-9.9.9-fuentes-terceros*")), [tar_final])

    def test_acepta_la_carpeta_runtime_en_vez_del_paquetes_txt(self):
        runtime = self.tmp / "runtime2"
        runtime.mkdir()
        (runtime / "PAQUETES.txt").write_text(PAQUETES_TXT, encoding="utf-8")
        codigo = fuentes_terceros.main([str(runtime), "--version", "9.9.9",
                                        "--salida", str(self.salida),
                                        "--fuentes", self.fuentes.as_uri(),
                                        "--cache", str(self.tmp / "cache")])
        self.assertEqual(codigo, 0)
        self.assertTrue((self.salida / "Cotejo-9.9.9-fuentes-terceros.tar").is_file())

    def test_sin_paquetes_txt_dice_que_corra_construir_primero(self):
        vacia = self.tmp / "vacia"
        vacia.mkdir()
        codigo = fuentes_terceros.main([str(vacia), "--salida", str(self.salida)])
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
