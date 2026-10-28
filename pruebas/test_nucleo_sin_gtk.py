"""El núcleo de Cotejo corre sin GTK: cada verbo de la CLI, en un Python que no puede importarlo.

Es la condición para empaquetar la CLI sola (una máquina sin escritorio, un agente en un
servidor) y la frontera que separa `cotejo` de `cotejoboard` (ver `tareas/board.py`). Hasta ahora
se sostenía por disciplina y por una lista de verbos en `__main__`; esta prueba es la que se
pone roja si alguien, por el camino de la CLI, importa `gi` o `tareas.app`.

Cada verbo corre en un subproceso nuevo porque dentro de este no se puede probar: otras
pruebas importan `tareas.app` (y con él `gi`) y el módulo ya estaría cargado. En el
subproceso un buscador al frente de `sys.meta_path` contesta a `import gi` lo mismo que un
Python sin PyGObject (`ModuleNotFoundError`) y además lo apunta: así se ve también el intento
que alguien envuelva en un `try/except ImportError` para disimularlo. (Tapar con
`sys.modules["gi"] = None` no bastaría: ese atajo falla antes de consultar a ningún buscador
y el intento no quedaría apuntado.)

Todo pasa en un vault, un HOME y un XDG de mentira: nada toca el vault ni el estado reales.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ, proyecto

# Lo que corre dentro del subproceso. Imprime una marca en stderr si algo intentó cargar la
# interfaz, y sale con 99 para que no pase desapercibido aunque el verbo haya ido bien.
VIGIA = r"""
import atexit, os, sys
intentos = []

class Vigia:
    def find_spec(self, nombre, ruta=None, objetivo=None):
        if nombre == "tareas.app":
            intentos.append(nombre)
        if nombre == "gi" or nombre.startswith("gi."):
            intentos.append(nombre)
            raise ModuleNotFoundError("No module named %r" % nombre, name=nombre)
        return None

sys.modules.pop("gi", None)
sys.meta_path.insert(0, Vigia())

def al_salir():
    cargados = [m for m in sys.modules if m == "tareas.app" or m.startswith("gi.")]
    if intentos or cargados:
        sys.stderr.write("CARGÓ LA INTERFAZ: %s\n" % sorted(set(intentos + cargados)))
        sys.stderr.flush()
        os._exit(99)

atexit.register(al_salir)
import runpy
sys.argv = ["cotejo"] + sys.argv[1:]
runpy.run_module("tareas", run_name="__main__", alter_sys=True)
"""

# Todos los verbos, en el orden en que tienen sentido: los que escriben dejan la tarea como
# la necesita el siguiente. `{id}` y `{id2}` son tareas que crea la propia secuencia.
# Un verbo nuevo en `cli.analizador()` sin fila aquí pone roja `test_no_falta_ningun_verbo`.
INVOCACIONES = [
    ("-h",),
    ("--estado",),
    ("estado",),
    ("tareas",),
    ("tareas", "--proyecto", "Uno", "--estado", "pendiente"),
    ("crear", "Probar el núcleo sin GTK", "--proyecto", "Uno"),
    ("tomar", "{id}", "--agente", "prueba"),
    ("entregar", "{id}", "--evidencia", "la prueba del núcleo"),
    ("comprobar", "{id}"),
    ("worktrees",),
    ("worktrees", "--limpiar"),
    ("asignar", "{id}", "sonnet"),
    ("asignar", "{id}"),
    ("limpiar", "Uno"),
    ("limpiar", "Uno", "--aplicar"),
    ("ahorro",),
    ("crear", "Otra para bloquear y despachar", "--proyecto", "Uno"),
    ("tomar", "{id2}", "--agente", "prueba"),
    ("bloquear", "{id2}", "--motivo", "para probar el camino"),
    ("asignar", "{id2}", "sonnet"),
    ("maestro", "--proyecto", "Uno", "--simular"),
    ("maestro", "--clientes"),
    ("modelos",),
    ("modelos", "agregar", "--clave", "prueba", "--modelo-id", "cliente/prueba",
     "--cliente", "opencode"),
    ("modelos", "quitar", "prueba"),
    ("modelos", "vivos", "--sin-preguntar"),
    ("decidir", "arreglar", "un", "typo"),
    ("decidir", "--tarea", "{id2}"),
    ("plan", "--proyecto", "Uno"),
    ("importar", "plan", "{plan}", "--proyecto", "Uno"),
    ("importar", "plan", "{plan}", "--proyecto", "Uno", "--aplicar"),
    ("importar", "obsidian", "Uno", "--destino", "{repo_init}"),
    ("fuentes", "agregar", "notion", "--comando", "{notion_cmd}"),
    ("importar", "notion", "Uno", "--destino", "{repo_init}"),
    ("despachar", "{id2}", "--simular", "--modelo", "sonnet"),
    ("despachar", "{id2}", "--motor", "simulado", "--modelo", "sonnet"),
    ("evaluar",),
    ("revisar",),
    ("capacidad", "--proyecto", "Uno"),
    ("despachos",),
    ("config",),
    ("config", "validar"),
    ("config", "init"),
    ("init", "--repo", "{repo_init}"),
    ("buscar", "--repo", "{repo_init}"),
    ("leer", "proyecto", "--repo", "{repo_init}"),
    ("contexto", "--repo", "{repo_init}"),
    ("editar", "proyecto", "--repo", "{repo_init}", "--version", "{version_proyecto}",
     "--texto", "Editado para que quede una fila en INVOCACIONES."),
    ("proponer", "decision", "--repo", "{repo_init}", "--titulo", "Probar el núcleo sin GTK",
     "--texto", "Para que quede una fila en INVOCACIONES."),
    ("anotar", "problema", "--repo", "{repo_init}", "--titulo", "Probar el núcleo sin GTK",
     "--texto", "Para que quede una fila en INVOCACIONES."),
    ("resolver", "{pro_id}", "--repo", "{repo_init}",
     "--solucion", "Resuelto para que quede una fila en INVOCACIONES."),
    ("anotar", "aprendizaje", "--repo", "{repo_init}", "--titulo", "Probar el núcleo sin GTK",
     "--texto", "Para que quede una fila en INVOCACIONES."),
    ("anotar", "referencia", "--repo", "{repo_init}", "--titulo", "Probar el núcleo sin GTK",
     "--texto", "Para que quede una fila en INVOCACIONES."),
    ("anotar", "arquitectura", "--repo", "{repo_init}", "--titulo", "Probar el núcleo sin GTK",
     "--texto", "Para que quede una fila en INVOCACIONES."),
    ("bitacora", "Probé el núcleo sin GTK.", "--repo", "{repo_init}"),
    ("version",),
    ("release",),
    ("protocolo",),
    ("doctor",),
    ("fuentes",),
    ("fuentes", "info", "obsidian"),
    ("fuentes", "probar", "obsidian"),
    ("fuentes", "usar", "obsidian"),
    ("fuentes", "agregar", "falsa", "--comando", "/bin/false"),
    ("fuentes", "quitar", "falsa"),
    ("temas",),
    ("temas", "comprobar", "oscuro"),
    ("temas", "nuevo", "mio"),
    ("temas", "usar", "mio"),
    ("mcp",),
    ("mcp", "--perfil", "nucleo"),
    ("mcp", "--perfil", "completo"),
]

# Los que miran «el repo donde estás» corren dentro del de la propia prueba (en la 0.1.0 desde
# `init`) y no en el checkout de Cotejo: la CI clona sin etiquetas, y sin ellas el checkout no
# tiene versión publicada ni en curso.
EN_REPO_INIT = {"version", "release"}

# Lo que se le escribe por stdin a cada invocación: nada, salvo al servidor MCP, que recibe una
# conversación corta y llama a una tool —que es el camino que tiene que seguir sin GTK—.
ENTRADAS = {"mcp": "".join(json.dumps(m) + "\n" for m in (
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "prueba", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "tareas", "arguments": {"proyecto": "Uno"}}},
))}


def verbos_de_la_cli():
    """Los verbos de `cli.analizador()` y, si tienen, sus acciones: {"fuentes": {"info", …}}."""
    import argparse
    from tareas import cli

    def subcomandos(analizador):
        for accion in analizador._actions:
            if isinstance(accion, argparse._SubParsersAction):
                return accion.choices
        return {}

    return {verbo: set(subcomandos(sub)) for verbo, sub in subcomandos(cli.analizador()).items()}


class SinId(dict):
    def __missing__(self, clave):
        return "sin-" + clave


class NucleoSinGTK(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        temporal = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        vault = raiz / "vault"
        (vault / "01-Proyectos").mkdir(parents=True)
        (vault / "01-Proyectos" / "Uno.md").write_text(
            proyecto("- [ ] Una tarea que ya estaba",
                     "- [x] Una finalizada hace tiempo, para `limpiar` — 2026-01-01"),
            encoding="utf-8")
        plan = raiz / "plan.md"
        plan.write_text("# Un plan de prueba\n\n- [ ] Importada desde el núcleo\n",
                        encoding="utf-8")
        # Un repo de mentira, aparte del vault, solo para `init`: nunca contra RAIZ (el propio
        # checkout de Cotejo) ni contra un repo real de quien corre las pruebas.
        repo_init = raiz / "repo-init"
        repo_init.mkdir()
        # Un repo de verdad: `version` y `release` le preguntan a git por las etiquetas.
        subprocess.run(["git", "init", "-q", str(repo_init)], check=True)
        (raiz / "home").mkdir()
        # Un agente de terminal de mentira en el PATH: `maestro --simular` necesita uno, y la
        # máquina que corre las pruebas (CI) puede no tener ninguno.
        agentes = raiz / "agentes"
        agentes.mkdir()
        falso = agentes / ("claude.cmd" if os.name == "nt" else "claude")
        falso.write_text("@echo off\n" if os.name == "nt" else "#!/bin/sh\n", encoding="utf-8")
        falso.chmod(0o755)
        # Sin los COTEJO_ ni los XDG_ de quien corre las pruebas: la fuente, el motor y dónde se
        # escribe no pueden depender de lo que tenga exportado esa máquina.
        entorno = {k: v for k, v in os.environ.items()
                   if not k.startswith(("COTEJO_", "XDG_", "PYTHON"))}
        entorno.update({
            "COTEJO_NO_PREGUNTAR_CLI": "1",
            "HOME": str(raiz / "home"),
            "XDG_STATE_HOME": str(raiz / "estado"),
            "XDG_CONFIG_HOME": str(raiz / "config"),
            "COTEJO_VAULT": str(vault),
            "COTEJO_CARPETA_PROYECTOS": "01-Proyectos",
            "COTEJO_CONFIG": str(raiz / "config" / "cotejo" / "config.json"),
            "NO_COLOR": "1",  # argparse 3.14 colorea la ayuda; aquí sobra
            "PATH": str(agentes) + os.pathsep + os.environ.get("PATH", ""),
        })
        cls.resultados = []
        # Si `crear` falla, los que vienen detrás corren con un id que no existe: fallarán, pero
        # la secuencia sigue y el informe dice cuál fue el primero, en vez de un KeyError.
        ids = SinId()
        ids["plan"] = str(plan)
        ids["repo_init"] = str(repo_init)
        # Un adaptador de Notion mínimo (sin red, sin GTK): lo justo para que `fuentes agregar`
        # y `importar notion` tengan algo que registrar y traer.
        ids["notion_cmd"] = f"{sys.executable} {RAIZ / 'pruebas' / 'notion_minimo.py'}"
        for invocacion in INVOCACIONES:
            argumentos = [a.format_map(ids) for a in invocacion]
            fuera = invocacion[0] in EN_REPO_INIT
            hecho = subprocess.run([sys.executable, "-c", VIGIA, *argumentos],
                                   cwd=repo_init if fuera else RAIZ,
                                   env={**entorno, "PYTHONPATH": str(RAIZ)} if fuera else entorno,
                                   capture_output=True, text=True, timeout=60,
                                   input=ENTRADAS.get(invocacion[0], ""))
            cls.resultados.append((argumentos, hecho))
            if invocacion[0] == "crear" and hecho.returncode == 0:
                ids["id" if "id" not in ids else "id2"] = json.loads(hecho.stdout)["tarea"]["id"]
            # La versión de `proyecto.md` y el id del problema, para que `editar` y `resolver`
            # puedan correr verificados por lo que acaba de leer y anotar la propia secuencia.
            if (invocacion[0] == "leer" and invocacion[1:2] == ("proyecto",)
                    and hecho.returncode == 0):
                ids["version_proyecto"] = json.loads(hecho.stdout)["version"]
            if (invocacion[0] == "anotar" and invocacion[1:2] == ("problema",)
                    and hecho.returncode == 0):
                ids["pro_id"] = json.loads(hecho.stdout)["id"]

    def test_ningun_verbo_carga_la_interfaz(self):
        for argumentos, hecho in self.resultados:
            with self.subTest(verbo=" ".join(argumentos)):
                self.assertNotIn("CARGÓ LA INTERFAZ", hecho.stderr)
                self.assertNotEqual(hecho.returncode, 99, hecho.stderr)
                self.assertNotIn("Traceback", hecho.stderr)

    def test_cada_verbo_hace_su_trabajo(self):
        # Que corra sin GTK no vale si corre porque falló antes de llegar a nada.
        for argumentos, hecho in self.resultados:
            with self.subTest(verbo=" ".join(argumentos)):
                self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
                self.assertTrue(hecho.stdout.strip())

    def test_mcp_sirve_el_perfil_que_se_pide(self):
        # Por defecto, el núcleo (los verbos marcados con `cli.nucleo()`); con `completo`, todos.
        from tareas import mcp
        listas = {}
        for argumentos, hecho in self.resultados:
            if argumentos[0] != "mcp":
                continue
            respuestas = [json.loads(l) for l in hecho.stdout.splitlines()]
            lista = next(r for r in respuestas if r.get("id") == 2)
            listas[" ".join(argumentos[1:])] = {t["name"] for t in lista["result"]["tools"]}
        self.assertEqual(set(listas), {"", "--perfil nucleo", "--perfil completo"})
        self.assertEqual(listas[""], set(mcp.catalogo(perfil=mcp.NUCLEO)))
        self.assertEqual(listas["--perfil nucleo"], listas[""])
        self.assertEqual(listas["--perfil completo"], set(mcp.catalogo()))
        self.assertLess(listas[""], listas["--perfil completo"])

    def test_no_falta_ningun_verbo(self):
        probados = {}
        for invocacion in INVOCACIONES:
            if invocacion[0].startswith("-"):
                continue
            accion = invocacion[1] if len(invocacion) > 1 else None
            probados.setdefault(invocacion[0], set()).add(accion)
        for verbo, acciones in verbos_de_la_cli().items():
            with self.subTest(verbo=verbo):
                self.assertIn(verbo, probados, f"`{verbo}` no está en INVOCACIONES")
                faltan = acciones - probados[verbo]
                self.assertFalse(faltan, f"`{verbo}` tiene acciones sin probar: {sorted(faltan)}")


class FronteraNucleoInterfaz(unittest.TestCase):
    """Quién va a la ventana y quién a la CLI cuando se llama a `python -m tareas`."""

    def setUp(self):
        from tareas.board import es_del_board
        self.es_del_board = es_del_board

    def test_la_ventana_solo_con_sus_opciones_o_sin_argumentos(self):
        for argumentos in ([], ["--board"], ["--fondo"], ["--gapplication-service"]):
            with self.subTest(argumentos=argumentos):
                self.assertTrue(self.es_del_board(argumentos))

    def test_todo_lo_demas_es_de_la_cli(self):
        # Incluidos un verbo que aún no existe y uno mal escrito: eso lo contesta argparse,
        # no una ventana que se abre.
        for argumentos in (["estado"], ["--estado"], ["-h"], ["--help"], ["tareas", "--board"],
                           ["un-verbo-nuevo"], ["tarea"], *[[v] for v in verbos_de_la_cli()]):
            with self.subTest(argumentos=argumentos):
                self.assertFalse(self.es_del_board(argumentos))

    def test_la_puerta_del_board_no_carga_la_interfaz_al_importarse(self):
        codigo = ("import sys; sys.modules['gi'] = None; import tareas.board, tareas.__main__; "
                  "assert 'tareas.app' not in sys.modules")
        hecho = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ,
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(hecho.returncode, 0, hecho.stderr)

    def test_solo_el_board_importa_la_interfaz(self):
        # Una lectura del código, no una ejecución: fuera del paquete `tareas/app/` y de la puerta
        # del board nadie nombra `gi` ni `.app`. Barato, y dice dónde está la fuga si la hay. El
        # widget del dot (`dot_widget.py`) es interfaz como `tareas/app/`, que es el único que lo
        # importa; su dibujo y su núcleo (`dot_dibujo.py`, `dot.py`) no nombran `gi`.
        interfaz = RAIZ / "tareas" / "app"
        permitidos = {RAIZ / "tareas" / "board.py", RAIZ / "tareas" / "dot_widget.py"}
        prohibido = ("import gi", "from gi", "from .app", "from tareas.app", "import tareas.app")
        for ruta in sorted((RAIZ / "tareas").rglob("*.py")) + sorted((RAIZ / "enrutador").rglob("*.py")):
            if ruta in permitidos or ruta.is_relative_to(interfaz):
                continue
            texto = ruta.read_text(encoding="utf-8")
            with self.subTest(archivo=str(ruta.relative_to(RAIZ))):
                encontrados = [patron for patron in prohibido if patron in texto]
                self.assertFalse(encontrados, f"importa la interfaz: {encontrados}")


if __name__ == "__main__":
    unittest.main()
