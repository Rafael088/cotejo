"""El empaquetado de Arch (`empaquetado/linux/construir.sh --arch`), de verdad.

Se salta entera si no hay `makepkg`/`bsdtar` (no es Arch): no hay forma barata de fingir
makepkg como se finge el espejo de MSYS2 en `test_empaquetado_windows.py`, así que cuando sí
corre, construye un paquete real — lo mismo que haría un release. Lo que prueba es justo lo que
se rompió una vez: que el `.BUILDINFO` que graba makepkg no lleva la ruta de este equipo ni el
usuario que lo compiló (construir en una carpeta de este repo, bajo `$HOME`, se lo pegaba), que
la carpeta temporal donde construye no sobrevive a la build, y que el `.pkg` ya instalado
—incluida su ruta real `usr/share/tareas-obsidian/linux/widget.py`, distinta de
`empaquetado/linux/widget.py`— pasa `herramientas/purga.py` sin hallazgos nuevos.
"""

import getpass
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

from herramientas import purga

CONSTRUIR = RAIZ / "empaquetado" / "linux" / "construir.sh"
HAY_MAKEPKG = shutil.which("makepkg") and shutil.which("bsdtar")


@unittest.skipUnless(HAY_MAKEPKG, "necesita makepkg y bsdtar (Arch) para construir de verdad")
class ConstruirArchTest(unittest.TestCase):
    def test_no_deja_restos_en_tmp_y_el_pkg_no_nombra_el_equipo_ni_pasa_la_purga(self):
        antes = {p.name for p in Path(tempfile.gettempdir()).glob("cotejo-arch.*")}

        with tempfile.TemporaryDirectory() as dist:
            resultado = subprocess.run(
                ["sh", str(CONSTRUIR), "--arch"],
                cwd=RAIZ, env={**os.environ, "DIST": dist},
                capture_output=True, text=True, timeout=120)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)

            # La carpeta de construcción (bajo /tmp, no bajo $DIST ni el repo) no sobrevive.
            despues = {p.name for p in Path(tempfile.gettempdir()).glob("cotejo-arch.*")}
            self.assertEqual(antes, despues, "quedó una carpeta de la build en /tmp")

            paquetes = list((Path(dist) / "arch").glob("*.pkg.tar.zst"))
            self.assertEqual(len(paquetes), 1, paquetes)
            paquete = paquetes[0]

            buildinfo = subprocess.run(
                ["bsdtar", "-xOf", str(paquete), ".BUILDINFO"],
                capture_output=True, text=True, check=True).stdout
            self.assertNotIn("/home/", buildinfo)
            self.assertNotIn(getpass.getuser(), buildinfo)
            self.assertNotIn(str(dist), buildinfo)
            self.assertNotIn(str(RAIZ), buildinfo)

            with tempfile.TemporaryDirectory() as extraido:
                subprocess.run(["bsdtar", "-xf", str(paquete), "-C", extraido], check=True)
                config = purga.cargar_config(purga.CONFIG_POR_DEFECTO)
                hallado = purga.escanear_arbol(Path(extraido), config)
                self.assertTrue(hallado.limpio, hallado.hallazgos)


if __name__ == "__main__":
    unittest.main()
