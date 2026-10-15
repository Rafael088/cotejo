"""La versión del proyecto del usuario (v1.2.4): la publicada y la que está en curso.

No es la versión de Cotejo (esa es `tareas.__version__`): es la del repo en el que trabaja el
agente. Dos datos y una regla:

- **La publicada sale de git**: el tag semver `vX.Y.Z` más alto alcanzable desde HEAD. No se
  guarda en ningún sitio, así que no se puede desincronizar.
- **La declarada va en `proyecto.md`**, en el frontmatter, como `version: X.Y.Z`. Se lee por el
  almacén, como cualquier otra entrada de `.cotejo/`.
- **La en curso se calcula**: la declarada mientras ningún tag la alcance; cuando el último tag
  la alcanza (o no hay declarada), la siguiente de parche de la publicada. Nadie sube
  `version:` a mano después de etiquetar, y calcularla no escribe nada.

Lo de arriba son funciones puras (`parsear`, `siguiente_parche`, `mas_alta`, `en_curso`); las
únicas con E/S son `publicada` (lee los tags) y `declarada` (lee `proyecto.md`), y `estado` las
junta. Es la base de `init`/`importar` (ponen `version:`), del tag `#vX.Y.Z` en las tareas, de
`cotejo version` y de `cotejo release`.
"""

import argparse
import re
import subprocess
from typing import NamedTuple

from . import almacen, rutas

CLAVE = "version"  # la clave del frontmatter de `proyecto.md`
INICIAL = "0.1.0"  # la que se pone a un proyecto sin ningún tag

SEMVER_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
# La versión a la que pertenece una tarea: `vX.Y.Z`, o `vX.Y` si es de toda la línea menor.
DE_TAREA_RE = re.compile(r"^v?((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))?)$")


class Semver(NamedTuple):
    """`X.Y.Z` sin prerelease ni build: es lo que se etiqueta. Compara como tupla."""

    mayor: int
    menor: int
    parche: int

    def __str__(self):
        return f"{self.mayor}.{self.menor}.{self.parche}"

    @property
    def etiqueta(self):
        """El nombre del tag de git: `vX.Y.Z`."""
        return f"v{self}"


# --- puras -----------------------------------------------------------------------------------

def parsear(texto):
    """`Semver` de `"1.2.3"` o `"v1.2.3"` (con espacios alrededor), o None si no lo es.

    Estricto a propósito: ni `1.2`, ni `v1.2.3-rc1`, ni ceros a la izquierda. Un tag que no es
    exactamente una versión publicada no cuenta como tal.
    """
    if isinstance(texto, Semver):
        return texto
    m = SEMVER_RE.match(str(texto or "").strip())
    return Semver(*map(int, m.groups())) if m else None


def de_tarea(texto):
    """La versión de una tarea, normalizada a `"vX.Y.Z"` o `"vX.Y"`, o None si no lo es.

    Acepta `1.2`, `v1.2`, `1.2.4` y `v1.2.4` (con espacios alrededor). Es el único parser de la
    versión de una tarea: lo usan la fuente al leer su tag (`#v1.2.4` en Obsidian), el modelo
    al leer el prefijo `v1.2.4 ·` del texto, y la CLI para validar `--version`.
    """
    m = DE_TAREA_RE.match(str(texto or "").strip())
    return f"v{m.group(1)}" if m else None


def argumento(texto):
    """El `type=` de `tareas --version` y `crear --version`: normalizada, o un error de uso."""
    normalizada = de_tarea(texto)
    if not normalizada:
        raise argparse.ArgumentTypeError(
            f"«{texto}» no es una versión: usa X.Y o X.Y.Z (1.2 o 1.2.4, con o sin la v)")
    return normalizada


def pertenece(version_tarea, pedida):
    """Si una tarea de `version_tarea` entra en el filtro `pedida` (`tareas --version`).

    `X.Y.Z` pide exactamente esa; `X.Y` pide la línea entera: las de `#vX.Y` y las de cualquier
    `#vX.Y.Z`. Una tarea de `#vX.Y` no entra en `--version X.Y.Z`: es de la línea, no de ese
    parche. Sin versión (o con una que no parsea) no entra en ningún filtro.
    """
    tarea, filtro = de_tarea(version_tarea), de_tarea(pedida)
    if not tarea or not filtro:
        return False
    return tarea == filtro or (filtro.count(".") == 1 and tarea.startswith(filtro + "."))


def siguiente_parche(version):
    """La siguiente de parche: `1.2.3` → `1.2.4`. Acepta `Semver` o texto; None si no parsea."""
    v = parsear(version)
    return Semver(v.mayor, v.menor, v.parche + 1) if v else None


def mas_alta(nombres):
    """La `Semver` más alta entre `nombres` (tags u otros textos); los que no son semver se
    ignoran. None si ninguno lo es."""
    versiones = [v for v in map(parsear, nombres) if v]
    return max(versiones) if versiones else None


def en_curso(publicada, declarada):
    """La versión en curso a partir de la publicada (último tag) y la declarada (`version:`).

    - La declarada, si ningún tag la alcanzó todavía.
    - La siguiente de parche de la publicada, si el tag ya la alcanzó o no hay declarada.
    - La declarada, si no hay tags; `None` si no hay ni una ni otra (el proyecto no tiene
      versión: lo dirá `doctor`).
    """
    pub, dec = parsear(publicada), parsear(declarada)
    if dec and (not pub or dec > pub):
        return dec
    return siguiente_parche(pub) if pub else None


def inicial(publicada):
    """La que se escribe en un proyecto que todavía no tiene `version:`: la siguiente de parche
    del último tag, o `0.1.0` si no hay ninguno."""
    return siguiente_parche(publicada) or parsear(INICIAL)


# --- con E/S (solo leer) ---------------------------------------------------------------------

def comando_git(raiz, *args):
    """`git -C raiz args`, con `core.longpaths=true` en Windows: sin él, git no lee los tags de
    un repo cuya raíz ronda los 240 caracteres (`.git/refs/tags/...` pasa de MAX_PATH) y la
    versión publicada sale None sin ningún error. Lo usan también `version` y `release`."""
    previo = ["-c", "core.longpaths=true"] if rutas.sistema() == "windows" else []
    return ["git", *previo, "-C", str(raiz), *args]


def tags(raiz):
    """Los tags alcanzables desde HEAD en el repo de `raiz`. Lista vacía si no es un repo, no
    hay commits, no hay git o algo falla: no tener versión publicada no es un error."""
    try:
        hecho = subprocess.run(comando_git(raiz, "tag", "--list", "--merged", "HEAD"),
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if hecho.returncode != 0:
        return []
    return [linea.strip() for linea in hecho.stdout.splitlines() if linea.strip()]


def publicada(raiz):
    """La `Semver` del tag semver más alto alcanzable desde HEAD, o None."""
    return mas_alta(tags(raiz))


def declarada(raiz):
    """`(Semver o None, texto crudo o None)` de `version:` en `.cotejo/proyecto.md`.

    El crudo se devuelve aparte para que quien llame pueda avisar de un `version:` que no es
    semver en vez de tratarlo como ausente. Sin `proyecto.md`, `(None, None)`.
    """
    alm = almacen.Almacen(raiz)
    try:
        entrada = alm.leer(almacen.ID_PROYECTO)
    except (almacen.EntradaNoExiste, almacen.IdRepetido):
        return None, None
    crudo = entrada.datos.get(CLAVE)
    if crudo in (None, "", []):
        return None, None
    crudo = str(crudo)
    return parsear(crudo), crudo


def estado(raiz):
    """Todo lo que se sabe de la versión del proyecto en `raiz`, listo para el JSON.

    `{"publicada", "tag", "declarada", "en_curso", "calculada", "valida"}`: las versiones como
    texto `X.Y.Z` (o None); `tag` es el nombre en git de la publicada; `calculada` dice si la en
    curso no es la que está escrita (se dedujo del último tag); `valida` es False si hay un
    `version:` escrito que no es semver.
    """
    pub = publicada(raiz)
    dec, crudo = declarada(raiz)
    curso = en_curso(pub, dec)
    return {
        "publicada": str(pub) if pub else None,
        "tag": pub.etiqueta if pub else None,
        "declarada": str(dec) if dec else crudo,
        "en_curso": str(curso) if curso else None,
        "calculada": bool(curso) and curso != dec,
        "valida": crudo is None or dec is not None,
    }


# --- con E/S (escribir) ----------------------------------------------------------------------

def asegurar(raiz):
    """Deja `version:` en el `proyecto.md` de `raiz`, sin pisar nunca una que ya esté.

    Es lo que usan `init` e `importar --aplicar`: la siguiente de parche del último tag, o
    `0.1.0` si no hay ninguno. Crea `proyecto.md` si no existe. Idempotente: con `version:`
    escrita (incluso una que no sea semver, que es de la persona y la dice `doctor`) no
    escribe nada. Devuelve `{"version": "X.Y.Z" | crudo, "hecho": "puesta" | "ya-estaba"}`.
    """
    dec, crudo = declarada(raiz)
    if crudo is not None:
        return {"version": crudo, "hecho": "ya-estaba"}
    nueva = str(inicial(publicada(raiz)))
    alm = almacen.Almacen(raiz)
    try:
        entrada = alm.leer(almacen.ID_PROYECTO)
    except almacen.EntradaNoExiste:
        entrada = alm.crear("proyecto", raiz.name if hasattr(raiz, "name") else str(raiz))
    alm.reescribir(almacen.ID_PROYECTO, entrada.version, campos={CLAVE: nueva})
    return {"version": nueva, "hecho": "puesta"}


def falta(raiz):
    """True si `raiz` ya tiene `.cotejo/proyecto.md` pero sin `version:` (lo avisa `doctor`)."""
    if declarada(raiz)[1] is not None:
        return False
    try:
        almacen.Almacen(raiz).leer(almacen.ID_PROYECTO)
    except (almacen.EntradaNoExiste, almacen.IdRepetido):
        return False
    return True
