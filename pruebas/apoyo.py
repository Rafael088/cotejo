"""Andamiaje de las pruebas: un vault de mentira que vive y muere con cada prueba.

Nada de aquí toca el vault de verdad ni el estado en `~/.local`. Es la condición para poder
probar la escritura sin miedo: `vault.py` es el único código del proyecto que modifica las
notas del usuario, así que las pruebas que lo cubren tienen que poder equivocarse sin
consecuencias.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Ninguna prueba le pregunta su sesión al claude/codex instalados (cotejo-2j6un7): las que
# prueban esa pregunta lo quitan y ponen CLIs de mentira en su PATH.
os.environ.setdefault("COTEJO_NO_PREGUNTAR_CLI", "1")

# Las temporales de las pruebas no buscan repo por encima de la temporal del sistema
# (cotejo-wwrzyf): si `/tmp` es un repo —por un `.git` que dejó otro programa—, `git` y
# `conexion._raiz_git` no deben tomar las carpetas de la prueba por hijas suyas. Es la misma
# frontera que pone git con `GIT_CEILING_DIRECTORIES`, y la heredan los subprocesos.
_techos = [tempfile.gettempdir()]
if os.environ.get("GIT_CEILING_DIRECTORIES"):
    _techos.append(os.environ["GIT_CEILING_DIRECTORIES"])
os.environ["GIT_CEILING_DIRECTORIES"] = os.pathsep.join(dict.fromkeys(_techos))


def nota(*lineas):
    """Une líneas dejando el salto final, que es como se ven los archivos de verdad."""
    return "".join(linea + "\n" for linea in lineas)


def proyecto(*lineas, **frontmatter):
    """Una nota de proyecto con su frontmatter. Sin claves, sale `tipo: proyecto` a secas."""
    frontmatter.setdefault("tipo", "proyecto")
    cabecera = ["---"] + [f"{k}: {v}" for k, v in frontmatter.items()] + ["---", ""]
    return nota(*cabecera, *lineas)


class PruebaConVault(unittest.TestCase):
    """Base con un vault temporal. `self.vault` es la ruta; `self.notas` lo llena."""

    CARPETA = "01-Proyectos"

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.vault = Path(temporal.name)
        (self.vault / self.CARPETA).mkdir(parents=True)

    def escribir_nota(self, ruta_relativa, contenido, binario=None):
        """Crea una nota bajo la carpeta de proyectos. `binario` escribe bytes tal cual,
        que es como se prueban los saltos de línea y los archivos ilegibles."""
        ruta = self.vault / self.CARPETA / ruta_relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if binario is not None:
            ruta.write_bytes(binario)
        else:
            ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def leer_nota(self, ruta_relativa):
        return (self.vault / self.CARPETA / ruta_relativa).read_text(encoding="utf-8")

    def leer_bytes(self, ruta_relativa):
        return (self.vault / self.CARPETA / ruta_relativa).read_bytes()

    @property
    def fuente(self):
        """La fuente Obsidian apuntada al vault de mentira de esta prueba.

        Se construye cada vez a propósito: una fuente no guarda estado entre llamadas, y si
        algún día lo guardara, estas pruebas lo dirían enseguida.
        """
        from tareas.fuentes.obsidian import Obsidian
        return Obsidian({"vault": str(self.vault), "carpeta_proyectos": self.CARPETA})

    def escanear(self, incluir_hechas=True):
        return self.fuente.escanear(incluir_hechas=incluir_hechas)

    def tareas_de(self, nombre_proyecto, incluir_hechas=True):
        proyectos = self.escanear(incluir_hechas)
        uno = next(p for p in proyectos if p.nombre == nombre_proyecto)
        return uno, list(uno.tareas) + list(uno.hechas)

    def una_tarea(self, nombre_proyecto="Uno"):
        _, tareas = self.tareas_de(nombre_proyecto)
        return tareas[0]


class PruebaDeCLI(PruebaConVault):
    """Como la anterior, pero además aísla lo que la CLI escribe fuera del vault.

    `estado.ARCHIVO` y `bitacora.ARCHIVO` apuntan de verdad a `~/.local/state`: sin
    redirigirlos, correr las pruebas le ensuciaría al usuario el archivo que lee el widget de
    la barra y el registro de lo que hicieron los agentes.
    """

    def setUp(self):
        super().setUp()
        from tareas import ahorro, bitacora, estado, worktrees
        estados = self.vault / "estado"
        estados.mkdir()
        # Los worktrees de despacho y su registro, fuera del vault de la prueba (como de verdad)
        # y lejos de la carpeta de estado del usuario.
        fuera = tempfile.TemporaryDirectory()
        self.addCleanup(fuera.cleanup)
        self.worktrees_base = Path(fuera.name) / "wt"
        self.worktrees_registro = Path(fuera.name) / "registro"
        self.archivo_estado = estados / "estado.json"
        self.bitacora = estados / "bitacora.jsonl"
        self.ahorro = estados / "ahorro.json"
        # La config también: sin esto, qué fuente se usa lo decidiría el archivo de verdad del
        # usuario, y una prueba pasaría o no según lo que tenga configurado esa máquina.
        self.config = self.vault / "config.json"
        for parche in (mock.patch.object(estado, "ARCHIVO", self.archivo_estado),
                       mock.patch.object(bitacora, "ARCHIVO", self.bitacora),
                       mock.patch.object(ahorro, "ARCHIVO", self.ahorro),
                       mock.patch.object(worktrees, "BASE", self.worktrees_base),
                       mock.patch.object(worktrees, "REGISTRO", self.worktrees_registro),
                       mock.patch.dict(os.environ, {"COTEJO_VAULT": str(self.vault),
                                                    "COTEJO_CARPETA_PROYECTOS": self.CARPETA,
                                                    "COTEJO_CONFIG": str(self.config),
                                                    # Sin esto, el obsidian.json de verdad de esta
                                                    # máquina decidiría qué vault «se detecta».
                                                    "XDG_CONFIG_HOME": str(self.vault / "xdg-sin-obsidian")})):
            parche.start()
            self.addCleanup(parche.stop)
        # Dentro del patch.dict de arriba, que deja el entorno como estaba al terminar.
        os.environ.pop("COTEJO_WORKTREES", None)

    def correr_crudo(self, *argumentos):
        """Llama a la CLI y devuelve (código, lo que imprimió tal cual).

        Aparte de `correr` porque no todo lo que imprime la CLI es JSON: `protocolo` escupe
        Markdown para que lo lea un agente que no sabe de esquemas.
        """
        from tareas import cli
        salida = io.StringIO()
        # stderr también: argparse escribe ahí sus errores de uso y ensuciaría el informe.
        with mock.patch.object(sys, "argv", ["tareas-obsidian", *argumentos]), \
                contextlib.redirect_stdout(salida), \
                contextlib.redirect_stderr(io.StringIO()):
            codigo = cli.main()
        return codigo, salida.getvalue().strip()

    def correr(self, *argumentos):
        """Llama a la CLI como lo haría la terminal. Devuelve (código, JSON de la salida)."""
        codigo, texto = self.correr_crudo(*argumentos)
        return codigo, json.loads(texto) if texto else None

    def operaciones(self):
        """Lo que quedó anotado en la bitácora, una por línea."""
        if not self.bitacora.exists():
            return []
        return [json.loads(l) for l in self.bitacora.read_text(encoding="utf-8").splitlines() if l]


class PruebaDeEnrutador(PruebaDeCLI):
    """Como la anterior, y además aísla lo que escribe el enrutador y con qué motor despacha.

    La bandera que importa es `COTEJO_MOTOR=agente`: sin ella, una prueba que despache con el
    motor por defecto lanzaría Claude de verdad. Pasó al escribir esta batería —88 segundos y
    tokens gastados— y por eso está aquí y no en cada prueba.
    """

    def setUp(self):
        super().setUp()
        from enrutador import bitacora as despachos
        self.despachos = self.vault / "estado" / "despachos.jsonl"
        for parche in (mock.patch.object(despachos, "ARCHIVO", self.despachos),
                       mock.patch.dict(os.environ, {"COTEJO_CONFIG": str(self.config),
                                                    "COTEJO_MOTOR": "agente"})):
            parche.start()
            self.addCleanup(parche.stop)

    def escribir_config(self, ajustes, fuera=None):
        """Los ajustes del enrutador, que van bajo su clave dentro del config de Cotejo."""
        self.config.write_text(json.dumps({**(fuera or {}), "enrutador": ajustes},
                                          ensure_ascii=False), encoding="utf-8")

    def despachados(self):
        """Lo que quedó anotado en la bitácora de despachos, uno por línea."""
        if not self.despachos.exists():
            return []
        return [json.loads(l) for l in self.despachos.read_text(encoding="utf-8").splitlines() if l]
