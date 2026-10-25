"""Un worktree de git por despacho: cada tarea de código se hace en su propia carpeta y rama.

El 2026-09-17 dos agentes compartían árbol y un `git add -A` se llevó el trabajo sin commitear
del otro, firmado con el nombre equivocado y en la rama equivocada. Desde B3 (v1.1),
`despachar` crea por defecto un worktree con la rama `cotejo/<id>` cuando la tarea es de un repo
de git, y le da esa carpeta al agente. `--sin-aislar` es para el caso contrario.

Dónde caen, y por qué ahí:

- **Fuera del repo y fuera del vault.** El repo de Cotejo vive dentro del vault de Obsidian; un
  worktree dentro de cualquiera de los dos metería sus `.md` con `- [ ]` en el escaneo, como si
  fueran tareas de verdad. Por defecto van en la carpeta de estado de Cotejo
  (`rutas.estado()/wt/<id>`), y se puede cambiar con `enrutador.worktrees.carpeta` o con
  `COTEJO_WORKTREES`; una carpeta que caiga dentro del repo o del vault se rechaza antes de
  tomar la tarea.
- **Con nombres cortos.** En Windows la ruta de un archivo hondo de un repo, colgada de
  `%LOCALAPPDATA%\\cotejo\\estado\\wt\\<id>`, ya roza los 260 caracteres; por eso `wt` y no
  `worktrees`, y por eso todo `git` de este módulo (`_git`) va con `core.longpaths=true` en
  Windows por defecto: no es solo `worktree add`/`remove`, cualquier `status` o `rev-parse`
  contra esa misma ruta se niega igual sin el `-c` (B5).

Lo que se sabe de cada uno vive en un registro (`<estado>/worktrees/<id>.json`), un archivo
por tarea para que dos despachos en paralelo no se pisen al escribirlo. De ahí lo leen
`comprobar` y `entregar` (que corren en el worktree de la tarea), `revisar` (que dice dónde
quedó) y el board (que lo retira al aprobar o descartar la tarea).

Retirar un worktree **nunca** borra la rama —es lo que se integra después— ni se lleva
cambios sin commitear: si el worktree tiene algo sin commitear, se queda donde está y se dice.

No importa GTK, como el resto del núcleo.
"""

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from . import rutas

ESQUEMA = 1

# El registro y la carpeta por defecto. Constantes de módulo, como `bitacora.ARCHIVO`: es lo que
# deja que las pruebas las redirijan con un `mock.patch` en vez de tocar el estado de verdad.
REGISTRO = rutas.estado() / "worktrees"
BASE = rutas.estado() / "wt"

PREFIJO_RAMA = "cotejo/"
TIEMPO_GIT = 60


class ErrorWorktree(Exception):
    """No se pudo preparar el worktree. Lleva qué hacer, como un `ErrorCLI`."""

    def __init__(self, mensaje, salida):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.salida = salida


def seguro(tarea_id):
    """El id como nombre de carpeta y de rama: solo letras, números, `-` y `_`.

    Un id sin marca de bloque se nombra por su nota y su línea (`Uno.md:3`), y ni `:` ni `/`
    valen en una carpeta de Windows o en una rama. Si hubo que cambiar algo, se le cuelga un
    trozo del hash del id original, para que dos ids que se limpian igual no choquen.
    """
    tarea_id = str(tarea_id or "")
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", tarea_id).strip("-_")[:60]
    if limpio != tarea_id or not limpio:
        resumen = hashlib.sha1(tarea_id.encode("utf-8")).hexdigest()[:6]
        limpio = f"{limpio}-{resumen}" if limpio else resumen
    return limpio


def rama_de(tarea_id):
    return PREFIJO_RAMA + seguro(tarea_id)


def carpeta_base(configurada=None):
    """Dónde se crean: `COTEJO_WORKTREES`, si no lo que diga la config, si no `BASE`."""
    desde_entorno = os.environ.get("COTEJO_WORKTREES")
    elegida = desde_entorno or configurada
    return Path(elegida).expanduser() if elegida else BASE


def _absoluta(ruta):
    """La ruta absoluta y normalizada para comparar, sin exigir que exista."""
    return os.path.normcase(os.path.abspath(os.path.realpath(str(ruta))))


def dentro(ruta, padre):
    """¿Está `ruta` dentro de `padre` (o es la misma)? Insensible a mayúsculas en Windows."""
    hija, madre = _absoluta(ruta), _absoluta(padre)
    try:
        return os.path.commonpath([hija, madre]) == madre
    except ValueError:  # distintas unidades en Windows
        return False


def _git(carpeta, *args, longpaths=True):
    """(código, salida, error) de un git sin shell, sin entrada y con tiempo límite.

    `longpaths` por defecto en `True`: toda llamada de este módulo puede caer sobre el repo o
    el worktree del usuario, y los dos pueden vivir en una ruta de más de 260 caracteres. No es
    solo cosa de `worktree add`/`remove` —lo que los hizo evidentes—: `status`, `rev-parse` o
    `symbolic-ref` contra esa misma ruta se niegan igual en Windows sin el `-c`. Sin coste fuera
    de Windows (`_git` lo ignora ahí) ni dentro de Windows cuando no hace falta.
    """
    previo = ["-c", "core.longpaths=true"] if longpaths and rutas.sistema() == "windows" else []
    try:
        hecho = subprocess.run(["git", *previo, "-C", str(carpeta), *args],
                               stdin=subprocess.DEVNULL, capture_output=True,
                               timeout=TIEMPO_GIT)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, "", str(error)
    return (hecho.returncode, hecho.stdout.decode("utf-8", "replace").strip(),
            hecho.stderr.decode("utf-8", "replace").strip())


def raiz_repo(carpeta):
    """La raíz del repo de git que contiene `carpeta`, o None si no es un repo (o no hay git)."""
    if not carpeta or not Path(carpeta).is_dir():
        return None
    codigo, salida, _ = _git(carpeta, "rev-parse", "--show-toplevel")
    return Path(salida) if codigo == 0 and salida else None


def sin_commits(repo):
    """¿El repo no tiene ningún commit (no hay HEAD)? Falso si no se puede saber."""
    codigo, _, _ = _git(repo, "rev-parse", "--verify", "-q", "HEAD")
    return codigo == 1


def planear(tarea_id, carpeta, base=None, vedadas=()):
    """Qué worktree tocaría a esta tarea, sin crear nada: `{repo, ruta, rama}` o None.

    None quiere decir «no es una tarea de un repo de git» (no hay carpeta, o no es un repo), y
    no es un error: una tarea del segundo cerebro que no es de código se despacha como siempre.
    Lanza `ErrorWorktree` si sí es de un repo pero el worktree caería donde no puede.
    """
    repo = raiz_repo(carpeta)
    if repo is None:
        return None
    base = Path(base) if base else BASE
    ruta = base / seguro(tarea_id)
    for vedada, que in [(repo, "el repo")] + [(v, "el vault") for v in vedadas if v]:
        if dentro(ruta, vedada):
            raise ErrorWorktree(
                f"El worktree caería en {ruta}, dentro de {que} ({vedada})",
                "Sus archivos se leerían como parte de él (en un vault, sus `- [ ]` como tareas "
                "de verdad). Pon `enrutador.worktrees.carpeta` (o COTEJO_WORKTREES) fuera de "
                "los dos, o despacha con --sin-aislar. No se tomó la tarea.")
    return {"repo": str(repo), "ruta": str(ruta), "rama": rama_de(tarea_id)}


def _archivo_registro(tarea_id):
    return REGISTRO / f"{seguro(tarea_id)}.json"


def de_tarea(tarea_id):
    """Lo registrado para esta tarea, con `existe` (si la carpeta sigue ahí), o None."""
    try:
        datos = json.loads(_archivo_registro(tarea_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or not datos.get("ruta"):
        return None
    datos["existe"] = Path(datos["ruta"]).is_dir()
    return datos


def carpeta_de(tarea_id):
    """La carpeta del worktree de la tarea si está registrado y sigue existiendo, o None."""
    datos = de_tarea(tarea_id)
    return datos["ruta"] if datos and datos["existe"] else None


def todos():
    """Todo lo registrado, cada uno con `existe`."""
    salida = []
    try:
        archivos = sorted(REGISTRO.glob("*.json"))
    except OSError:
        return salida
    for archivo in archivos:
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict) and datos.get("ruta"):
            datos["existe"] = Path(datos["ruta"]).is_dir()
            salida.append(datos)
    return salida


def _registrar(tarea_id, datos):
    REGISTRO.mkdir(parents=True, exist_ok=True)
    archivo = _archivo_registro(tarea_id)
    temporal = archivo.with_name(archivo.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, archivo)


def _es_worktree_de(ruta, rama):
    codigo, actual, _ = _git(ruta, "symbolic-ref", "--short", "-q", "HEAD")
    return codigo == 0 and actual == rama


def crear(tarea_id, plan):
    """Crea (o reutiliza) el worktree del plan y lo registra. Devuelve lo registrado.

    Reutiliza si ya existe para esta tarea en esa rama: un despacho repetido —la tarea volvió
    a pendiente y se reparte otra vez— sigue donde quedó el anterior en vez de empezar de cero.
    Si la rama `cotejo/<id>` existe pero ya no tiene carpeta, se le hace una nueva encima, con
    sus commits. Lanza `ErrorWorktree` si no se puede.
    """
    repo, ruta, rama = Path(plan["repo"]), Path(plan["ruta"]), plan["rama"]
    reutilizado = False
    anterior = de_tarea(tarea_id)
    if ruta.is_dir() and any(ruta.iterdir()):
        if not _es_worktree_de(ruta, rama):
            raise ErrorWorktree(
                f"Ya hay algo en {ruta} y no es el worktree de {rama}",
                "Bórralo o muévelo (o cambia enrutador.worktrees.carpeta) y repite; o despacha "
                "con --sin-aislar. No se tomó la tarea.")
        reutilizado = True
    else:
        # Un worktree cuya carpeta se borró a mano sigue apuntado en el repo, y git se niega a
        # crear otro en la misma rama hasta que se olvida.
        _git(repo, "worktree", "prune")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        codigo, _, _ = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{rama}")
        argumentos = (["worktree", "add", str(ruta), rama] if codigo == 0 else
                      ["worktree", "add", "-b", rama, str(ruta), "HEAD"])
        codigo, _, error = _git(repo, *argumentos, longpaths=True)
        if codigo != 0:
            raise ErrorWorktree(
                f"git no pudo crear el worktree en {ruta}: {error or 'sin detalle'}",
                "Mira `git worktree list` en el repo. Si la rama está en uso en otra carpeta, "
                "retírala ahí; si no, despacha con --sin-aislar.")
    _, cabeza, _ = _git(ruta, "rev-parse", "HEAD")
    datos = {"esquema": ESQUEMA, "tarea": tarea_id, "repo": str(repo), "ruta": str(ruta),
             "rama": rama, "desde": cabeza, "creado": int(time.time())}
    if reutilizado and anterior:
        datos["creado"] = anterior.get("creado", datos["creado"])
        # La base es de dónde salió la rama, no dónde quedó: la nota de retomar cuenta los
        # commits desde ahí (`retomar.py`).
        if anterior.get("rama") == rama and anterior.get("desde"):
            datos["desde"] = anterior["desde"]
    _registrar(tarea_id, datos)
    return {**datos, "reutilizado": reutilizado}


def retirar(tarea_id):
    """Quita el worktree de la tarea, sin borrar su rama ni cambios sin commitear.

    Devuelve `{"retirado": bool, ...}`; si no se retiró, `motivo` dice por qué. Sin nada
    registrado no hay nada que hacer, y eso no es un fallo (`registrado: false`).
    """
    datos = de_tarea(tarea_id)
    if datos is None:
        return {"retirado": False, "registrado": False}
    ruta, repo = Path(datos["ruta"]), Path(datos["repo"])
    salida = {"registrado": True, "ruta": str(ruta), "rama": datos.get("rama")}
    if ruta.is_dir():
        codigo, sucio, _ = _git(ruta, "status", "--porcelain")
        if codigo is None or codigo != 0:
            return {**salida, "retirado": False,
                    "motivo": f"no pude preguntarle a git por {ruta}; no lo toqué"}
        if sucio:
            return {**salida, "retirado": False,
                    "motivo": f"{ruta} tiene cambios sin commitear; no lo borro"}
        codigo, _, error = _git(repo, "worktree", "remove", str(ruta), longpaths=True)
        if codigo != 0:
            return {**salida, "retirado": False,
                    "motivo": f"git no pudo retirarlo: {error or 'sin detalle'}"}
    else:
        _git(repo, "worktree", "prune")
    try:
        _archivo_registro(tarea_id).unlink()
    except OSError:
        pass
    return {**salida, "retirado": True}
