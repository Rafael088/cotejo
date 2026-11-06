"""El candado del maestro: aprobar es de una persona, aunque el maestro tenga shell (v1.3.1,
cotejo-va7lgn).

Desde la 1.3.1 el maestro del board puede hacer lo que haría la persona en una terminal: editar
el código, correr comandos, crear y asignar tareas, despachar, entregar, bloquear. Lo único que
no puede es **aprobar**: dar una tarea por hecha (`[x]`, o «por integrar», que es la aprobación
a la espera del merge), aceptar una decisión propuesta o meter la rama `cotejo/<id>` de una tarea
en la rama principal. Decírselo en el prompt no basta: con un shell, `sed` pone una `[x]`
igual que el board. Por eso Cotejo lo comprueba él, fuera del agente:

- **Antes del turno** (`foto`): qué tareas del proyecto estaban aprobadas, en qué estado estaba
  cada decisión del `.cotejo/` del repo y dónde estaban la rama principal y las `cotejo/*`. La
  foto viaja en el turno en curso (`conversacion`), así que sobrevive a un board que se cierra.
- **Al terminar** (`revisar`, también si el turno murió o la persona lo paró): toda tarea que
  pasó a aprobada se devuelve al estado de antes por la fuente (`marcar(hecha=False)`,
  `poner_estado`); toda decisión que pasó a aceptada vuelve a `propuesta` sin `aceptada_el`, y
  la que su aceptación dejó reemplazada vuelve como estaba (`Almacen.deshacer_estado`). Un merge
  a la rama principal **no se deshace**: tocar git así es destructivo; se avisa. Cada cosa
  queda en la bitácora de Cotejo y en la respuesta que ve la persona (`aviso`).

Lo que aprueba la persona en el board mientras el maestro contesta no se toca: el board lo
apunta aquí (`lo_aprueba_la_persona`) al escribirlo. Ese registro vive en la memoria del proceso
del board, donde el maestro no llega; un `cotejo maestro` de la CLI no lo ve, y una aprobación
hecha en un board abierto aparte durante ese turno se deshace igual (ante la duda, se escala:
la persona vuelve a aprobarla).
"""

import threading
import time

from tareas import almacen, bitacora, modelo

DESHACER = "candado"   # la operación con que queda en la bitácora
MOTIVO = "El maestro la intentó aprobar; aprobar es de una persona, en el board."
_APROBADAS = (modelo.HECHA, modelo.POR_INTEGRAR)

_cerrojo = threading.Lock()
_de_la_persona = {}   # id de tarea o de decisión → cuándo lo aprobó una persona en el board


def lo_aprueba_la_persona(*ids):
    """El board aprueba esto ahora (marca una tarea, la integra, acepta una decisión)."""
    with _cerrojo:
        for ident in ids:
            if ident:
                _de_la_persona[str(ident)] = time.time()


def _de_persona(ident, desde):
    with _cerrojo:
        return _de_la_persona.get(str(ident), 0) >= desde


def _estado(tarea):
    return modelo.HECHA if tarea.hecha else (tarea.estado or modelo.PENDIENTE)


# --- la foto -----------------------------------------------------------------------------------

def _proyecto(nombre):
    from tareas import cli
    fuente, proyectos, _ = cli.cargar()
    return fuente, [uno for uno in proyectos if uno.nombre == nombre]


def _tareas(nombre):
    try:
        _, proyectos = _proyecto(nombre)
    except Exception:  # noqa: BLE001 — sin foto se avisa al final; el turno sigue
        return None
    return {t.id: _estado(t) for uno in proyectos for t in list(uno.tareas) + list(uno.hechas)}


def _almacen(directorio):
    alm = almacen.Almacen(directorio) if directorio else None
    return alm if alm is not None and alm.existe() else None


def _decisiones(directorio):
    alm = _almacen(directorio)
    if alm is None:
        return {}
    return {e.id: {"estado": e.estado, "reemplazada_por": e.datos.get("reemplazada_por")}
            for e in alm.entradas("decision")}


def _git(repo, *args):
    from tareas import worktrees
    return worktrees._git(repo, *args)


def _principales(repo):
    """Las ramas que reciben las integraciones: `main`, `master`, la de `origin/HEAD` y la que
    esté abierta si no es de una tarea. `{rama: commit}` de las que existen."""
    from tareas import worktrees
    codigo, abierta, _ = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    nombres = {"main", "master", worktrees.rama_por_defecto(repo)}
    if codigo == 0 and abierta and not abierta.startswith("cotejo/"):
        nombres.add(abierta)
    salida = {}
    for rama in sorted(n for n in nombres if n):
        codigo, commit, _ = _git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{rama}")
        if codigo == 0 and commit:
            salida[rama] = commit
    return salida


def _ramas(directorio):
    from tareas import worktrees
    repo = worktrees.raiz_repo(directorio)
    if repo is None:
        return None
    codigo, salida, _ = _git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)",
                             "refs/heads/cotejo/")
    tareas = dict(l.split(" ", 1) for l in salida.splitlines() if " " in l) if codigo == 0 else {}
    return {"repo": str(repo), "principales": _principales(repo), "tareas": tareas}


def foto(proyecto, directorio):
    """Lo que hay aprobado antes de un turno del maestro: se guarda con el turno (JSON)."""
    return {"desde": time.time(), "proyecto": proyecto, "directorio": directorio,
            "tareas": _tareas(proyecto), "decisiones": _decisiones(directorio),
            "ramas": _ramas(directorio)}


# --- al terminar el turno ------------------------------------------------------------------------

def _revisar_tareas(foto_):
    antes, desde = foto_.get("tareas"), foto_.get("desde") or 0
    if antes is None:
        return [], [("las tareas", "no pude leerlas antes de que empezara")]
    try:
        fuente, proyectos = _proyecto(foto_["proyecto"])
    except Exception as error:  # noqa: BLE001
        return [], [("las tareas", str(error))]
    deshechas, fallos = [], []
    for uno in proyectos:
        for tarea in list(uno.tareas) + list(uno.hechas):
            previo = antes.get(tarea.id) or modelo.PENDIENTE
            if (_estado(tarea) not in _APROBADAS or previo in _APROBADAS
                    or _de_persona(tarea.id, desde)):
                continue
            try:
                actual = fuente.marcar(tarea, hecha=False) if tarea.hecha else tarea
                if (actual.estado or modelo.PENDIENTE) != previo:
                    actual = fuente.poner_estado(actual, previo)
            except Exception as error:  # noqa: BLE001 — se dice, no tumba el resto
                fallos.append((f"«{tarea.texto}» ({tarea.id})", str(error)))
                continue
            bitacora.anotar(DESHACER, uno, actual, de=_estado(tarea), a=previo, motivo=MOTIVO)
            deshechas.append(f"«{tarea.texto}» ({tarea.id})")
    return deshechas, fallos


def _revisar_decisiones(foto_):
    alm = _almacen(foto_.get("directorio"))
    if alm is None:
        return [], []
    antes, desde = foto_.get("decisiones") or {}, foto_.get("desde") or 0
    deshechas, fallos = [], []
    for entrada in alm.entradas("decision"):
        if (entrada.estado != "aceptada" or (antes.get(entrada.id) or {}).get("estado")
                == "aceptada" or _de_persona(entrada.id, desde)):
            continue
        try:
            alm.deshacer_estado(entrada.id, entrada.version, "propuesta", quitar=("aceptada_el",))
        except (almacen.EntradaCambiada, almacen.NoSeEdita, OSError) as error:
            fallos.append((f"la decisión {entrada.id}", str(error)))
            continue
        deshechas.append(entrada.id)
        bitacora.anotar_verbo(DESHACER, alm.raiz, tipo="decision", entrada=entrada.id,
                              de="aceptada", a="propuesta", motivo=MOTIVO)
    # La que la aceptación dejó reemplazada vuelve a como estaba.
    for entrada in alm.entradas("decision") if deshechas else ():
        previo = (antes.get(entrada.id) or {}).get("estado")
        if (entrada.estado == "reemplazada" and entrada.datos.get("reemplazada_por") in deshechas
                and previo in ("aceptada", "propuesta")):
            try:
                alm.deshacer_estado(entrada.id, entrada.version, previo,
                                    quitar=("reemplazada_por",))
            except (almacen.EntradaCambiada, almacen.NoSeEdita, OSError) as error:
                fallos.append((f"la decisión {entrada.id}", str(error)))
    return deshechas, fallos


def _ancestro(repo, commit, de):
    return _git(repo, "merge-base", "--is-ancestor", commit, de)[0] == 0


def _revisar_ramas(foto_):
    """Las ramas `cotejo/<id>` que entraron en una principal durante el turno, sin tocarlas."""
    antes = foto_.get("ramas")
    if not antes:
        return []
    repo, desde = antes["repo"], foto_.get("desde") or 0
    ahora = _principales(repo)
    _, salida, _ = _git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)",
                        "refs/heads/cotejo/")
    tareas = {**dict(l.split(" ", 1) for l in salida.splitlines() if " " in l),
              **(antes.get("tareas") or {})}
    metidas = []
    for principal, previo in (antes.get("principales") or {}).items():
        nuevo = ahora.get(principal)
        if not nuevo or nuevo == previo:
            continue
        for rama, commit in sorted(tareas.items()):
            ident = rama.split("/", 1)[1]
            if (_de_persona(ident, desde) or not _ancestro(repo, commit, nuevo)
                    or _ancestro(repo, commit, previo)):
                continue
            metidas.append((rama, principal))
            bitacora.anotar_verbo(DESHACER, repo, tipo="merge", rama=rama, destino=principal,
                                  motivo="El maestro integró la rama de una tarea; Cotejo no "
                                         "deshace git: lo revisa una persona.")
    return metidas


def revisar(foto_):
    """Deshace lo que el maestro aprobó durante el turno y devuelve el aviso para la persona
    («» si no tocó nada). Nunca levanta: un fallo al deshacer también se dice."""
    if not foto_:
        return ""
    try:
        tareas, fallos = _revisar_tareas(foto_)
    except Exception as error:  # noqa: BLE001
        tareas, fallos = [], [("las tareas", str(error))]
    try:
        decisiones, mas = _revisar_decisiones(foto_)
    except Exception as error:  # noqa: BLE001
        decisiones, mas = [], [("las decisiones", str(error))]
    try:
        ramas = _revisar_ramas(foto_)
    except Exception:  # noqa: BLE001
        ramas = []
    return aviso(tareas, decisiones, ramas, fallos + mas)


def aviso(tareas=(), decisiones=(), ramas=(), fallos=()):
    """Lo que se añade a la respuesta del maestro, en llano."""
    lineas = []
    if tareas:
        lineas.append(f"Intenté dar por hecha {', '.join(tareas)}; Cotejo lo deshizo: aprobar "
                      "es tuyo, en el board.")
    if decisiones:
        lineas.append(f"Intenté aceptar {', '.join(decisiones)}; Cotejo la devolvió a "
                      "propuesta: aceptar una decisión es tuyo, en el board.")
    for rama, principal in ramas:
        lineas.append(f"Metí la rama {rama} en {principal}. Cotejo no deshace git, pero "
                      "integrar es aprobar y eso es tuyo: revísalo antes de seguir.")
    for que, motivo in fallos:
        lineas.append(f"Cotejo no pudo comprobar o deshacer {que} ({motivo}): mira en el board "
                      "que no haya quedado nada aprobado sin ti.")
    return "\n".join(lineas)
