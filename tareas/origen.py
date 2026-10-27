"""De dónde salió un proyecto: si lo creó el Inicio del board (v1.3.0, cotejo-00fwc2).

Un proyecto creado desde el Inicio es de alguien que no programa: allí aprobar una entrega mete
su rama en la rama principal sin preguntar (`revision.integrar_sola`), y la persona nunca ve una
rama. Los de quien programa siguen con el diálogo de siempre (`ofrecer_integrar`).

La marca es `origen: inicio` en el frontmatter de `.cotejo/proyecto.md`: viaja con el repo (va en
el commit inicial de `init`), se ve y se quita a mano. La pone `cotejo init` solo cuando corre con
`COTEJO_ORIGEN=inicio` en el entorno, que es lo que lleva el agente que prepara el proyecto
(`inicio.ENTORNO`); ninguna persona ni agente la pide con una bandera. Un proyecto sin marca —todos
los de antes— sigue con el flujo de quien programa: nada se integra solo por adivinar.

**El agente del proyecto** (cotejo-qixs4j) viaja igual: `agente: codex` en el mismo frontmatter,
el cliente que la persona eligió al crearlo. Lo pone `init` con `COTEJO_AGENTE=<cliente>` en el
entorno (lo añade `enrutador/preparar.py` al del agente que lo prepara). Con él, las propuestas
del enrutador para ese proyecto son de ese agente (`niveles.del_cliente`) y el menú «Asignar a»
lo pone primero. Sin marca, Claude, como siempre.
"""

import os

from . import almacen

CLAVE = "origen"
CLAVE_AGENTE = "agente"
VARIABLE_AGENTE = "COTEJO_AGENTE"
INICIO = "inicio"
VARIABLE = "COTEJO_ORIGEN"


def es_del_inicio(raiz):
    """True si el proyecto de `raiz` lleva `origen: inicio`. Sin `proyecto.md`, o roto, False."""
    try:
        entrada = almacen.Almacen(raiz).leer(almacen.ID_PROYECTO)
    except (almacen.EntradaNoExiste, almacen.IdRepetido, OSError, ValueError):
        return False
    return str(entrada.datos.get(CLAVE) or "").strip().lower() == INICIO


def marcar_si_viene_del_inicio(raiz, entorno=None):
    """Lo que hace `init`: con `COTEJO_ORIGEN=inicio`, deja la marca si falta. Nunca la quita ni
    pisa otro `origen`. Devuelve True si la escribió ahora."""
    entorno = os.environ if entorno is None else entorno
    if (entorno.get(VARIABLE) or "").strip().lower() != INICIO:
        return False
    alm = almacen.Almacen(raiz)
    entrada = alm.leer(almacen.ID_PROYECTO)
    if entrada.datos.get(CLAVE) not in (None, ""):
        return False
    alm.reescribir(almacen.ID_PROYECTO, entrada.version, campos={CLAVE: INICIO})
    return True


def agente_de(raiz):
    """El agente con el que se creó el proyecto de `raiz` (`codex`, `gemini`…), o "" si no lo
    dice (entonces es Claude). Sin `proyecto.md`, o roto, ""."""
    if not raiz:
        return ""
    try:
        entrada = almacen.Almacen(raiz).leer(almacen.ID_PROYECTO)
    except (almacen.EntradaNoExiste, almacen.IdRepetido, OSError, ValueError):
        return ""
    return str(entrada.datos.get(CLAVE_AGENTE) or "").strip().lower()


def marcar_agente(raiz, entorno=None):
    """Lo que hace `init`: con `COTEJO_AGENTE=<cliente>`, deja `agente:` si falta. Nunca pisa
    otro. Devuelve True si lo escribió ahora."""
    entorno = os.environ if entorno is None else entorno
    agente = (entorno.get(VARIABLE_AGENTE) or "").strip().lower()
    if not agente or not agente.replace("-", "").replace("_", "").isalnum():
        return False
    alm = almacen.Almacen(raiz)
    entrada = alm.leer(almacen.ID_PROYECTO)
    if entrada.datos.get(CLAVE_AGENTE) not in (None, ""):
        return False
    alm.reescribir(almacen.ID_PROYECTO, entrada.version, campos={CLAVE_AGENTE: agente})
    return True
