"""Inicio de un proyecto de punta a punta (v1.2.4 B.4): carpeta que no existe → `init` → lo que
pide la skill de inicio → `contexto`.

«El agente» va guionizado con los mismos verbos y en el mismo orden que
`skills/cotejo/referencias/inicio.md`. Todo corre en un proceso aparte con HOME y XDG_* en un tmp,
sin red y sin tocar la config ni el vault reales.

Tope de tokens: se usa `medir.py` (skill `ax`) si está en esta máquina; si no, la misma
estimación que hace él, ~4 caracteres por token, así la prueba vale en CI.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

MEDIR = Path.home() / ".claude" / "skills" / "ax" / "scripts" / "medir.py"
POR_TOKEN = 4
TOPE_TOKENS = 1000


def tokens_de(texto):
    if MEDIR.is_file():
        try:
            espec = importlib.util.spec_from_file_location("medir_ax", MEDIR)
            modulo = importlib.util.module_from_spec(espec)
            espec.loader.exec_module(modulo)
            return modulo.tokens(len(texto))
        except Exception:
            pass
    return round(len(texto) / POR_TOKEN)


class InicioDePuntaAPunta(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        base = Path(temporal.name)
        self.casa = base / "casa"
        self.casa.mkdir()
        self.carpeta = base / "proyectos" / "lista-compra"  # todavía no existe
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("COTEJO_", "FOCO_"))}
        self.env.update(HOME=str(self.casa), XDG_CONFIG_HOME=str(base / "config"),
                        XDG_STATE_HOME=str(base / "estado"), XDG_DATA_HOME=str(base / "datos"),
                        PYTHONPATH=str(RAIZ))

    def cotejo(self, *args):
        hecho = subprocess.run([sys.executable, "-m", "tareas", *args], cwd=self.casa,
                               env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(hecho.returncode, 0, f"{args}: {hecho.stderr}{hecho.stdout}")
        return hecho.stdout

    def json(self, *args):
        return json.loads(self.cotejo(*args))

    def test_de_carpeta_vacia_a_contexto(self):
        repo = str(self.carpeta)
        self.assertFalse(self.carpeta.exists())
        iniciado = self.json("init", "--repo", repo)
        self.assertTrue(iniciado["git_init"])
        self.assertEqual(iniciado["version"]["version"], "0.1.0")
        self.assertEqual(self.json("fuentes", "usar", "repo")["activa"], "repo")

        # Lo que escribe el agente tras entrevistar (inicio.md, §3).
        hash_ = self.json("leer", "proyecto", "--repo", repo)["version"]
        self.json("editar", "proyecto", "--repo", repo, "--version", hash_, "--texto",
                  "## Objetivo\nApp de lista de la compra compartida para una pareja.\n"
                  "## Stack\nPython y SQLite, interfaz web mínima.\n"
                  "## Siguiente paso\nModelo de datos de la lista.")
        propuestas = [self.json("proponer", "decision", "--repo", repo, "--titulo", titulo,
                                "--temas", temas, "--texto", texto)["id"]
                      for titulo, temas, texto in (
                          ("SQLite como almacén", "stack,datos", "Un archivo local basta."),
                          ("Sin cuentas en la 0.1.0", "alcance", "Se comparte por enlace."))]
        self.json("anotar", "arquitectura", "--repo", repo, "--titulo", "Arquitectura inicial",
                  "--temas", "arquitectura", "--texto", "Servidor web que habla con SQLite.")
        for tarea in ("Modelo de datos: tabla de artículos", "API: añadir y tachar artículos",
                      "Pantalla de la lista", "Crear el dominio y decidir el nombre"):
            self.json("crear", tarea, "--proyecto", "lista-compra", "--version", "0.1.0")

        # Comprobar (inicio.md, §4).
        bruto = self.cotejo("contexto", "--repo", repo)
        datos = json.loads(bruto)
        self.assertIn("lista de la compra", datos["proyecto"]["objetivo"])
        self.assertEqual(datos["proyecto"]["siguiente_paso"], "Modelo de datos de la lista.")
        self.assertEqual(datos["version"], "0.1.0")
        self.assertCountEqual(datos["decisiones_propuestas"], propuestas)
        self.assertEqual(datos["decisiones_vigentes_total"], 2)
        self.assertEqual(datos["tareas"]["pendiente"], 4)
        n = tokens_de(bruto)
        self.assertLess(n, TOPE_TOKENS, f"contexto = {n} tokens")

        en_curso = self.json("version", "--proyecto", "lista-compra")
        self.assertEqual(en_curso["en_curso"], "0.1.0")
        self.assertEqual(en_curso["tareas"]["pendiente"], 4)


if __name__ == "__main__":
    unittest.main()
