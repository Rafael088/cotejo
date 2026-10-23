"""Repos de git como fuente: un `.cotejo/tareas.md` en cada uno, con la misma línea que Obsidian.

Es para quien no tiene vault. Un repo es un proyecto, y sus tareas viven en
`<repo>/.cotejo/tareas.md` con exactamente la misma línea que en una nota de Obsidian
(`- [ ] texto #medio #agente/x ^cotejo-id`). Por eso esta fuente no trae parser ni escritura
propios: hereda los de `fuentes/obsidian.py` —la comprobación de que la línea sigue igual, el
reemplazo atómico, la marca de bloque como id— y solo cambia **dónde** están los archivos. Dos
implementaciones de «escribir verificado» discreparían justo el día que importa.

Qué repos se leen lo dice la config: una lista (`repos`) o una carpeta (`raiz`) cuyos hijos
directos que sean repos y tengan `.cotejo/tareas.md` cuentan como proyectos. Las dos cosas se
pueden juntar. `COTEJO_REPOS` (rutas separadas por `os.pathsep`) y `COTEJO_RAIZ_REPOS` mandan
sobre la config en una sola invocación, igual que `COTEJO_VAULT` en Obsidian.

Lo que no hace: crear `.cotejo/tareas.md` ni registrar el repo en la config. Eso es de
`cotejo init`; aquí un repo de la lista sin el archivo se avisa en vez de inventárselo.
"""

import os
from pathlib import Path, PurePath

from .. import configuracion
from ..modelo import Proyecto
from .obsidian import ESTADOS_OCULTOS, Obsidian, leer_frontmatter, leer_tareas

CARPETA = ".cotejo"
ARCHIVO = "tareas.md"


class Repo(Obsidian):
    nombre = "repo"
    accion_abrir = "Abrir el archivo de tareas"
    respaldo = ("xdg-open",)
    parametros = {
        "repos": "Lista de rutas a repos de git; cada uno es un proyecto y sus tareas van en "
                 "<repo>/.cotejo/tareas.md.",
        "raiz": "Carpeta donde buscar repos: cuenta cada hijo directo que sea un repo y tenga "
                ".cotejo/tareas.md. Opcional, y se suma a «repos».",
    }

    @classmethod
    def config_inicial(cls):
        return {"repos": [], "raiz": ""}

    def __init__(self, config=None):
        config = config or {}
        entorno = os.environ.get("COTEJO_REPOS")
        repos = entorno.split(os.pathsep) if entorno is not None else config.get("repos") or []
        if isinstance(repos, str):
            repos = [repos]
        self.repos = [Path(r.strip()).expanduser() for r in repos
                      if isinstance(r, str) and r.strip()]
        raiz = os.environ.get("COTEJO_RAIZ_REPOS")
        raiz = raiz if raiz is not None else config.get("raiz") or ""
        self.raiz = Path(raiz.strip()).expanduser() if isinstance(raiz, str) and raiz.strip() else None
        # Lo que Obsidian usa y aquí no aplica: sin vault ni carpetas sueltas.
        self.vault = None
        self.carpeta_proyectos = ""
        self.carpetas_sueltas = []
        self._leido = {}
        self._notas_por_proyecto = {}
        # `donde` de cada proyecto → su archivo de verdad. Se llena al descubrir los repos.
        self._mapa = {}

    @property
    def problema(self):
        # Como en Obsidian, se mira en cada consulta: una ruta mal escrita escanearía cero
        # proyectos y el board diría «Todo al día».
        if not self.repos and not self.raiz:
            return (f"No hay ningún repo configurado. Pon la lista en {configuracion.ruta()}, "
                    f'con la forma {{"fuentes": {{"repo": {{"repos": ["/ruta/al/repo"]}}}}}} '
                    f'o {{"raiz": "/carpeta/de/repos"}}')
        # Un repo de la lista que ya no existe NO tumba la fuente (v1.3.0): se salta con aviso
        # (`faltantes`, y `escanear` lo deja en «avisos»). Solo es un problema si no queda
        # ninguno con el que trabajar: entonces cero proyectos no sería «todo al día».
        if self.faltantes and not any(r.is_dir() for r in self.repos) \
                and not (self.raiz and self.raiz.is_dir()):
            repo = self.faltantes[0]
            return (f"El repo {repo} no existe o no es una carpeta. Corrige «repos» en "
                    f"{configuracion.ruta()} o en COTEJO_REPOS")
        if self.raiz and not self.raiz.is_dir():
            return (f"La carpeta de repos {self.raiz} no existe. Corrige «raiz» en "
                    f"{configuracion.ruta()} o en COTEJO_RAIZ_REPOS")
        return None

    @property
    def faltantes(self):
        """Los repos de la lista que ya no existen (o no son carpeta), en el orden de la lista."""
        return [repo for repo in self.repos if not repo.is_dir()]

    def aviso_de_faltante(self, repo):
        """El aviso estructurado de un repo que falta: `nota` es la ruta, `motivo` lo explica en
        llano con cómo arreglarlo, y `repo_falta` deja la ruta para quien quiera actuar."""
        return {"nota": str(repo), "repo_falta": str(repo),
                "motivo": (f"El repo «{repo}» ya no existe, así que se salta y los demás siguen "
                           f"funcionando. Si lo borraste o lo moviste a propósito, quítalo de "
                           f"«repos» en {configuracion.ruta()} (no hay un comando para quitarlo "
                           f"todavía); si lo moviste, pon su ruta nueva.")}

    # --- qué repos hay ------------------------------------------------

    def _descubrir(self):
        """Los repos que cuentan, como `[(nombre, ruta, explicito)]`, y llena `_mapa`.

        De la raíz solo entran los hijos con `.git` como **carpeta**: un worktree o un
        submódulo lo tienen como archivo, y contarlos repetiría las tareas del repo principal
        con otros ids de proyecto.
        """
        candidatos = [(repo, True) for repo in self.repos if repo.is_dir()]
        if self.raiz and self.raiz.is_dir():
            for hijo in sorted(self.raiz.iterdir(), key=lambda p: p.name.lower()):
                if (not hijo.name.startswith(".") and hijo.is_dir()
                        and (hijo / ".git").is_dir() and (hijo / CARPETA / ARCHIVO).is_file()):
                    candidatos.append((hijo, False))

        vistos, nombres, repos = set(), set(), []
        for ruta, explicito in candidatos:
            real = ruta.resolve()
            if real in vistos:
                continue
            vistos.add(real)
            # Un proyecto se llama como su carpeta. Si dos repos se llaman igual, el segundo
            # lleva delante a su padre: dos grupos con el mismo nombre harían que
            # `--proyecto X` mezclara las tareas de los dos.
            nombre = real.name
            if nombre.lower() in nombres:
                nombre = f"{real.parent.name}/{real.name}"
            if nombre.lower() in nombres:
                nombre = str(real)
            nombres.add(nombre.lower())
            self._mapa[_donde(nombre)] = real / CARPETA / ARCHIVO
            repos.append((nombre, real, explicito))
        return repos

    def _archivo(self, relativa):
        # Normalizar a slashes ('/') para que coincida con las claves en _mapa que siempre
        # usan '/' (generadas por _donde()). En Windows, str(Path) puede tener backslashes.
        relativa = PurePath(relativa).as_posix()
        if relativa not in self._mapa:
            self._descubrir()
        if relativa not in self._mapa:
            # El repo ya no está en la config: no hay dónde escribir, y adivinar sería peor.
            raise FileNotFoundError(f"No encuentro el repo de «{relativa}»")
        return self._mapa[relativa]

    # --- leer ---------------------------------------------------------

    def escanear(self, incluir_hechas=False, avisos=None):
        self._leido = {}
        self._notas_por_proyecto = {}
        self._mapa = {}
        proyectos = []
        if avisos is not None:
            avisos.extend(self.aviso_de_faltante(repo) for repo in self.faltantes)
        for nombre, ruta, explicito in self._descubrir():
            donde = _donde(nombre)
            archivo = self._mapa[donde]
            if not archivo.is_file():
                if explicito and avisos is not None:
                    avisos.append({"nota": str(archivo),
                                   "motivo": f"el repo no tiene {CARPETA}/{ARCHIVO} todavía"})
                continue
            lineas = self._leer(archivo, avisos, donde)
            meta = leer_frontmatter(lineas[:60])
            if meta.get("estado") in ESTADOS_OCULTOS:
                continue
            proyecto = Proyecto(nombre=nombre, donde=donde, estado=meta.get("estado", ""),
                                prioridad=meta.get("prioridad", ""))
            self._notas_por_proyecto[donde] = {donde}
            for tarea in leer_tareas(Path(donde), lineas, incluir_hechas):
                (proyecto.hechas if tarea.hecha else proyecto.tareas).append(tarea)
            proyectos.append(proyecto)
        proyectos.sort(key=lambda p: p.orden)
        return proyectos

    # --- dónde vive ---------------------------------------------------

    def vigilables(self):
        """La `.cotejo/` de cada repo (o el repo, si todavía no la tiene), sus subcarpetas del
        almacén (decisiones, problemas, etc.) y la raíz, para enterarse también de un repo nuevo."""
        rutas = []
        for _, ruta, _ in self._descubrir():
            carpeta = ruta / CARPETA
            rutas.append(str(carpeta if carpeta.is_dir() else ruta))
            # Añade las subcarpetas del almacén que existan en .cotejo/
            if carpeta.is_dir():
                from ..almacen import TIPOS
                for tipo in TIPOS.values():
                    if tipo.carpeta:  # proyecto no tiene carpeta
                        subcarpeta = carpeta / tipo.carpeta
                        if subcarpeta.is_dir():
                            rutas.append(str(subcarpeta))
        if self.raiz and self.raiz.is_dir():
            rutas.append(str(self.raiz))
        return list(dict.fromkeys(rutas))

    def carpeta_de(self, proyecto):
        for nombre, ruta, _ in self._descubrir():
            if nombre == proyecto:
                return ruta
        return None

    def uri(self, tarea):
        try:
            return self._archivo(tarea.donde).as_uri()
        except (FileNotFoundError, ValueError):
            return ""


def _donde(nombre):
    """Cómo se nombra el archivo de un proyecto hacia fuera: legible y sin rutas de la máquina."""
    return f"{nombre}/{CARPETA}/{ARCHIVO}"
