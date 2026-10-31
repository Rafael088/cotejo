"""Revisar el equipo sin GTK (tareas/equipo.py): qué agentes y git hay, y adónde llevar si faltan."""

import os
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import clientes
from tareas import equipo
from tareas.fuentes.repo import Repo


def revisar(agentes, git=True, sin_sesion=(), sin_modelo=()):
    """Sin mirar la máquina: `agentes` instalados, todos con sesión salvo `sin_sesion`."""
    with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)), \
            mock.patch("enrutador.modelos_vivos.sesion", lambda n, **_: n not in sin_sesion), \
            mock.patch("enrutador.modelos_vivos.preguntar",
                       lambda n, *_a, **_k: [] if n in sin_modelo else None), \
            mock.patch("enrutador.modelos_vivos.en_cache",
                       lambda n: [] if n in sin_modelo else ["modelo"]), \
            mock.patch("tareas.instalar_agentes.sumar_al_path", return_value=[]), \
            mock.patch("tareas.instalar_agentes.instalado", return_value=False), \
            mock.patch("tareas.equipo.hay_git", return_value=git):
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
        self.assertEqual(e.titular, "Todo listo para empezar con Codex")
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


if __name__ == "__main__":
    unittest.main()
