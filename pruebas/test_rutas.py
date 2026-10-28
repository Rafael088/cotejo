"""Dónde guarda Cotejo sus cosas en cada sistema, y que en Linux siga siendo donde era.

Las pruebas fingen el sistema cambiando `sys.platform` y el hogar: no hace falta un Mac ni un
Windows para saber qué ruta saldría en ellos. La última se pone roja si alguien vuelve a
escribir `~/.config` o `~/.local` a mano fuera de `tareas/rutas.py`.
"""

import importlib.util
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tareas import rutas

RAIZ = Path(__file__).resolve().parent.parent
HOGAR = Path("/hogar/de/nadie")
VARIABLES = ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "APPDATA", "LOCALAPPDATA", "COTEJO_ESTADO")


class EnCadaSistema(unittest.TestCase):
    def en(self, plataforma, **entorno):
        """Finge `plataforma`, un hogar de mentira y solo las variables que se pasen."""
        limpio = {k: v for k, v in os.environ.items() if k not in VARIABLES}
        for parche in (mock.patch.object(rutas.sys, "platform", plataforma),
                       mock.patch.object(rutas.Path, "home", return_value=HOGAR),
                       mock.patch.dict(os.environ, {**limpio, **entorno}, clear=True)):
            parche.start()
            self.addCleanup(parche.stop)

    def test_en_linux_nada_cambia_de_sitio(self):
        # El widget de la barra lee estado.json de ahí: es un contrato.
        self.en("linux")
        self.assertEqual(rutas.config_base(), HOGAR / ".config")
        self.assertEqual(rutas.estado(), HOGAR / ".local" / "state" / "tareas-obsidian")

    def test_en_linux_manda_xdg(self):
        self.en("linux", XDG_CONFIG_HOME="/xdg/config", XDG_STATE_HOME="/xdg/estado")
        self.assertEqual(rutas.config_base(), Path("/xdg/config"))
        self.assertEqual(rutas.estado(), Path("/xdg/estado/tareas-obsidian"))

    def test_en_macos_todo_va_en_application_support(self):
        # Aunque haya XDG en el entorno: en un Mac no es la convención del sistema.
        self.en("darwin", XDG_CONFIG_HOME="/xdg/config")
        base = HOGAR / "Library" / "Application Support"
        self.assertEqual(rutas.config_base(), base)
        self.assertEqual(rutas.estado(), base / "cotejo" / "estado")

    def test_en_windows_config_en_appdata_y_estado_en_localappdata(self):
        self.en("win32", APPDATA="C:/U/AppData/Roaming", LOCALAPPDATA="C:/U/AppData/Local")
        self.assertEqual(rutas.config_base(), Path("C:/U/AppData/Roaming"))
        self.assertEqual(rutas.estado(), Path("C:/U/AppData/Local/cotejo/estado"))

    def test_en_windows_sin_variables_cuelga_del_hogar(self):
        self.en("win32")
        self.assertEqual(rutas.config_base(), HOGAR / "AppData" / "Roaming")
        self.assertEqual(rutas.estado(), HOGAR / "AppData" / "Local" / "cotejo" / "estado")

    def test_cotejo_estado_gana_en_cualquier_sistema(self):
        for plataforma in ("linux", "darwin", "win32"):
            with self.subTest(plataforma):
                self.en(plataforma, COTEJO_ESTADO="/otra/parte")
                self.assertEqual(rutas.estado(), Path("/otra/parte"))

    def test_la_config_de_cotejo_cuelga_de_la_base_del_sistema(self):
        from tareas import configuracion
        self.en("darwin")
        self.assertEqual(configuracion.nueva(),
                         HOGAR / "Library" / "Application Support" / "cotejo" / "config.json")

    def test_obsidian_se_busca_donde_lo_guarda_cada_sistema(self):
        self.en("win32", APPDATA="C:/U/AppData/Roaming")
        self.assertEqual(rutas.obsidian(), Path("C:/U/AppData/Roaming/obsidian/obsidian.json"))

    def test_en_linux_obsidian_de_flatpak_se_encuentra(self):
        with tempfile.TemporaryDirectory() as hogar:
            flatpak = (Path(hogar) / ".var/app/md.obsidian.Obsidian/config/obsidian"
                       / "obsidian.json")
            flatpak.parent.mkdir(parents=True)
            flatpak.write_text("{}")
            self.en("linux")
            with mock.patch.object(rutas.Path, "home", return_value=Path(hogar)):
                self.assertEqual(rutas.obsidian(), flatpak)

    def test_el_adaptador_de_notion_busca_el_token_en_la_misma_carpeta(self):
        # Se instala y corre sin Cotejo, así que repite la cuenta: que no se desvíe.
        spec = importlib.util.spec_from_file_location(
            "cotejo_notion_rutas", RAIZ / "extras" / "notion" / "cotejo_notion.py")
        notion = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(notion)
        entornos = {"linux": {"XDG_CONFIG_HOME": "/xdg/config"}, "darwin": {},
                    "win32": {"APPDATA": "C:/U/AppData/Roaming"}}
        for plataforma, entorno in entornos.items():
            with self.subTest(plataforma):
                self.en(plataforma, **entorno)
                with mock.patch.object(notion.sys, "platform", plataforma), \
                        mock.patch.object(notion.os.path, "expanduser",
                                          side_effect=lambda r: r.replace("~", str(HOGAR))):
                    self.assertEqual(Path(notion.carpeta_config()), rutas.config_base())


class NingunaRutaAMano(unittest.TestCase):
    # skill.py escribe en ~/.config/opencode, que es donde opencode se lee en todos los sistemas;
    # el adaptador de Notion repite la cuenta de rutas.py y lo vigila la prueba de arriba.
    PERMITIDOS = {"tareas/rutas.py", "tareas/skill.py", "extras/notion/cotejo_notion.py"}
    PATRON = re.compile(r"""["'](?:~/)?\.(?:config|local)["'/]""")

    def test_nadie_escribe_config_ni_local_fuera_de_rutas(self):
        culpables = []
        for carpeta in ("tareas", "enrutador", "extras"):
            for archivo in (RAIZ / carpeta).rglob("*.py"):
                relativo = archivo.relative_to(RAIZ).as_posix()
                if relativo in self.PERMITIDOS:
                    continue
                for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
                    if self.PATRON.search(linea) and not linea.lstrip().startswith("#"):
                        culpables.append(f"{relativo}:{numero}: {linea.strip()}")
        self.assertEqual(culpables, [], "usa tareas.rutas en vez de escribir la ruta a mano")


class BoardJsonSigueAlEstado(unittest.TestCase):
    def test_board_json_se_mira_en_cada_uso(self):
        # Calculado al importar, las pruebas del board (que cambian COTEJO_ESTADO después)
        # leían y escribían el board.json de la persona: el proyecto elegido se colaba.
        try:
            from tareas.app import comun
        except (ImportError, ValueError):
            self.skipTest("sin GTK")
        with tempfile.TemporaryDirectory() as temporal, \
                mock.patch.dict(os.environ, {"COTEJO_ESTADO": temporal}):
            comun.guardar_board(proyecto="Prueba")
            self.assertEqual(comun.ruta_board(), Path(temporal) / "board.json")
            self.assertEqual(comun.cargar_board()["proyecto"], "Prueba")


if __name__ == "__main__":
    unittest.main()
