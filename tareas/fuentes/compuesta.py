"""El vault y los repos migrados a la vez (v1.2, A3): la fuente de la migración gradual.

Mientras dure la migración hay dos sitios con tareas: los proyectos que ya se importaron a su
repo (`.cotejo/tareas.md`) y los que siguen en el vault. Esta fuente los junta para que el
board, la CLI y la barra vean un solo segundo cerebro, sin saber de dónde sale cada proyecto.

No es una fuente que se elija: es la de Obsidian con la marca `migrados` en su config,
`{"Cotejo": "/ruta/al/repo"}`. Un proyecto marcado se lee de su repo y **deja de leerse del
vault**, aunque su nota siga ahí: la nota original no se toca, y si estuviera en los dos sitios
saldrían sus tareas dos veces. Gana el repo. Quitar la marca lo deshace todo, sin escribir nada.

Es mínima a propósito (decisión E1): solo Obsidian + repos, y no N fuentes cualesquiera. Las dos
comparten la línea y la escritura verificada (`Repo` hereda de `Obsidian`), así que juntarlas
es repartir por proyecto; Notion u otra externa tienen otras garantías y se quedan fuera.

Cada escritura va a la fuente dueña de la tarea, que es la que sabe verificarla. Cuál es la
dueña se sabe por `donde`: las rutas de un repo son `<nombre>/.cotejo/tareas.md` y las conoce
su `_mapa`; todo lo demás es del vault.
"""

from pathlib import Path, PurePath

from ..fuente import Fuente
from .obsidian import Obsidian
from .repo import Repo


def migrados_de(config):
    """`{nombre del proyecto: ruta del repo}` desde la config, con lo que no se entiende fuera."""
    migrados = (config or {}).get("migrados") or {}
    if not isinstance(migrados, dict):
        return {}
    return {str(nombre).strip(): str(ruta).strip() for nombre, ruta in migrados.items()
            if str(nombre).strip() and isinstance(ruta, str) and ruta.strip()}


class Compuesta(Fuente):
    """El vault de Obsidian más los repos de los proyectos migrados."""

    nombre = "obsidian"  # la config es la de Obsidian; esto es Obsidian con proyectos fuera
    parametros = Obsidian.parametros
    accion_abrir = Obsidian.accion_abrir
    respaldo = Obsidian.respaldo

    def __init__(self, config=None):
        config = dict(config or {})
        self.migrados = migrados_de(config)
        self.vault = Obsidian(config)
        self.repo = Repo({"repos": list(self.migrados.values())})
        # Los repos son los migrados y nada más: ni `raiz` ni `COTEJO_REPOS`, que son de la
        # fuente repo cuando se usa sola y aquí colarían proyectos que nadie migró.
        self.repo.repos = [Path(ruta).expanduser() for ruta in self.migrados.values()]
        self.repo.raiz = None
        # Ruta resuelta del repo → el nombre que tiene el proyecto en el vault. Un repo se
        # llama como su carpeta («cotejo»), pero el proyecto es el que la persona conoce
        # («Cotejo»): `--proyecto Cotejo` tiene que seguir funcionando después de migrar.
        self._nombres = {Path(ruta).expanduser().resolve(): nombre
                         for nombre, ruta in self.migrados.items()}
        self._fuera = {nombre.lower() for nombre in self.migrados}

    @property
    def problema(self):
        # Un repo migrado que no está es un problema y no una lista más corta: sus tareas ya
        # no se leen del vault, así que sin él desaparecerían sin que nadie se entere.
        return self.vault.problema or (self.repo.problema if self.migrados else None)

    # --- leer ---------------------------------------------------------

    def escanear(self, incluir_hechas=False, avisos=None):
        proyectos = [p for p in self.vault.escanear(incluir_hechas, avisos)
                     if p.nombre.lower() not in self._fuera]
        # El nombre del repo («cotejo») → el del proyecto en el vault («Cotejo»).
        renombre = {nombre: self._nombres.get(ruta, nombre)
                    for nombre, ruta, _ in self.repo._descubrir()}
        for proyecto in self.repo.escanear(incluir_hechas, avisos):
            proyecto.nombre = renombre.get(proyecto.nombre, proyecto.nombre)
            proyectos.append(proyecto)
        proyectos.sort(key=lambda p: p.orden)
        return proyectos

    def normalizar_id(self, texto):
        return self.vault.normalizar_id(texto)

    def leido(self, proyectos=None):
        # Cada una cuenta solo los `donde` que conoce, así que pasarle a las dos la misma
        # lista no cuenta nada dos veces.
        return self.vault.leido(proyectos) + self.repo.leido(proyectos)

    # --- escribir -----------------------------------------------------

    def _duena(self, donde):
        relativa = PurePath(str(donde)).as_posix()
        if relativa not in self.repo._mapa:
            self.repo._descubrir()
        return self.repo if relativa in self.repo._mapa else self.vault

    def crear(self, proyecto, texto, dificultad="", **opciones):
        return self._duena(proyecto.donde).crear(proyecto, texto, dificultad, **opciones)

    def marcar(self, tarea, hecha=True):
        return self._duena(tarea.donde).marcar(tarea, hecha)

    def poner_estado(self, tarea, nuevo):
        return self._duena(tarea.donde).poner_estado(tarea, nuevo)

    def poner_agente(self, tarea, agente):
        return self._duena(tarea.donde).poner_agente(tarea, agente)

    def asegurar_id(self, tarea):
        return self._duena(tarea.donde).asegurar_id(tarea)

    def quitar(self, tarea):
        return self._duena(tarea.donde).quitar(tarea)

    def fecha_cierre(self, tarea):
        return self._duena(tarea.donde).fecha_cierre(tarea)

    # --- dónde vive ---------------------------------------------------

    def vigilables(self):
        return list(dict.fromkeys([*self.vault.vigilables(), *self.repo.vigilables()]))

    def uri(self, cosa):
        return self._duena(cosa.donde).uri(cosa)

    def carpeta_de(self, proyecto):
        for nombre, ruta in self.migrados.items():
            if nombre.lower() == str(proyecto).lower():
                ruta = Path(ruta).expanduser()
                return ruta if ruta.is_dir() else None
        return self.vault.carpeta_de(proyecto)

    def carpetas_propias(self):
        return [*self.vault.carpetas_propias(), *self.repo.carpetas_propias()]
