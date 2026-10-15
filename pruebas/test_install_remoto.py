"""El instalador por comando de Linux: `web/public/install.sh` (cotejo-pq7y96).

    curl -fsSL https://cotejo.dev/install.sh | sh

Se prueba sin red: COTEJO_DESCARGAS apunta a una carpeta con un tar.gz armado por
`construir.sh` y su SHA256SUMS (curl lee `file://`), y todo se instala en un HOME de mentira.
Lo que se vigila es lo que no puede fallar en silencio: que una suma que no coincide no instale
nada, que volver a correrlo actualice, y que sin el board instale al menos la CLI.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

SCRIPT = RAIZ / "web" / "public" / "install.sh"


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("curl")
                     and shutil.which("git"), "Linux con curl y git")
class InstalarPorComando(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="cotejo-remoto-"))
        cls.version = subprocess.run(["sh", RAIZ / "empaquetado/linux/construir.sh", "--version"],
                                     capture_output=True, text=True, check=True).stdout.strip()
        cls.release = cls.tmp / "release"
        subprocess.run(["sh", RAIZ / "empaquetado/linux/construir.sh"], check=True,
                       capture_output=True, env={**os.environ, "DIST": str(cls.release)})
        cls.paquete = cls.release / f"cotejo-{cls.version}-linux.tar.gz"
        cls.suma = hashlib.sha256(cls.paquete.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.hogar = Path(tempfile.mkdtemp(dir=self.tmp))
        self.escribir_sumas(self.suma)

    def escribir_sumas(self, suma):
        (self.release / "SHA256SUMS").write_text(
            f"{suma}  {self.paquete.name}\n{'0' * 64}  otro-archivo.exe\n")

    def instalar(self, *opciones, codigo=0, sin_gi=False):
        entorno = {k: v for k, v in os.environ.items()
                   if not k.startswith(("XDG_", "COTEJO_", "FOCO_", "PYTHON"))}
        entorno.update(HOME=str(self.hogar), COTEJO_VERSION=self.version,
                       COTEJO_DESCARGAS=f"file://{self.release}", NO_COLOR="1")
        if sin_gi:
            carpeta = self.hogar / "sin-gi"
            carpeta.mkdir(exist_ok=True)
            (carpeta / "sitecustomize.py").write_text(
                "import sys\nclass S:\n    def find_spec(self, n, r=None, o=None):\n"
                "        if n == 'gi' or n.startswith('gi.'):\n"
                "            raise ModuleNotFoundError(n, name=n)\nsys.meta_path.insert(0, S())\n")
            entorno["PYTHONPATH"] = str(carpeta)
        hecho = subprocess.run(["sh", SCRIPT, *opciones], capture_output=True, text=True,
                               env=entorno, cwd=self.hogar, timeout=120)
        self.assertEqual(hecho.returncode, codigo, f"{hecho.stdout}\n{hecho.stderr}")
        return hecho.stdout + hecho.stderr

    def version_instalada(self):
        return subprocess.run([self.hogar / ".local/bin/cotejo", "--version"],
                              capture_output=True, text=True,
                              env={**os.environ, "HOME": str(self.hogar)}).stdout.strip()

    def test_instala_comprobando_la_suma_y_reinstalar_lo_dice(self):
        salida = self.instalar("--sin-board", "--sin-agentes")
        self.assertIn(f"instalando la {self.version}", salida)
        self.assertIn(f"SHA-256 {self.suma}", salida)
        self.assertEqual(self.version_instalada(), f"cotejo {self.version}")
        self.assertIn(f"ya tienes la {self.version}", self.instalar("--sin-board", "--sin-agentes"))

    def test_una_suma_que_no_coincide_no_instala_nada(self):
        self.escribir_sumas("f" * 64)
        salida = self.instalar("--sin-board", codigo=1)
        self.assertIn("no coincide", salida)
        self.assertFalse((self.hogar / ".local").exists())

    def test_sin_la_suma_del_paquete_no_instala_nada(self):
        (self.release / "SHA256SUMS").write_text(f"{'0' * 64}  otro-archivo.exe\n")
        self.assertIn("no trae la suma", self.instalar(codigo=1))
        self.assertFalse((self.hogar / ".local").exists())

    def test_sin_las_dependencias_del_board_instala_la_cli_y_dice_que_falta(self):
        salida = self.instalar("--sin-agentes", sin_gi=True)
        self.assertIn("instalo solo la CLI", salida)
        self.assertTrue((self.hogar / ".local/bin/cotejo").exists())
        self.assertFalse((self.hogar / ".local/bin/cotejoboard").exists())


class ElComandoDeLaWeb(unittest.TestCase):
    def test_la_web_instala_con_el_comando_corto_que_sirve_pages(self):
        config = (RAIZ / "web/src/config.js").read_text(encoding="utf-8")
        self.assertIn("cotejo.dev", config)
        self.assertIn("/install.sh | sh", config)

    def test_y_en_windows_el_de_install_ps1(self):
        config = (RAIZ / "web/src/config.js").read_text(encoding="utf-8")
        self.assertIn("/install.ps1 | iex", config)


class InstalarEnWindows(unittest.TestCase):
    """`web/public/install.ps1` se corre de verdad en .github/workflows/install-ps1.yml (Windows);
    aquí se vigila lo que se puede leer sin PowerShell (cotejo-9pmnwj)."""

    TEXTO = (RAIZ / "web/public/install.ps1").read_text(encoding="utf-8")

    def test_no_cierra_la_sesion_de_quien_lo_corre(self):
        # Con `irm | iex` el script corre en la PowerShell del usuario: un `exit` se la cierra.
        import re
        codigo = "\n".join(l for l in self.TEXTO.splitlines() if not l.lstrip().startswith("#"))
        self.assertIsNone(re.search(r"(?i)\bexit\b", codigo))

    def test_lee_la_version_instalada_del_appid_del_instalador(self):
        import re
        iss = (RAIZ / "empaquetado/windows/cotejo.iss").read_text(encoding="utf-8")
        appid = re.search(r"AppId=\{(\{[0-9A-F-]+\})", iss).group(1)
        self.assertIn(f"{appid}_is1", self.TEXTO)

    def test_comprueba_la_suma_antes_de_ejecutar_y_lo_corre_en_silencio(self):
        self.assertLess(self.TEXTO.index("Get-FileHash"), self.TEXTO.index("Start-Process"))
        for bandera in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER"):
            self.assertIn(bandera, self.TEXTO)
        self.assertIn("instalador.exe", self.TEXTO)   # el instalador, no un ZIP
