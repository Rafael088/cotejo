"""El maestro: una conversación dentro del board con un agente que conoce el proyecto.

Desde la 1.3.0 (cotejo-9ybn1a, decisión del dueño del 2026-10-27) el maestro ya no abre una
terminal. La persona le escribe en lenguaje llano en la barra del pie de CotejoBoard y ve la
conversación en la app: le pide **añadir tareas** («apunta que falta el login»), **pregunta por el
proyecto** («qué falta», «cómo va», «qué hace la pieza Fuente») y le pide **repartir lo
asignado**. Cada mensaje es un turno de un cliente sin interfaz (`conversacion.py`) que solo
puede correr `cotejo`; este módulo arma lo que lee en cada turno, sin E/S.

Por qué así y no de otra manera:

- **Nunca una terminal.** Una terminal es una ventana fuera de la app que la persona no sabe
  leer ni cerrar sin miedo, y que trabaja donde el board no lo ve. La conversación es la misma
  persona pidiéndolo, con lo que hace a la vista en el board.
- **Repartir lo hace el board, no el agente.** El maestro no lanza agentes: si la persona le
  pide repartir, termina su respuesta con una línea `REPARTIR: <ids>` y el board le enseña un
  botón para lanzarlas por el mismo camino que mover una carta a Haciendo (con su ficha en
  vivo, su worktree y la capacidad de la máquina). Solo valen las pendientes que **una persona
  asignó a un modelo** (`asignadas`): ni las sin modelo ni las de una persona, y Cotejo vuelve
  a filtrar lo que el agente proponga (`pedidas`).
- **Tampoco finaliza ni entrega.** Puede apuntar trabajo (`cotejo crear`), porque apuntar no
  afirma que esté hecho; entregar es de quien hizo la tarea y `[x]` es de una persona.
"""

import re


class SinProyecto(Exception):
    pass


# La línea con la que el maestro pide repartir. Va sola, al final de su respuesta; el board la
# quita del texto y en su lugar enseña el botón.
MARCA_REPARTIR = "REPARTIR:"
_RE_REPARTIR = re.compile(r"^[\s*`>-]*REPARTIR\s*:(.*)$", re.IGNORECASE | re.MULTILINE)
_RE_ID = re.compile(r"[a-z]+-[a-z0-9]{4,}", re.IGNORECASE)

# Cuántos turnos anteriores lee el maestro, y hasta cuántos caracteres de cada uno: la
# conversación viaja entera en cada turno (no todos los clientes tienen una forma documentada
# de retomar su sesión sin interfaz), así que se recorta para que no crezca sin tope.
TURNOS_DE_MEMORIA = 12
CARACTERES_POR_TURNO = 2000


def resolver_proyecto(nombre, nombres):
    """El nombre exacto del proyecto pedido: el idéntico si lo hay, si no el único que lo contenga."""
    buscado = (nombre or "").strip().lower()
    exactos = [n for n in nombres if n.lower() == buscado]
    if exactos:
        return exactos[0]
    parecidos = [n for n in nombres if buscado and buscado in n.lower()]
    if len(parecidos) == 1:
        return parecidos[0]
    if not parecidos:
        raise SinProyecto(f"No hay ningún proyecto que se llame «{nombre}».")
    raise SinProyecto(f"«{nombre}» puede ser {', '.join(parecidos)}: di cuál.")


def _recorte(texto):
    texto = (texto or "").strip()
    if len(texto) <= CARACTERES_POR_TURNO:
        return texto
    return texto[:CARACTERES_POR_TURNO] + " […]"


def instruccion(proyecto, asignadas, directorio=None, pedido="", historia=()):
    """Lo que lee el maestro en un turno. `asignadas` son filas `{id, modelo, texto}` de las
    pendientes que una persona asignó a un modelo; `historia`, los turnos anteriores
    (`{"quien": "persona"|"maestro", "texto"}`); `pedido`, lo que la persona acaba de escribir.
    """
    comillas = f'"{proyecto}"'
    repo = f" --repo \"{directorio}\"" if directorio else ""
    partes = [
        f"Eres el maestro del proyecto «{proyecto}» en Cotejo y hablas con su dueño dentro de "
        "CotejoBoard, en una conversación. Contesta en español, en lenguaje llano y corto: "
        "quien te lee puede no programar. No hay terminal: lo que respondas es lo que se ve.",
        "",
        "Puedes hacer tres cosas:",
        "",
        "1. Añadir tareas al proyecto cuando te lo pidan, una por cada cosa que hacer:",
        f"       cotejo crear \"<qué hay que hacer>\" --proyecto {comillas}",
        "   Di cuáles apuntaste, con su id.",
        "2. Contestar preguntas sobre el proyecto (qué falta, cómo va, qué hace una pieza). "
        "Míralo con la CLI antes de contestar, no lo adivines:",
        f"       cotejo tareas --proyecto {comillas} [--estado pendiente|en-curso|por-validar]",
        f"       cotejo contexto{repo}",
        f"       cotejo buscar --tipo arquitectura{repo}   ·   cotejo leer <id>{repo}",
        "   Si hace falta, lee el código del proyecto; no lo modifiques.",
        "3. Repartir lo asignado, si te lo piden. No lances nada tú: termina la respuesta con "
        "una línea sola así, y el board le enseñará a la persona un botón para repartirlas:",
        f"       {MARCA_REPARTIR} <id> <id> …",
        "   Solo valen las pendientes que una persona ya asignó a un modelo"
        + (":" if asignadas else ", y ahora mismo no hay ninguna: dilo y explica que se "
           "asignan en el board, en ⋮ → Asignar a."),
    ]
    partes += [f"       - {t['id']} → {t['modelo']}: {t['texto']}" for t in asignadas]
    partes += [
        "",
        "No hagas nada más: no edites archivos, no hagas commits, no despaches ni tomes "
        "tareas, no entregues ni bloquees las de otros. No hay verbo para marcar una tarea "
        "como hecha y es a propósito: [x] lo pone una persona en el board.",
    ]
    if directorio:
        partes.append(f"El código del proyecto vive en {directorio}.")
    else:
        partes.append("Cotejo no sabe en qué carpeta vive el código de este proyecto; si te "
                      "preguntan por el código, dilo en vez de buscarlo.")
    recientes = [t for t in historia if (t.get("texto") or "").strip()][-TURNOS_DE_MEMORIA:]
    if recientes:
        partes += ["", "La conversación hasta ahora:"]
        for turno in recientes:
            quien = "Persona" if turno.get("quien") == "persona" else "Maestro"
            partes.append(f"[{quien}] {_recorte(turno.get('texto'))}")
    pedido = (pedido or "").strip()
    partes += ["", "Ahora la persona te dice:",
               pedido or "(nada: preséntate en una frase y di qué puedes hacer)"]
    return "\n".join(partes)


def pedidas(respuesta, asignadas):
    """Los ids que el maestro pidió repartir (`REPARTIR:`) y que de verdad están asignados.

    El agente propone; el filtro es de Cotejo: un id que no esté en `asignadas` —una tarea sin
    modelo, una de una persona, una que ya no está pendiente— no sale nunca, lo diga quien lo
    diga. En el orden en que los pidió y sin repetir.
    """
    validos = {t["id"] for t in asignadas}
    vistos = []
    for linea in _RE_REPARTIR.findall(respuesta or ""):
        for ident in _RE_ID.findall(linea):
            if ident in validos and ident not in vistos:
                vistos.append(ident)
    return vistos


def sin_marca(respuesta):
    """La respuesta sin las líneas `REPARTIR:`: lo que se le enseña a la persona."""
    return _RE_REPARTIR.sub("", respuesta or "").strip()
