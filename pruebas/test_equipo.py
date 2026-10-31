"""Revisar el equipo sin GTK (tareas/equipo.py): qué agentes y git hay, y adónde llevar si faltan."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import clientes
from tareas import equipo
from tareas.fuentes.repo import Repo


def revisar(agentes, git=True, sin_sesion=(), sin_modelo=(), empuja="helper"):
    """Sin mirar la máquina: `agentes` instalados, todos con sesión salvo `sin_sesion`; git
    empuja con `empuja` (None: sin credenciales)."""
    with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)), \
            mock.patch("enrutador.modelos_vivos.sesion", lambda n, **_: n not in sin_sesion), \
            mock.patch("enrutador.modelos_vivos.preguntar",
                       lambda n, *_a, **_k: [] if n in sin_modelo else None), \
            mock.patch("enrutador.modelos_vivos.en_cache",
                       lambda n: [] if n in sin_modelo else ["modelo"]), \
            mock.patch("tareas.instalar_agentes.sumar_al_path", return_value=[]), \
            mock.patch("tareas.instalar_agentes.instalado", return_value=False), \
            mock.patch("tareas.equipo.hay_git", return_value=git), \
            mock.patch("tareas.equipo.puede_empujar", return_value=empuja):
        return equipo.revisar(preguntar_cli=True)


class Equipo(unittest.TestCase):
    def test_con_todo_instalado(self):
        e = revisar(clientes.CLIENTES, git=True)
        self.assertTrue(all(p.listo for p in (*e.agentes, e.git)))
        self.assertEqual(e.faltan, ())
        self.assertTrue(e.hay_agente)
        self.assertEqual(e.titular, "Todo listo: tienes 5 agentes")

    def test_sin_nada_marca_todo_y_manda_a_las_paginas_oficiales(self):
        e = revisar([], git=False)
        self.assertEqual([p.clave for p in e.agentes], list(clientes.CLIENTES))
        self.assertFalse(e.hay_agente)
        self.assertEqual(len(e.faltan), 6)                # cinco agentes y git
        self.assertEqual(e.titular, "Te falta un agente de IA")
        self.assertIn("Instalar", e.mensaje)
        self.assertEqual([a.clave for a in e.agentes if a.recomendado], ["claude"])
        for p in e.piezas:
            self.assertEqual(p.estado, "No instalado")
            self.assertTrue(p.pagina.startswith("https://"), p.clave)
        self.assertEqual(e.git.titulo, equipo.TITULO_GIT)
        self.assertEqual(e.git.texto_enlace, "Cómo instalar git")

    def test_algunos(self):
        e = revisar(["codex"], git=False)
        self.assertEqual({p.clave for p in e.piezas if p.listo}, {"codex"})
        self.assertEqual(e.titular, "Casi listo: falta git")
        self.assertIn("git", e.mensaje)
        self.assertEqual([p.clave for p in e.faltan],
                         ["claude", "opencode", "gemini", "antigravity", "git"])

    def test_tres_estados_por_agente(self):
        e = revisar(["claude", "codex"], git=True, sin_sesion={"codex"})
        estados = {p.clave: p.estado for p in e.agentes}
        self.assertEqual(estados, {"claude": "Listo", "codex": "Falta iniciar sesión",
                                   "opencode": "No instalado", "gemini": "No instalado",
                                   "antigravity": "No instalado"})
        self.assertEqual(e.titular, "Todo listo para empezar con Claude Code")
        self.assertFalse(any(p.recomendado for p in e.agentes))

    def test_instalado_sin_sesion_no_cuenta_como_listo(self):
        e = revisar(["opencode"], sin_sesion={"opencode"})
        self.assertFalse(e.hay_agente)
        self.assertTrue(e.hay_instalado)
        self.assertEqual(e.titular, "Te falta iniciar sesión en OpenCode")
        self.assertIn("navegador", e.mensaje)

    def test_con_sesion_pero_sin_modelo_dice_como_arreglarlo(self):
        e = revisar(["opencode"], sin_modelo={"opencode"})
        opencode = next(p for p in e.agentes if p.clave == "opencode")
        self.assertEqual(opencode.estado, "Falta elegir modelo")
        self.assertFalse(opencode.listo)
        self.assertIn("configura un proveedor y un modelo", opencode.nota)

    def test_gemini_solo_enlaza_y_manda_a_antigravity(self):
        e = revisar([])
        gemini = next(p for p in e.agentes if p.clave == "gemini")
        self.assertFalse(gemini.instalable)
        self.assertIn("Solo con licencia de empresa", gemini.nota)
        self.assertIn("Antigravity CLI", gemini.nota)
        agy = next(p for p in e.agentes if p.clave == "antigravity")
        self.assertEqual((agy.titulo, agy.estado), ("Antigravity CLI", "No instalado"))
        self.assertTrue(agy.instalable)
        self.assertTrue(agy.pagina.startswith("https://antigravity.google/"))

    def test_antigravity_instalado_cuenta_para_tareas_sin_ver_su_sesion(self):
        # Su sesión vive en el llavero y no hay cómo preguntarla (cotejo-r4yg0n): instalado
        # cuenta como listo, dice «Instalado» (no «Listo») y no pide iniciar sesión.
        e = revisar(["antigravity"], sin_sesion={"antigravity"})
        agy = next(p for p in e.agentes if p.clave == "antigravity")
        self.assertEqual(agy.estado, "Instalado")
        self.assertTrue(agy.listo and agy.sesion_desconocida)
        self.assertFalse(agy.pide_sesion)
        self.assertIn("no puede ver si ya entraste", agy.nota)
        self.assertTrue(e.hay_agente)
        self.assertEqual(e.titular, "Todo listo para empezar con Antigravity CLI")

    def test_antigravity_con_sesion_por_entorno_dice_listo(self):
        e = revisar(["antigravity"])
        agy = next(p for p in e.agentes if p.clave == "antigravity")
        self.assertEqual(agy.estado, "Listo")
        self.assertFalse(agy.sesion_desconocida)

    def test_cada_revision_vuelve_a_detectar(self):
        self.assertFalse(revisar([]).hay_agente)
        self.assertTrue(revisar(["claude"]).hay_agente)

    def test_las_paginas_cubren_todos_los_clientes(self):
        for nombre in clientes.CLIENTES:
            self.assertIn(nombre, equipo.PAGINAS)

    def test_primer_arranque_es_una_fuente_de_repos_sin_ninguno(self):
        with mock.patch.dict("os.environ"):
            for var in ("COTEJO_REPOS", "COTEJO_RAIZ_REPOS"):
                os.environ.pop(var, None)
            self.assertTrue(equipo.es_primer_arranque(Repo({})))
            roto = Repo({"repos": ["/no/existe/de/verdad"]})
            self.assertIsNotNone(roto.problema)
            self.assertFalse(equipo.es_primer_arranque(roto))



class GitPuedeEmpujar(unittest.TestCase):
    """Git solo está listo si guardar un cambio no va a pedir usuario y contraseña
    (cotejo-vz6v3c): helper de credenciales, gh con sesión o llave SSH."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.casa = Path(temporal.name)
        self.entorno = {"HOME": str(self.casa), "GIT_CONFIG_SYSTEM": str(self.casa / "no-hay")}

    def empuja(self):
        return equipo.puede_empujar(self.casa, self.entorno)

    def gitconfig(self, texto, donde=".gitconfig"):
        archivo = self.casa / donde
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")

    def gh_con_cuenta(self):
        self.gitconfig("github.com:\n    user: alguien\n    git_protocol: https\n",
                       ".config/gh/hosts.yml")

    def test_sin_nada_no_puede(self):
        self.gitconfig("[user]\n\tname = Alguien\n\temail = a@b.c\n")
        self.assertIsNone(self.empuja())

    def test_un_helper_cualquiera_basta(self):
        self.gitconfig("[credential]\n\thelper = libsecret\n")
        self.assertEqual(self.empuja(), "helper")

    def test_el_helper_por_url_tambien_y_en_la_config_de_xdg(self):
        self.gitconfig('[credential "https://github.com"]\n\thelper = osxkeychain\n',
                       ".config/git/config")
        self.assertEqual(self.empuja(), "helper")

    def test_el_helper_de_gh_solo_cuenta_con_gh_con_sesion(self):
        self.gitconfig('[credential "https://github.com"]\n\thelper =\n'
                       '\thelper = !/usr/bin/gh auth git-credential\n')
        self.assertIsNone(self.empuja())
        self.gh_con_cuenta()
        self.assertEqual(self.empuja(), "helper")

    def test_un_helper_vacio_borra_los_de_antes_y_los_comentarios_no_cuentan(self):
        self.gitconfig("[credential]\n\thelper = cache\n\thelper =\n"
                       "# helper = store\n[otra]\n\thelper = x\n")
        self.assertIsNone(self.empuja())

    def test_una_llave_ssh(self):
        (self.casa / ".ssh").mkdir()
        (self.casa / ".ssh" / "known_hosts").write_text("", encoding="utf-8")
        self.assertIsNone(self.empuja())
        (self.casa / ".ssh" / "id_ed25519").write_text("x", encoding="utf-8")
        self.assertEqual(self.empuja(), "ssh")

    def test_gh_sin_hosts_no_tiene_sesion_y_con_token_en_el_entorno_si(self):
        self.assertFalse(equipo.gh_con_sesion(self.casa, self.entorno))
        self.assertTrue(equipo.gh_con_sesion(self.casa, {**self.entorno, "GH_TOKEN": "t"}))
        self.gh_con_cuenta()
        self.assertTrue(equipo.gh_con_sesion(self.casa, self.entorno))

    def test_instalado_sin_credenciales_no_promete_listo(self):
        e = revisar(["claude"], git=True, empuja=None)
        self.assertEqual(e.git.estado, "Falta conectar")
        self.assertFalse(e.git.listo)
        self.assertTrue(e.git.pide_sesion)
        self.assertIn("usuario y contraseña", e.git.nota)
        self.assertIn("nunca guarda tu contraseña", e.git.nota)
        self.assertEqual(e.titular, "Casi listo: falta conectar git para guardar tus cambios")
        self.assertNotIn("listo", e.titular.replace("Casi listo", ""))
        self.assertIn("Conectar", e.mensaje)
        self.assertIn(e.git, e.faltan)

    def test_con_credenciales_si_esta_listo(self):
        for como in ("helper", "ssh"):
            e = revisar(["claude"], git=True, empuja=como)
            self.assertEqual(e.git.estado, "Listo")
            self.assertEqual(e.titular, "Todo listo para empezar con Claude Code")

    def test_sin_git_no_mira_credenciales(self):
        e = revisar(["claude"], git=False, empuja=None)
        self.assertEqual(e.git.estado, "No instalado")
        self.assertFalse(e.git.pide_sesion)


if __name__ == "__main__":
    unittest.main()
