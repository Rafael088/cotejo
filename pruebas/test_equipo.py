"""Revisar el equipo sin GTK (tareas/equipo.py): qué agentes y git hay, y adónde llevar si faltan."""

import os
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import clientes
from tareas import equipo
from tareas.fuentes.repo import Repo


def revisar(agentes, git=True, sin_sesion=()):
    """Sin mirar la máquina: `agentes` instalados, todos con sesión salvo `sin_sesion`."""
    with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)), \
            mock.patch("enrutador.modelos_vivos.sesion", lambda n: n not in sin_sesion), \
            mock.patch("tareas.instalar_agentes.sumar_al_path", return_value=[]), \
            mock.patch("tareas.equipo.hay_git", return_value=git):
        return equipo.revisar()


class Equipo(unittest.TestCase):
    def test_con_todo_instalado(self):
        e = revisar(clientes.CLIENTES, git=True)
        self.assertTrue(all(p.listo for p in e.piezas))
        self.assertEqual(e.faltan, ())
        self.assertTrue(e.hay_agente)
        self.assertEqual(e.titular, "Todo listo: tienes 4 agentes")

    def test_sin_nada_marca_todo_y_manda_a_las_paginas_oficiales(self):
        e = revisar([], git=False)
        self.assertEqual([p.clave for p in e.agentes], list(clientes.CLIENTES))
        self.assertFalse(e.hay_agente)
        self.assertEqual(len(e.faltan), 5)
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
        self.assertEqual([p.clave for p in e.faltan], ["claude", "opencode", "gemini", "git"])

    def test_tres_estados_por_agente(self):
        e = revisar(["claude", "codex"], git=True, sin_sesion={"codex"})
        estados = {p.clave: p.estado for p in e.agentes}
        self.assertEqual(estados, {"claude": "Listo", "codex": "Falta iniciar sesión",
                                   "opencode": "No instalado", "gemini": "No instalado"})
        self.assertEqual(e.titular, "Todo listo para empezar con Claude Code")
        self.assertFalse(any(p.recomendado for p in e.agentes))

    def test_instalado_sin_sesion_no_cuenta_como_listo(self):
        e = revisar(["opencode"], sin_sesion={"opencode"})
        self.assertFalse(e.hay_agente)
        self.assertTrue(e.hay_instalado)
        self.assertEqual(e.titular, "Te falta iniciar sesión en OpenCode")
        self.assertIn("navegador", e.mensaje)

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
