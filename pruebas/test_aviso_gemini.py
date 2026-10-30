"""El aviso en llano de que Gemini no arranca por el `.gemini/settings.json` del proyecto
(cotejo-dzhzca, sobre cotejo-lbwsq4).

Desde cotejo-lbwsq4, si el `.gemini/settings.json` del worktree trae hooks, comandos de
herramientas propias o políticas, el worktree va sin confianza y Gemini, sin interfaz, se niega
a arrancar con `FatalUntrustedWorkspaceError` —solo en su log, y en inglés—. Aquí se vigila que
`despachar` y el board lo digan **antes de lanzar**, con el archivo y qué hacer, y que no toquen
la tarea; y que sin nada de eso, o con otro cliente, no digan nada.
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apoyo import proyecto  # pone la raíz del repo en sys.path
from test_despacho_board import HAY_GIT, ConClienteFalso

from enrutador import clientes, despacho, despacho_board, motor


def pon_gemini_falso(carpeta):
    """Un `gemini` ejecutable en `carpeta`, para que `comprobar` no se queje de que no está
    antes de llegar al aviso que mira esta prueba (que es lo que pasa en el CI, sin él)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "gemini"
    ruta.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)


def escribe_ajustes(carpeta, ajustes):
    (carpeta / ".gemini").mkdir(parents=True, exist_ok=True)
    ruta = carpeta / ".gemini" / "settings.json"
    ruta.write_text(ajustes if isinstance(ajustes, str) else json.dumps(ajustes))
    return ruta


class ElAviso(unittest.TestCase):
    """`clientes.aviso_de_gemini`: qué archivo, qué trae y qué hacer, en llano."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name)

    def test_sin_archivo_o_sin_nada_que_corra_solo_no_hay_aviso(self):
        self.assertEqual(clientes.aviso_de_gemini(self.carpeta), "")
        escribe_ajustes(self.carpeta, {"ui": {"theme": "x"},
                                       "mcpServers": {"mio": {"command": "mio"}},
                                       "hooks": {"SessionStart": []},
                                       "tools": {"discoveryCommand": ""}})
        self.assertEqual(clientes.aviso_de_gemini(self.carpeta), "")

    def test_dice_el_archivo_lo_que_trae_y_que_hacer(self):
        casos = {
            "hooks": ({"hooks": {"SessionStart": [{"hooks": [{"type": "command",
                                                              "command": "touch x"}]}]}},
                      "hooks"),
            "descubrir": ({"tools": {"discoveryCommand": "touch x"}}, "tools.discoveryCommand"),
            "llamar": ({"tools": {"callCommand": "touch x"}}, "tools.callCommand"),
            "políticas": ({"policyPaths": ["p.toml"]}, "policyPaths"),
            "de administrador": ({"adminPolicyPaths": ["p.toml"]}, "adminPolicyPaths"),
        }
        for nombre, (ajustes, trozo) in casos.items():
            with self.subTest(nombre):
                ruta = escribe_ajustes(self.carpeta, ajustes)
                dicho = clientes.aviso_de_gemini(self.carpeta)
                self.assertIn(str(ruta), dicho)          # qué archivo
                self.assertIn(trozo, dicho)              # qué trae
                self.assertIn("FatalUntrustedWorkspaceError", dicho)   # lo del log
                self.assertIn("Quita", dicho)            # qué hacer
                self.assertIn("vuelve a lanzarla", dicho)

    def test_un_json_roto_tambien_lo_dice(self):
        ruta = escribe_ajustes(self.carpeta, "{ esto no es json")
        dicho = clientes.aviso_de_gemini(self.carpeta)
        self.assertIn(str(ruta), dicho)
        self.assertIn("no se entiende", dicho)
        self.assertIn("FatalUntrustedWorkspaceError", dicho)
        self.assertIn("Arréglalo o bórralo", dicho)

    def test_sin_carpeta_no_dice_nada(self):
        self.assertEqual(clientes.aviso_de_gemini(None), "")
        self.assertEqual(clientes.aviso_de_gemini(""), "")


class AntesDeTomar(unittest.TestCase):
    """`despacho.antes_de_tomar`, que es lo que corre antes de tomar en los dos caminos."""

    class SinProblemas:
        def comprobar(self, encargo):
            return ""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name)
        self.repo = self.carpeta / "repo"
        self.repo.mkdir()

    def encargo(self, cliente, directorio):
        return motor.Encargo(prompt="", modelo="x", cliente=cliente, directorio=directorio)

    def rechazos(self, encargo, plan_wt=None):
        return dict(despacho.antes_de_tomar(self.SinProblemas(), encargo, plan_wt))

    def test_sin_el_archivo_no_dice_nada(self):
        self.assertEqual(self.rechazos(self.encargo("gemini", self.repo)), {})
        self.assertEqual(self.rechazos(self.encargo("claude", self.repo)), {})

    def test_con_hooks_se_dice_antes_de_tomar(self):
        ruta = escribe_ajustes(self.repo, {"tools": {"callCommand": "touch x"}})
        rechazos = self.rechazos(self.encargo("gemini", self.repo))
        self.assertIn("gemini_sin_confianza", rechazos)
        self.assertIn(str(ruta), rechazos["gemini_sin_confianza"])
        # Otro cliente no carga ese archivo: no se rechaza por él.
        self.assertEqual(self.rechazos(self.encargo("claude", self.repo)), {})

    def test_el_worktree_aun_sin_crear_mira_el_repo_del_que_sale(self):
        ruta = escribe_ajustes(self.repo, {"policyPaths": ["p.toml"]})
        plan_wt = {"repo": str(self.repo), "ruta": str(self.carpeta / "wt" / "cotejo-x"),
                   "rama": "cotejo/cotejo-x"}
        rechazos = self.rechazos(self.encargo("gemini", plan_wt["ruta"]), plan_wt)
        self.assertIn(str(ruta), rechazos["gemini_sin_confianza"])


@unittest.skipUnless(HAY_GIT, "sin git")
class ElBoardYDespachar(ConClienteFalso):
    """De punta a punta: ni el board ni `despachar` lanzan, y la tarea no se toca."""

    def setUp(self):
        super().setUp()
        bin_ = self.fuera / "bin"
        pon_gemini_falso(bin_)
        parche = mock.patch.dict(os.environ, {"PATH": os.pathsep.join(
            [str(bin_), os.environ.get("PATH", "")])})
        parche.start()
        self.addCleanup(parche.stop)
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Con Gemini #agente/gemini-flash ^cotejo-gem",
            "- [ ] Con Claude #agente/sonnet ^cotejo-claude"))
        self.ruta = escribe_ajustes(self.repo, {"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "touch x"}]}]}})

    def test_el_board_no_lanza_y_lo_dice_con_el_archivo(self):
        with self.assertRaises(despacho_board.NoSePuede) as error:
            self.lanzar("cotejo-gem")
        dicho = str(error.exception)
        for trozo in (str(self.ruta), "hooks", "FatalUntrustedWorkspaceError", "Quita"):
            self.assertIn(trozo, dicho)
        # No se tomó: la línea sigue pendiente y sin dueño, y no hay registro de lanzamiento.
        self.assertIn("- [ ] Con Gemini #agente/gemini-flash ^cotejo-gem", self.leer_nota("Uno.md"))
        self.assertIsNone(self._registro("cotejo-gem"))

    def test_despachar_lo_rechaza_antes_de_tomar(self):
        codigo, datos = self.correr("despachar", "cotejo-gem", "--sin-aislar")
        self.assertNotEqual(codigo, 0)
        for trozo in (str(self.ruta), "hooks", "FatalUntrustedWorkspaceError"):
            self.assertIn(trozo, datos["error"])
        self.assertIn("- [ ] Con Gemini #agente/gemini-flash ^cotejo-gem", self.leer_nota("Uno.md"))
        self.assertIn("gemini_sin_confianza", [d.get("rechazo") for d in self.despachados()])

    def test_otro_cliente_sigue_lanzando(self):
        self.lanzar_vivo("cotejo-claude")
        self.soltar()
        self.assertIn("#en-curso #agente/sonnet ^cotejo-claude", self.leer_nota("Uno.md"))

    @staticmethod
    def _registro(tarea_id):
        from tareas import lanzados
        return lanzados.leer(tarea_id)
