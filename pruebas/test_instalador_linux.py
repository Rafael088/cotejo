"""El instalador de Linux: `install.sh`, `uninstall.sh` y `empaquetado/linux/usuario.sh`.

Cada prueba instala de verdad, pero en un HOME de mentira (y, para el paquete, en un
`--destdir`): nada toca la instalación en uso, la config real ni la barra real. XDG y las
variables de Cotejo se quitan del entorno para que ninguna apunte fuera del temporal.

Vigila lo que un instalador rompe sin avisar: que la barra lea de donde la app escribe, que un
paquete no escriba en el $HOME de quien lo construye, que la CLI sola funcione sin PyGObject,
y que desinstalar quite lo que se puso sin llevarse la config.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

# Un Python sin PyGObject: `import gi` falla como si no estuviera instalado.
SIN_GI = """
import sys
class SinGi:
    def find_spec(self, nombre, ruta=None, objetivo=None):
        if nombre == "gi" or nombre.startswith("gi."):
            raise ModuleNotFoundError("No module named %r" % nombre, name=nombre)
sys.meta_path.insert(0, SinGi())
"""


HAY_GTK = subprocess.run([sys.executable, "-c", "import gi; gi.require_version('Gtk','4.0'); "
                          "gi.require_version('Adw','1')"], capture_output=True).returncode == 0


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("sh"), "solo en Linux")
class Instalador(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cotejo-instalador-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hogar = self.tmp / "hogar"
        self.hogar.mkdir()
        self.entorno = {k: v for k, v in os.environ.items()
                        if not k.startswith(("XDG_", "COTEJO_", "FOCO_", "PYTHON", "FORCE_COLOR"))}
        # argparse (3.14) pinta la ayuda si cree que hay una terminal.
        self.entorno.update(HOME=str(self.hogar), NO_COLOR="1", COTEJO_NO_PREGUNTAR_CLI="1")
        # fc-cache tarda dos segundos por instalación y no es lo que se prueba aquí.
        falsos = self.tmp / "falsos"
        falsos.mkdir()
        (falsos / "fc-cache").write_text("#!/bin/sh\nexit 0\n")
        (falsos / "fc-cache").chmod(0o755)
        self.entorno["PATH"] = f"{falsos}{os.pathsep}{self.entorno.get('PATH', '')}"
        self.bin = self.hogar / ".local/bin"
        self.destino = self.hogar / ".local/share/tareas-obsidian"

    def correr(self, *orden, cwd=None, codigo=0, **extra):
        hecho = subprocess.run([str(o) for o in orden], cwd=cwd or self.tmp, capture_output=True,
                               text=True, env={**self.entorno, **extra}, timeout=120)
        if hecho.returncode != codigo:
            self.fail(f"{orden} salió con {hecho.returncode}:\n{hecho.stdout}\n{hecho.stderr}")
        return hecho

    def instalar(self, *opciones, **extra):
        return self.correr("sh", RAIZ / "install.sh", *opciones, **extra)

    def con_omarchy(self):
        omarchy = self.hogar / ".config/omarchy"
        omarchy.mkdir(parents=True)
        (omarchy / "shell.json").write_text(json.dumps(
            {"bar": {"layout": {"right": [{"id": "reloj"}]}}}), encoding="utf-8")
        return omarchy

    def widgets(self, omarchy):
        datos = json.loads((omarchy / "shell.json").read_text(encoding="utf-8"))
        return [w["id"] for s in datos["bar"]["layout"].values() for w in s]

    def sin_gi(self):
        carpeta = self.tmp / "sin-gi"
        carpeta.mkdir(exist_ok=True)
        (carpeta / "sitecustomize.py").write_text(SIN_GI, encoding="utf-8")
        return {"PYTHONPATH": str(carpeta)}

    # --- la CLI sola ---------------------------------------------------------------------

    def test_la_cli_sola_se_instala_y_corre_sin_pygobject(self):
        sin_gi = self.sin_gi()
        self.correr(sys.executable, "-c", "import gi", codigo=1, **sin_gi)
        self.con_omarchy()
        self.instalar("--sin-board", **sin_gi)
        for nombre in ("cotejo", "tareas-obsidian", "foco", "cotejo-notion"):
            self.assertTrue(os.access(self.bin / nombre, os.X_OK), nombre)
        self.assertFalse((self.bin / "cotejoboard").exists())
        self.assertFalse((self.hogar / ".local/share/applications").exists())
        self.assertFalse((self.hogar / ".config/omarchy/plugins/cotejo.barra").exists())
        ayuda = self.correr(self.bin / "cotejo", "--help", **sin_gi)
        self.assertIn("usage: cotejo", ayuda.stdout)

    def test_el_lanzador_no_se_deja_suplantar_por_la_carpeta_actual(self):
        self.instalar("--sin-board", "--sin-agentes")
        trampa = self.tmp / "trampa" / "tareas"
        trampa.mkdir(parents=True)
        (trampa / "__init__.py").write_text("raise SystemExit('se cargó el tareas equivocado')")
        (trampa / "cli.py").write_text("raise SystemExit('se cargó el tareas equivocado')")
        ayuda = self.correr(self.bin / "cotejo", "--help", cwd=trampa.parent)
        self.assertIn("usage: cotejo", ayuda.stdout)

    def test_el_estado_para_la_barra_se_escribe_donde_dicen_las_rutas(self):
        vault = self.tmp / "vault"
        (vault / ".obsidian").mkdir(parents=True)
        self.instalar("--sin-board", "--sin-agentes")
        self.correr(self.bin / "tareas-obsidian", "--estado", COTEJO_VAULT=str(vault))
        self.assertTrue((self.hogar / ".local/state/tareas-obsidian/estado.json").exists())

    # --- la instalación de usuario, con board ------------------------------------------------

    @unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4/libadwaita")
    def test_la_de_usuario_pone_board_menu_agentes_y_widget(self):
        omarchy = self.con_omarchy()
        (self.hogar / ".claude").mkdir()
        vieja = self.hogar / ".config/foco"
        vieja.mkdir()
        (vieja / "config.json").write_text("{}", encoding="utf-8")
        self.instalar()

        self.assertTrue(os.access(self.bin / "cotejoboard", os.X_OK))
        self.assertIn("from tareas.board import main", (self.bin / "cotejoboard").read_text())
        self.assertIn("from tareas.__main__ import main", (self.bin / "cotejo").read_text())
        escritorio = self.hogar / ".local/share/applications/io.github.cotejoapp.Cotejo.desktop"
        self.assertIn(f"Exec={self.bin}/tareas-obsidian\n", escritorio.read_text())
        self.assertTrue((self.hogar / ".local/share/fonts/tareas-obsidian").is_dir())
        self.assertTrue((self.hogar / ".claude/skills/cotejo/SKILL.md").exists())
        self.assertTrue((self.hogar / ".config/foco").is_symlink())
        self.assertTrue((self.hogar / ".config/cotejo/config.json").exists())

        qml = (omarchy / "plugins/cotejo.barra/Widget.qml").read_text(encoding="utf-8")
        self.assertIn(json.dumps(str(self.bin / "tareas-obsidian")), qml)
        self.assertIn(json.dumps(str(self.hogar / ".local/state/tareas-obsidian/estado.json")), qml)
        self.assertEqual(self.widgets(omarchy), ["cotejo.barra", "reloj"])
        self.assertTrue((omarchy / "shell.json.bak").exists())

        # Reinstalar no pone un segundo widget ni pierde dónde lo dejó el usuario.
        datos = json.loads((omarchy / "shell.json").read_text(encoding="utf-8"))
        datos["bar"]["layout"] = {"left": [{"id": "cotejo.barra"}], "right": [{"id": "reloj"}]}
        (omarchy / "shell.json").write_text(json.dumps(datos), encoding="utf-8")
        self.instalar()
        self.assertEqual(self.widgets(omarchy), ["cotejo.barra", "reloj"])
        self.assertEqual(json.loads((omarchy / "shell.json").read_text())["bar"]["layout"]["left"],
                         [{"id": "cotejo.barra"}])

    @unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4/libadwaita")
    def test_la_barra_lee_de_xdg_state_home_si_lo_hay(self):
        omarchy = self.con_omarchy()
        estado = self.tmp / "estado-propio"
        self.instalar("--sin-agentes", XDG_STATE_HOME=str(estado))
        qml = (omarchy / "plugins/cotejo.barra/Widget.qml").read_text(encoding="utf-8")
        self.assertIn(json.dumps(str(estado / "tareas-obsidian/estado.json")), qml)

    @unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4/libadwaita")
    def test_sin_widget_no_toca_la_barra(self):
        omarchy = self.con_omarchy()
        antes = (omarchy / "shell.json").read_text()
        self.instalar("--sin-widget", "--sin-agentes")
        self.assertFalse((omarchy / "plugins").exists())
        self.assertEqual((omarchy / "shell.json").read_text(), antes)

    @unittest.skipUnless(HAY_GTK, "sin PyGObject/GTK 4/libadwaita")
    def test_desinstalar_quita_lo_puesto_y_conserva_la_config(self):
        omarchy = self.con_omarchy()
        (self.hogar / ".claude").mkdir()
        config = self.hogar / ".config/cotejo/config.json"
        config.parent.mkdir(parents=True)
        config.write_text("{}", encoding="utf-8")
        self.instalar()
        self.correr("sh", RAIZ / "uninstall.sh")

        self.assertFalse(self.destino.exists())
        self.assertEqual(sorted(p.name for p in self.bin.iterdir()), [])
        self.assertFalse((self.hogar / ".local/share/applications/io.github.cotejoapp.Cotejo.desktop").exists())
        self.assertFalse((self.hogar / ".claude/skills/cotejo").exists())
        self.assertFalse((omarchy / "plugins/cotejo.barra").exists())
        self.assertEqual(self.widgets(omarchy), ["reloj"])
        self.assertTrue(config.exists())

    # --- el paquete del sistema --------------------------------------------------------------

    def test_el_paquete_no_toca_ningun_hogar_ni_nombra_el_destdir(self):
        raiz = self.tmp / "paquete"
        # Construir un paquete no necesita PyGObject: solo instalarlo para abrir el board.
        self.instalar("--prefijo", "/usr", "--destdir", raiz, **self.sin_gi())
        self.assertEqual(list(self.hogar.iterdir()), [], "el paquete escribió en el $HOME")

        usr = raiz / "usr"
        self.assertIn('sys.path.insert(0, "/usr/share/tareas-obsidian")', (usr / "bin/cotejo").read_text())
        self.assertIn("Exec=/usr/bin/tareas-obsidian\n",
                      (usr / "share/applications/io.github.cotejoapp.Cotejo.desktop").read_text())
        for archivo in raiz.rglob("*"):
            if archivo.is_file() and archivo.suffix not in (".ttf", ".otf"):
                self.assertNotIn(str(raiz), archivo.read_text(encoding="utf-8", errors="ignore"),
                                 f"{archivo} nombra la carpeta de empaquetado")
        self.assertFalse(list(raiz.rglob("__pycache__")))

    def test_con_un_paquete_cada_usuario_pone_su_widget(self):
        raiz = self.tmp / "paquete"
        self.instalar("--prefijo", "/usr", "--destdir", raiz)
        omarchy = self.con_omarchy()
        usuario = raiz / "usr/share/tareas-obsidian/linux/usuario.sh"
        self.correr("sh", usuario, "--sin-agentes")
        qml = (omarchy / "plugins/cotejo.barra/Widget.qml").read_text(encoding="utf-8")
        # Sin --bin, el de la instalación: <prefijo>/share/tareas-obsidian → <prefijo>/bin.
        self.assertIn(json.dumps(str(raiz / "usr/bin/tareas-obsidian")), qml)
        self.assertEqual(self.widgets(omarchy), ["cotejo.barra", "reloj"])

        self.correr("sh", usuario, "--quitar", "--sin-agentes")
        self.assertFalse((omarchy / "plugins/cotejo.barra").exists())
        self.assertEqual(self.widgets(omarchy), ["reloj"])

    def hace_falta(self, destino):
        """Lo que diría el board de esa instalación al arrancar: el argv de usuario.sh o None."""
        hecho = self.correr(sys.executable, "-c",
                            "import json; from tareas import usuario; "
                            "print(json.dumps(usuario.hace_falta()))", cwd=destino)
        return json.loads(hecho.stdout)

    def test_con_un_paquete_el_board_pone_lo_del_usuario_solo_si_falta(self):
        # cotejo-8ecldw: con pacman el widget no aparecía nunca, porque nadie corría usuario.sh.
        raiz = self.tmp / "paquete"
        self.instalar("--prefijo", "/usr", "--destdir", raiz)
        omarchy = self.con_omarchy()
        destino = raiz / "usr/share/tareas-obsidian"
        script = destino / "linux/usuario.sh"
        self.assertEqual(self.hace_falta(destino), ["sh", str(script)])

        # Lo que hace el board con ese argv; después ya no hace falta.
        self.correr("sh", script)
        self.assertTrue((omarchy / "plugins/cotejo.barra/Widget.qml").exists())
        anotado = json.loads((self.hogar / ".local/state/tareas-obsidian/usuario.json").read_text())
        self.assertEqual((anotado["widget"], anotado["agentes"]), ("auto", True))
        self.assertIsNone(self.hace_falta(destino))

        # Otra versión: hay que repetirlo, con las opciones que se eligieron.
        self.correr("sh", script, "--sin-widget", "--sin-agentes")
        marca = self.hogar / ".local/state/tareas-obsidian/usuario.json"
        marca.write_text(json.dumps({**json.loads(marca.read_text()), "version": "0.9"}))
        self.assertEqual(self.hace_falta(destino),
                         ["sh", str(script), "--sin-widget", "--sin-agentes"])

        # Quitado a propósito, no vuelve solo.
        self.correr("sh", script, "--quitar", "--sin-agentes")
        self.assertIsNone(self.hace_falta(destino))

    def test_doctor_dice_que_falta_lo_del_usuario_y_el_widget(self):
        raiz = self.tmp / "paquete"
        self.instalar("--prefijo", "/usr", "--destdir", raiz)
        self.con_omarchy()
        vault = self.tmp / "vault"
        (vault / ".obsidian").mkdir(parents=True)
        destino = raiz / "usr/share/tareas-obsidian"
        # El lanzador de usr/bin apunta a /usr/share (el de la máquina): se corre el empaquetado.
        doctor = json.loads(self.correr(sys.executable, "-m", "tareas", "doctor", cwd=destino,
                                        COTEJO_VAULT=str(vault)).stdout)
        self.assertFalse(doctor["usuario"]["puesto"])
        self.assertIn("usuario.sh", doctor["salida"])
        self.assertTrue(any("widget" in a for a in doctor["usuario"]["avisos"]))
        self.correr("sh", raiz / "usr/share/tareas-obsidian/linux/usuario.sh", "--sin-agentes")
        doctor = json.loads(self.correr(sys.executable, "-m", "tareas", "doctor", cwd=destino,
                                        COTEJO_VAULT=str(vault)).stdout)
        self.assertEqual(doctor["usuario"]["avisos"], [])
        self.assertTrue(doctor["usuario"]["widget"])

    @unittest.skipUnless((RAIZ / ".git").exists() and shutil.which("git"), "no es un checkout de git")
    def test_el_tarball_trae_todo_lo_que_install_sh_copia(self):
        # Sale de HEAD: lo que se prueba es lo que está en el último commit.
        dist = self.tmp / "dist"
        hecho = self.correr("sh", RAIZ / "empaquetado/linux/construir.sh",
                            DIST=str(dist), COTEJO_VERSION="0.prueba")
        tarball = dist / "cotejo-0.prueba-linux.tar.gz"
        self.assertEqual(hecho.stdout.strip(), str(tarball))
        with tarfile.open(tarball) as archivo:
            archivo.extractall(self.tmp / "suelto", filter="data")
        suelto = self.tmp / "suelto/cotejo-0.prueba"
        self.assertFalse((suelto / "pruebas").exists())
        # Con board y en un destdir: así hacen falta todas las piezas y no se toca ningún hogar.
        raiz = self.tmp / "paquete"
        self.correr("sh", suelto / "install.sh", "--prefijo", "/usr", "--destdir", raiz)
        self.assertTrue((raiz / "usr/share/tareas-obsidian/barra/cotejo.barra/Widget.qml").exists())
        ayuda = self.correr(sys.executable, raiz / "usr/bin/cotejo", "--help",
                            PYTHONPATH=str(raiz / "usr/share/tareas-obsidian"))
        self.assertIn("usage: cotejo", ayuda.stdout)

    def test_destdir_sin_prefijo_se_rechaza(self):
        self.instalar("--destdir", self.tmp / "x", codigo=2)
        self.assertFalse((self.tmp / "x").exists())

    def test_los_scripts_son_sh_valido(self):
        for script in ("install.sh", "uninstall.sh", "empaquetado/linux/usuario.sh",
                       "empaquetado/linux/construir.sh"):
            self.correr("sh", "-n", RAIZ / script)

    def test_el_widget_sigue_declarando_las_rutas_que_el_instalador_reescribe(self):
        qml = (RAIZ / "barra/cotejo.barra/Widget.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property string archivo: ", qml)
        self.assertIn("readonly property string lanzador: ", qml)


if __name__ == "__main__":
    unittest.main()
