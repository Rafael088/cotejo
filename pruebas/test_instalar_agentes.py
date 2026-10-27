"""Instalar y conectar agentes sin GTK (tareas/instalar_agentes.py, cotejo-2j6un7).

Nada de esto descarga ni instala nada de verdad: `descargar` se sustituye por uno que escribe un
instalador falso, los CLIs son scripts en un PATH temporal y HOME y el estado de Cotejo viven en
una carpeta que muere con cada prueba. No depende de qué agentes tenga la máquina ni de la red.
"""

import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import equipo, instalar_agentes as inst

# Lo único del sistema que ven los instaladores y CLIs falsos: nada de terminales ni agentes.
HERRAMIENTAS = ("sh", "bash", "mkdir", "chmod", "sleep", "cat")


def ejecutable(ruta, texto):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    ruta.chmod(ruta.stat().st_mode | stat.S_IXUSR)
    return ruta


class Base(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.casa = self.raiz / "casa"
        self.bin = self.raiz / "bin"
        self.casa.mkdir()
        self.bin.mkdir()
        sistema = self.raiz / "sistema"
        sistema.mkdir()
        for nombre in HERRAMIENTAS:
            real = shutil.which(nombre)
            if real:
                (sistema / nombre).symlink_to(real)
        entorno = mock.patch.dict(os.environ, {
            "HOME": str(self.casa), "COTEJO_ESTADO": str(self.raiz / "estado"),
            "COTEJO_CONFIG": str(self.raiz / "config.json"),
            "XDG_DATA_HOME": str(self.casa / ".local" / "share"),
            "PATH": f"{self.bin}:{sistema}"})
        entorno.start()
        self.addCleanup(entorno.stop)
        for var in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY",
                    "CODEX_HOME", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            os.environ.pop(var, None)

    def con_instalador(self, texto):
        """`descargar` escribe este script en vez de bajar el oficial."""
        def falso(url, destino, tope=None):
            self.descargado = url
            destino.write_text(texto, encoding="utf-8")
        parche = mock.patch.object(inst, "descargar", side_effect=falso)
        parche.start()
        self.addCleanup(parche.stop)


class Instaladores(unittest.TestCase):
    def test_solo_los_oficiales_por_https_y_con_su_fuente(self):
        self.assertEqual(inst.INSTALADORES["claude"].url, "https://claude.ai/install.sh")
        self.assertEqual(inst.INSTALADORES["codex"].url, "https://chatgpt.com/codex/install.sh")
        self.assertEqual(inst.INSTALADORES["opencode"].url, "https://opencode.ai/install")
        self.assertEqual(inst.INSTALADORES["codex"].interprete, "sh")
        self.assertNotIn("gemini", inst.INSTALADORES)
        self.assertEqual(inst.INSTALADORES["antigravity"].url,
                         "https://antigravity.google/cli/install.sh")
        self.assertEqual(inst.INSTALADORES["antigravity"].interprete, "bash")
        for clave, i in inst.INSTALADORES.items():
            self.assertTrue(i.url.startswith("https://"), clave)
            self.assertTrue(i.fuente.startswith("https://"), clave)
            self.assertNotIn("sudo", i.url + i.interprete)
        for clave, s in inst.SESIONES.items():
            self.assertTrue(s.fuente.startswith("https://"), clave)

    def test_logins_oficiales(self):
        self.assertEqual(inst.texto_para_copiar("claude"), "claude auth login")
        self.assertEqual(inst.texto_para_copiar("codex"), "codex login")
        self.assertEqual(inst.texto_para_copiar("opencode"), "opencode auth login")
        self.assertEqual(inst.texto_para_copiar("gemini"), "gemini")
        self.assertEqual(inst.texto_para_copiar("antigravity"), "agy")
        self.assertFalse(inst.SESIONES["codex"].en_terminal)

    def test_descargar_solo_https(self):
        with self.assertRaises(OSError):
            inst.descargar("http://ejemplo.org/x.sh", Path("/nunca"))


class Instalar(Base):
    def test_corre_el_instalador_y_cuenta_lo_que_dice(self):
        self.con_instalador(
            "echo 'Bajando Claude Code…'\n"
            "mkdir -p \"$HOME/.local/bin\"\n"
            "printf '#!/bin/sh\\necho 9.9\\n' > \"$HOME/.local/bin/claude\"\n"
            "chmod +x \"$HOME/.local/bin/claude\"\n"
            "printf '\\033[32mInstalación completa\\033[0m\\n'\n")
        vistas, fin = [], []
        t = inst.instalar("claude", al_linea=lambda t, l: vistas.append(l),
                          al_terminar=fin.append)
        self.assertEqual(t.esperar(10), "hecho")
        self.assertEqual(self.descargado, "https://claude.ai/install.sh")
        self.assertEqual(fin, [t])
        self.assertIn("Bajando Claude Code…", vistas)
        self.assertIn("Instalación completa", vistas)   # sin los colores de la terminal
        self.assertIn("Instalación completa", t.log.read_text(encoding="utf-8"))
        self.assertEqual(t.log.parent, Path(os.environ["COTEJO_ESTADO"]) / "agentes")
        # Lo instalado en ~/.local/bin se ve aunque esa carpeta no estuviera en el PATH.
        self.assertEqual(inst.sumar_al_path(), [str(self.casa / ".local" / "bin")])
        self.assertEqual(inst.sumar_al_path(), [])
        self.assertIn("instalado", inst.resultado(t, True))

    def test_codex_sin_preguntas(self):
        self.con_instalador('echo "sin preguntas=$CODEX_NON_INTERACTIVE"\n')
        t = inst.instalar("codex")
        self.assertEqual(t.esperar(10), "hecho")
        self.assertIn("sin preguntas=1", t.lineas)

    def test_nunca_sube_privilegios(self):
        self.con_instalador("echo 'necesito permisos'\nsudo mkdir /opt/agente || exit 3\n")
        t = inst.instalar("opencode")
        self.assertEqual(t.esperar(10), "sin_permisos")
        self.assertFalse(any(inst.MARCA_SIN_PERMISOS in l for l in t.lineas))
        dicho = inst.resultado(t, False)
        self.assertIn("sudo", dicho)
        self.assertIn("https://opencode.ai/docs/", dicho)

    def test_falla_y_dice_donde_esta_el_registro(self):
        self.con_instalador("echo 'algo salió mal' >&2\nexit 4\n")
        t = inst.instalar("claude")
        self.assertEqual(t.esperar(10), "fallo")
        self.assertEqual(t.codigo, 4)
        self.assertIn("algo salió mal", t.lineas)
        self.assertIn("código 4", inst.resultado(t, False))

    def test_termino_pero_no_aparece(self):
        self.con_instalador("echo hecho\n")
        t = inst.instalar("claude")
        self.assertEqual(t.esperar(10), "hecho")
        self.assertIn("no encuentro", inst.resultado(t, False))

    def test_se_puede_cancelar(self):
        self.con_instalador("echo empiezo\nsleep 30\necho nunca\n")
        t = inst.instalar("claude")
        self.assertTrue(_hasta(lambda: "empiezo" in t.lineas))
        t.cancelar()
        self.assertEqual(t.esperar(10), "cancelado")
        self.assertNotIn("nunca", t.lineas)
        self.assertIn("Cancelado", inst.resultado(t))

    def test_tiene_tope(self):
        self.con_instalador("sleep 30\n")
        t = inst.instalar("claude", tope=1)
        self.assertEqual(t.esperar(10), "tarde")

    def test_sin_red(self):
        with mock.patch.object(inst, "descargar", side_effect=OSError("sin red")):
            t = inst.instalar("claude")
            self.assertEqual(t.esperar(10), "sin_descarga")
        self.assertIn("internet", inst.resultado(t))

    def test_una_pagina_web_no_es_un_instalador(self):
        self.con_instalador("<!doctype html><html>403</html>\n")
        t = inst.instalar("claude")
        self.assertEqual(t.esperar(10), "sin_descarga")

    def test_gemini_no_se_instala_aqui(self):
        self.assertFalse(inst.puede_instalar("gemini"))

    def test_en_windows_solo_enlaza(self):
        with mock.patch("tareas.rutas.sistema", return_value="windows"):
            self.assertFalse(inst.puede_instalar("claude"))


class Antigravity(Base):
    def test_se_instala_con_su_oficial_y_queda_en_local_bin(self):
        self.con_instalador(
            "mkdir -p \"$HOME/.local/bin\"\n"
            "printf '#!/bin/sh\\n' > \"$HOME/.local/bin/agy\"\n"
            "chmod +x \"$HOME/.local/bin/agy\"\n")
        t = inst.instalar("antigravity")
        self.assertEqual(t.esperar(10), "hecho")
        self.assertEqual(self.descargado, "https://antigravity.google/cli/install.sh")
        self.assertIn("Antigravity CLI quedó instalado", inst.resultado(t, True))
        e = equipo.revisar()
        self.assertEqual(e.aparte[0].estado, equipo.INSTALADO)

    def test_abrir_es_agy_en_una_terminal(self):
        agy = ejecutable(self.bin / "agy", "#!/bin/sh\n")
        abrir = mock.Mock()
        with mock.patch.object(inst, "terminal", return_value=["mi-terminal"]):
            a = inst.iniciar_sesion("antigravity", abrir=abrir)
        self.assertEqual(a.como, "terminal")
        abrir.assert_called_once_with(["mi-terminal", str(agy)])


class IniciarSesion(Base):
    def test_codex_en_segundo_plano_con_su_salida(self):
        ejecutable(self.bin / "codex",
                   "#!/bin/sh\necho \"Abre http://localhost:1455/auth ($*)\"\n"
                   "mkdir -p \"$HOME/.codex\" && echo '{}' > \"$HOME/.codex/auth.json\"\n")
        abrir = mock.Mock()
        a = inst.iniciar_sesion("codex", abrir=abrir)
        self.assertEqual(a.como, "fondo")
        self.assertEqual(a.trabajo.esperar(10), "hecho")
        self.assertIn("Abre http://localhost:1455/auth (login)", a.trabajo.lineas)
        abrir.assert_not_called()
        from enrutador import modelos_vivos
        self.assertTrue(modelos_vivos.sesion("codex"))

    def test_claude_en_una_terminal(self):
        claude = ejecutable(self.bin / "claude", "#!/bin/sh\n")
        abrir = mock.Mock()
        with mock.patch.object(inst, "terminal", return_value=["mi-terminal", "-e"]):
            a = inst.iniciar_sesion("claude", abrir=abrir)
        self.assertEqual(a.como, "terminal")
        abrir.assert_called_once_with(["mi-terminal", "-e", str(claude), "auth", "login"])

    def test_sin_terminal_se_copia_el_comando(self):
        ejecutable(self.bin / "opencode", "#!/bin/sh\n")
        with mock.patch.object(inst, "terminal", return_value=None):
            a = inst.iniciar_sesion("opencode", abrir=mock.Mock())
        self.assertEqual((a.como, a.comando), ("copiar", "opencode auth login"))

    def test_la_terminal_es_la_del_sistema_sin_inventar(self):
        self.assertIsNone(inst.terminal())
        ejecutable(self.bin / "x-terminal-emulator", "#!/bin/sh\n")
        self.assertEqual(inst.terminal(), ["x-terminal-emulator", "-e"])
        ejecutable(self.bin / "xdg-terminal-exec", "#!/bin/sh\n")
        self.assertEqual(inst.terminal(), ["xdg-terminal-exec"])


class EstadosDelEquipo(Base):
    def test_sin_ningun_agente_recomienda_uno(self):
        e = equipo.revisar()
        self.assertFalse(e.hay_instalado)
        claude = e.agentes[0]
        self.assertEqual((claude.clave, claude.estado), ("claude", equipo.NO_INSTALADO))
        self.assertTrue(claude.recomendado and claude.instalable)
        self.assertIn("empieza por este", claude.nota)
        self.assertEqual([a.clave for a in e.agentes if a.recomendado], ["claude"])
        gemini = next(a for a in e.agentes if a.clave == "gemini")
        self.assertFalse(gemini.instalable)
        self.assertIn("licencia de empresa", gemini.nota)
        self.assertTrue(e.aparte[0].instalable)
        self.assertIn("Instalar", e.mensaje)

    def test_instalado_sin_sesion_y_despues_listo(self):
        ejecutable(self.casa / ".local" / "bin" / "codex", "#!/bin/sh\n")
        e = equipo.revisar()          # lo encuentra aunque ~/.local/bin no estuviera en el PATH
        codex = next(a for a in e.agentes if a.clave == "codex")
        self.assertEqual(codex.estado, equipo.SIN_SESION)
        self.assertTrue(codex.pide_sesion)
        self.assertEqual(e.titular, "Te falta iniciar sesión en Codex")
        self.assertIn("Iniciar sesión", e.mensaje)
        self.assertFalse(any(a.recomendado for a in e.agentes))
        (self.casa / ".codex").mkdir()
        (self.casa / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
        e = equipo.revisar()
        self.assertEqual(next(a for a in e.agentes if a.clave == "codex").estado, equipo.LISTO)
        self.assertEqual(e.titular, "Todo listo para empezar con Codex")


def _hasta(condicion, tope=5.0):
    import time
    limite = time.monotonic() + tope
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return condicion()


if __name__ == "__main__":
    unittest.main()
