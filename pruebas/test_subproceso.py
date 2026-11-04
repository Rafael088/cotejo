"""Ningún proceso del paquete abre consola en Windows (cotejo-gckm21).

Tres capas: el código (toda llamada a `subprocess` de `enrutador/` y `tareas/` pasa por
`enrutador/subproceso.py`), el helper (con `sys.platform` de Windows simulado pone
`CREATE_NO_WINDOW` y traduce `start_new_session`) y, en un Windows de verdad, que ni el hijo ni
el nieto (lo que lanza el hijo sin flags, un `.cmd`) tienen ventana de consola.
"""

import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import subproceso

RAIZ = Path(__file__).resolve().parent.parent
PAQUETES = ("enrutador", "tareas")
LANZADORES = {"run", "Popen", "call", "check_call", "check_output", "getoutput",
              "getstatusoutput"}
# `os.*` que lanzan procesos sin pasar por `subprocess` (y sin flags posibles).
OS_LANZADORES = {"system", "popen", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv",
                 "spawnve", "spawnvp", "spawnvpe", "startfile"}
# Corre suelto con `python -I -S` (no puede importar el helper): sus llamadas llevan el flag a
# mano, salvo el `git` que pide el agente, que escribe en la consola que hereda.
SUELTO = "enrutador/guarda_git.py"
SIN_FLAG_EN_SUELTO = {"call"}

# Lo que hace un proceso de Windows para decir si tiene consola y si esa consola tiene ventana.
CONSOLA = "import ctypes; k = ctypes.windll.kernel32; print(k.GetConsoleWindow(), k.GetConsoleCP())"


def _archivos():
    for paquete in PAQUETES:
        yield from sorted((RAIZ / paquete).rglob("*.py"))


def _llamadas_directas(arbol):
    """(línea, nombre, keywords) de cada `subprocess.X(...)`/`os.X(...)` que lanza algo, y de cada
    nombre importado de `subprocess` con `from subprocess import ...`."""
    importados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "subprocess":
            importados |= {a.asname or a.name for a in nodo.names if a.name in LANZADORES}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        claves = {k.arg for k in nodo.keywords}
        if isinstance(funcion, ast.Attribute) and isinstance(funcion.value, ast.Name):
            if funcion.value.id == "subprocess" and funcion.attr in LANZADORES:
                yield nodo.lineno, f"subprocess.{funcion.attr}", claves
            elif funcion.value.id == "os" and funcion.attr in OS_LANZADORES:
                yield nodo.lineno, f"os.{funcion.attr}", claves
        elif isinstance(funcion, ast.Name) and funcion.id in importados:
            yield nodo.lineno, funcion.id, claves


class TodoPasaPorElHelper(unittest.TestCase):

    def test_ninguna_llamada_directa_a_subprocess(self):
        malas = []
        for archivo in _archivos():
            relativo = archivo.relative_to(RAIZ).as_posix()
            if relativo == "enrutador/subproceso.py":
                continue
            arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=relativo)
            for linea, nombre, claves in _llamadas_directas(arbol):
                if relativo == SUELTO:
                    corto = nombre.split(".")[-1]
                    if "creationflags" in claves or corto in SIN_FLAG_EN_SUELTO:
                        continue
                malas.append(f"{relativo}:{linea} {nombre}(…)")
        self.assertEqual(malas, [], "En Windows abrirían una consola cada una: usa "
                                    "enrutador.subproceso (run, Popen, call, check_output).")

    def test_la_prueba_ve_una_llamada_directa(self):
        codigo = textwrap.dedent("""
            import subprocess, os
            from subprocess import Popen as P
            subprocess.run(["git"])
            P(["x"])
            os.system("x")
            subproceso.run(["git"])
        """)
        vistas = [n for _, n, _ in _llamadas_directas(ast.parse(codigo))]
        self.assertEqual(sorted(vistas), ["P", "os.system", "subprocess.run"])

    def test_el_suelto_lleva_el_flag_a_mano(self):
        texto = (RAIZ / SUELTO).read_text(encoding="utf-8")
        self.assertIn("CREATE_NO_WINDOW = 0x08000000", texto)
        self.assertEqual(subproceso.CREATE_NO_WINDOW, 0x08000000)


class ElHelper(unittest.TestCase):

    def en(self, plataforma):
        return mock.patch.object(subproceso.sys, "platform", plataforma)

    def test_en_windows_pone_create_no_window(self):
        with self.en("win32"):
            kwargs = subproceso.opciones({"stdin": subprocess.DEVNULL})
        self.assertEqual(kwargs["creationflags"], subproceso.CREATE_NO_WINDOW)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)

    def test_en_windows_start_new_session_es_un_grupo_propio(self):
        with self.en("win32"):
            kwargs = subproceso.opciones({"start_new_session": True})
        self.assertNotIn("start_new_session", kwargs)
        self.assertEqual(kwargs["creationflags"],
                         subproceso.CREATE_NO_WINDOW | subproceso.CREATE_NEW_PROCESS_GROUP)

    def test_en_windows_respeta_los_flags_que_ya_vienen(self):
        with self.en("win32"):
            kwargs = subproceso.opciones({"creationflags": 0x10, "start_new_session": False})
        self.assertEqual(kwargs["creationflags"], 0x10 | subproceso.CREATE_NO_WINDOW)
        self.assertNotIn("start_new_session", kwargs)

    def test_fuera_de_windows_no_toca_nada(self):
        for plataforma in ("linux", "darwin"):
            with self.en(plataforma):
                original = {"start_new_session": True, "text": True}
                self.assertEqual(subproceso.opciones(original), original)
                self.assertEqual(subproceso.opciones({}), {})

    def test_no_cambia_el_dict_de_quien_llama(self):
        original = {"start_new_session": True}
        with self.en("win32"):
            subproceso.opciones(original)
        self.assertEqual(original, {"start_new_session": True})

    def test_cada_lanzador_pasa_el_flag(self):
        for nombre in ("run", "Popen", "call", "check_call", "check_output"):
            with self.subTest(nombre), self.en("win32"), \
                    mock.patch.object(subprocess, nombre) as real:
                getattr(subproceso, nombre)(["git", "status"], cwd="x", start_new_session=True)
            real.assert_called_once_with(
                ["git", "status"], cwd="x",
                creationflags=subproceso.CREATE_NO_WINDOW | subproceso.CREATE_NEW_PROCESS_GROUP)

    def test_un_patch_de_subprocess_sigue_valiendo(self):
        # Las pruebas del resto del paquete parchean `subprocess.run`/`Popen`: el helper los
        # busca al llamar, no al importar.
        with mock.patch("subprocess.run", return_value="parcheado"):
            self.assertEqual(subproceso.run(["x"]), "parcheado")


@unittest.skipUnless(sys.platform == "win32", "solo en un Windows de verdad")
class EnWindows(unittest.TestCase):
    """Un proceso con CREATE_NO_WINDOW tiene consola sin ventana (GetConsoleWindow() == 0,
    GetConsoleCP() != 0), y lo que él lance sin flags la hereda en vez de abrir otra."""

    def consola(self, salida):
        ventana, pagina = salida.split()
        return int(ventana), int(pagina)

    def test_el_hijo_no_tiene_ventana(self):
        hecho = subproceso.run([sys.executable, "-c", CONSOLA], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60, start_new_session=True)
        ventana, pagina = self.consola(hecho.stdout)
        self.assertEqual(ventana, 0)
        self.assertNotEqual(pagina, 0)

    def test_el_nieto_tampoco(self):
        nieto = (f"import subprocess, sys; print(subprocess.run([sys.executable, '-c', {CONSOLA!r}],"
                 f" capture_output=True, text=True).stdout)")
        hecho = subproceso.run([sys.executable, "-c", nieto], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=60)
        ventana, pagina = self.consola(hecho.stdout)
        self.assertEqual(ventana, 0)
        self.assertNotEqual(pagina, 0)

    def test_un_cmd_tampoco(self):
        # Los clientes de npm son `.cmd`: los corre un cmd.exe, y lo que él lanza es el nieto.
        with tempfile.TemporaryDirectory() as carpeta:
            script = Path(carpeta) / "cliente.cmd"
            script.write_text(f'@"{sys.executable}" -c "{CONSOLA}"\r\n', encoding="utf-8")
            hecho = subproceso.run([str(script)], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=60)
        ventana, pagina = self.consola(hecho.stdout)
        self.assertEqual(ventana, 0)
        self.assertNotEqual(pagina, 0)


if __name__ == "__main__":
    unittest.main()
