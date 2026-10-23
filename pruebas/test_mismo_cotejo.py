"""El lanzador `cotejo` del agente (enrutador/mismo_cotejo.py, cotejo-w7oeio): corre el mismo
código que el proceso que lo escribe, va primero en el PATH sin repetirse, y `otro` encuentra el
Cotejo de otra versión que habría quedado delante. Sin red, en carpetas temporales."""

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from apoyo import RAIZ  # noqa: F401
from enrutador import mismo_cotejo
from tareas import __version__, preparando


def falso(carpeta, salida):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "cotejo"
    ruta.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo "{salida}"
    """))
    ruta.chmod(0o755)
    return ruta


@unittest.skipIf(os.name == "nt", "el lanzador de prueba es de sh")
class MismoCotejo(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.bin = self.base / "estado" / "agente" / "bin"

    def test_el_lanzador_corre_el_codigo_de_este_proceso(self):
        destino = mismo_cotejo.preparar_lanzador(self.bin)
        self.assertEqual(mismo_cotejo.raiz(), Path(RAIZ).resolve())
        hecho = subprocess.run([str(destino / "cotejo"), "--version"], capture_output=True,
                               text=True, timeout=60, cwd=self.base)
        self.assertEqual(hecho.stdout.strip(), f"cotejo {__version__}")
        hecho = subprocess.run(
            [str(destino / "cotejo"), "anotar", "arquitectura", "--help"],
            capture_output=True, text=True, timeout=60, cwd=self.base)
        self.assertIn("--pieza", hecho.stdout)

    def test_un_tareas_en_la_carpeta_del_agente_no_lo_tapa(self):
        # El agente arranca en la carpeta del proyecto: un `tareas/` ahí no es Cotejo.
        (self.base / "tareas").mkdir()
        (self.base / "tareas" / "__init__.py").write_text("raise SystemExit('el falso')\n")
        destino = mismo_cotejo.preparar_lanzador(self.bin)
        hecho = subprocess.run([str(destino / "cotejo"), "--version"], capture_output=True,
                               text=True, timeout=60, cwd=self.base)
        self.assertEqual(hecho.stdout.strip(), f"cotejo {__version__}")

    def test_el_path_lo_pone_primero_y_una_sola_vez(self):
        base = {"PATH": os.pathsep.join(["/usr/bin", str(self.bin), "/bin"])}
        entorno = mismo_cotejo.entorno({"COTEJO_FUENTE": "repo"}, base=base, destino=self.bin)
        self.assertEqual(entorno["COTEJO_FUENTE"], "repo")
        self.assertEqual(entorno["PATH"].split(os.pathsep), [str(self.bin), "/usr/bin", "/bin"])
        # Otra vez sobre el resultado: no se acumula.
        otra = mismo_cotejo.entorno({}, base=entorno, destino=self.bin)
        self.assertEqual(otra["PATH"], entorno["PATH"])
        self.assertTrue(os.access(self.bin / "cotejo", os.X_OK))

    def test_otro_de_otra_version_misma_version_o_ninguno(self):
        otro = falso(self.base / "otro", "cotejo 1.0.0")
        base = {"PATH": str(otro.parent)}
        self.assertEqual(mismo_cotejo.otro(base=base, destino=self.bin),
                         {"ruta": str(otro), "version": "1.0.0", "esta": __version__})
        falso(self.base / "otro", f"cotejo {__version__}")
        self.assertIsNone(mismo_cotejo.otro(base=base, destino=self.bin))
        self.assertIsNone(mismo_cotejo.otro(base={"PATH": str(self.base / "vacio")},
                                            destino=self.bin))
        # El propio lanzador no cuenta como «otro».
        mismo_cotejo.preparar_lanzador(self.bin)
        self.assertIsNone(mismo_cotejo.otro(base={"PATH": str(self.bin)}, destino=self.bin))

    def test_una_version_que_no_se_lee_tambien_se_avisa(self):
        otro = falso(self.base / "otro", "no sé")
        dicho = mismo_cotejo.otro(base={"PATH": str(otro.parent)}, destino=self.bin)
        self.assertEqual(dicho["version"], "")
        self.assertIn("una versión que no supe leer", preparando.aviso_otro_cotejo(dicho))
        self.assertEqual(preparando.aviso_otro_cotejo(None), "")


if __name__ == "__main__":
    unittest.main()
