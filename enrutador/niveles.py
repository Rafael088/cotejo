"""Qué niveles hay, qué modelo atiende cada uno y cuál no atiende ningún modelo.

Aquí no hay tareas, ni notas, ni subprocesos: solo el catálogo. Lo que decide *qué* nivel le
toca a una tarea está en `decision.py`; lo que la ejecuta, en `motores/`.

El nivel que más importa es el que no lleva modelo. Al medir las 105 tareas reales del vault
apareció el caso que ninguna versión del diseño contemplaba: «Comprar el dominio miempresa.co»,
«Que un abogado revise los textos», «Sacar la API key de Anthropic». Un enrutador que solo
elige entre haiku, sonnet y opus manda *todas* esas a un modelo, y el modelo las toma, las
intenta y las entrega a medias. Por eso `humano` es un destino de primera clase: la decisión
correcta para una tarea puede ser «esto no lo hace ningún modelo», y hace falta poder decirlo.

Los precios son los de la API de Anthropic y salen de la skill `claude-api` (tabla del
2026-10-06, familia 5.5), no de memoria. Están aquí para que `modelos` y `plan` puedan poner un número
delante de una decisión; no se cobran por este camino —`claude -p` factura por la suscripción
de Claude Code— así que lo que dan es la *proporción* entre niveles, que es lo que justifica
enrutar. Si cambian, se cambian aquí y en ningún otro sitio.
"""

from dataclasses import dataclass

HUMANO = "humano"


@dataclass(frozen=True)
class Nivel:
    """Un destino posible. `modelo` es el alias que entiende `claude --model`.

    Se guardan las dos formas del nombre a propósito: el alias (`opus`) es lo que sobrevive a
    que Anthropic saque un modelo nuevo sin que haya que tocar la config de nadie, y el id
    exacto (`claude-opus-5-5`) es lo que hace falta para hablar de precios y para dejar en la
    bitácora qué atendió de verdad esta tarea y no cuál era el alias ese día.
    """

    clave: str
    modelo: str          # alias para `claude --model`; "" en el nivel humano
    modelo_id: str       # id exacto de la API, para precios y bitácora
    entrada_mtok: float  # USD por millón de tokens de entrada
    salida_mtok: float   # USD por millón de tokens de salida
    para_que: str
    cliente: str = "claude"  # cliente que sabe ejecutar `modelo_id`, si aplica
    nivel_base: str = ""  # tamaño equivalente en los modelos personalizados
    # Argumentos extra para el cliente con este modelo (p. ej. `-c model_reasoning_effort=high`
    # en Codex): van después de `-m` y antes del prompt, en todos los motores.
    argumentos: tuple = ()

    @property
    def despachable(self):
        return bool(self.modelo)


NIVELES = (
    Nivel("n0", "", "", 0.0, 0.0,
          "Lo que ningún modelo puede hacer: comprar, firmar, llamar a alguien, tocar algo "
          "físico, abrir una cuenta o decidir por ti."),
    Nivel("n1", "haiku", "claude-haiku-5-5", 0.10, 0.50,
          "Trabajo mecánico y acotado: anotar, renombrar, cambiar un print, documentar un paso "
          "que ya sabes."),
    Nivel("n2", "sonnet", "claude-sonnet-5-5", 2.0, 10.0,
          "El trabajo normal de código: un cambio en uno o dos archivos, con sus pruebas. Es "
          "también el default seguro."),
    Nivel("n3", "opus", "claude-opus-5-5", 4.0, 20.0,
          "Arquitectura, contratos, cambios que cruzan varios archivos y lo que haya que "
          "diseñar antes de escribir."),
)

# Los de fábrica de los otros agentes (v1.3.0, cotejo-qixs4j): lo justo para que un proyecto hecho
# con Codex, OpenCode, Gemini o Antigravity tenga a quién proponer sin registrar nada a mano, y
# sin inventar ningún id. Gemini CLI entiende alias estables (`pro`, `flash`, `flash-lite`), como
# Claude Code. OpenCode y Antigravity no: su entrada de fábrica es **el modelo que el agente tenga
# por defecto** (`modelo_id` vacío: se lanza sin `-m`), que vale para cualquier nivel, y los
# modelos concretos se añaden con «Añadir modelo» o `cotejo modelos agregar`. Codex sí lista sus
# modelos con nombre exacto (`codex debug models` / `~/.codex/models_cache.json`): los cuatro de
# la cuenta van abajo, de pequeño a grande, para que n1/n2/n3 y el menú no dependan de un id
# inventado. Un modelo registrado con la misma clave gana a estos (no son reservados: no se rompe
# la config de nadie).
DE_FABRICA = (
    Nivel("gemini-flash-lite", "gemini-flash-lite", "flash-lite", 0.0, 0.0,
          "Gemini CLI, su modelo ligero (alias flash-lite).", "gemini", "n1"),
    Nivel("gemini-flash", "gemini-flash", "flash", 0.0, 0.0,
          "Gemini CLI, su modelo rápido (alias flash).", "gemini", "n2"),
    Nivel("gemini-pro", "gemini-pro", "pro", 0.0, 0.0,
          "Gemini CLI, su modelo grande (alias pro).", "gemini", "n3"),
    # Codex (cotejo-ef3xzj): los nombres reales de la cuenta, leídos de su catálogo (los que
    # `codex debug models` marca `visibility: list`). Van de pequeño a grande: `grupos` los
    # invierte para enseñar el grande primero y `del_cliente` se queda, entre dos del mismo
    # tamaño, con el último (el más capaz, nunca el más barato).
    Nivel("gpt-5.6-luna", "gpt-5.6-luna", "gpt-5.6-luna", 0.0, 0.0,
          "Codex, su modelo ligero (gpt-5.6-luna).", "codex", "n1"),
    Nivel("gpt-5.6-terra", "gpt-5.6-terra", "gpt-5.6-terra", 0.0, 0.0,
          "Codex, su modelo rápido (gpt-5.6-terra).", "codex", "n2"),
    Nivel("gpt-5.6-sol", "gpt-5.6-sol", "gpt-5.6-sol", 0.0, 0.0,
          "Codex, su modelo para el trabajo normal (gpt-5.6-sol).", "codex", "n2"),
    Nivel("gpt-6-astra", "gpt-6-astra", "gpt-6-astra", 0.0, 0.0,
          "Codex, su modelo grande (gpt-6-astra).", "codex", "n3"),
    Nivel("opencode", "opencode", "", 0.0, 0.0,
          "OpenCode con el modelo que tenga por defecto.", "opencode", "n3"),
    # Antigravity CLI (cotejo-r4yg0n), como OpenCode: el modelo que tenga elegido (sin
    # `--model`). Qué slugs hay depende del plan de cada cuenta (`agy models`): los concretos
    # se añaden con «Añadir modelo», nunca un id de fábrica que en otra cuenta no exista.
    Nivel("antigravity", "antigravity", "", 0.0, 0.0,
          "Antigravity CLI con el modelo que tenga elegido.", "antigravity", "n3"),
)

POR_CLAVE = {n.clave: n for n in NIVELES}
POR_MODELO = {n.modelo: n for n in NIVELES if n.modelo}

# Los nombres con los que se asignaron tareas a Codex antes de tener sus modelos reales
# (cotejo-ef3xzj). Se resuelven al equivalente de hoy sin tocar el vault ni la config: `codex`
# era el tamaño normal, `codex-rapido` el ligero y `codex-fuerte` el grande.
ALIAS_DE_ANTES = {
    "codex-rapido": "gpt-5.6-luna",
    "codex": "gpt-5.6-sol",
    "codex-fuerte": "gpt-6-astra",
}

# Cómo se llama cada nivel en el tag `#agente/<x>` de Cotejo. `persona` es el nivel humano: quien
# se asigne una tarea a sí mismo ya está diciendo «esto no es para un modelo».
AGENTE_A_NIVEL = {"haiku": "n1", "sonnet": "n2", "opus": "n3", "persona": "n0"}

HUMANO_NIVEL = POR_CLAVE["n0"]
DEFECTO = POR_CLAVE["n2"]


def personalizados(definiciones=()):
    """Construye niveles de modelos registrados en la config, sin modificar los integrados."""
    if all(isinstance(definicion, Nivel) for definicion in definiciones or ()):
        return tuple(definiciones)
    salida = []
    for definicion in definiciones or ():
        clave = str(definicion.get("clave", "")).strip().lower()
        salida.append(Nivel(
            clave=clave,
            modelo=clave,
            modelo_id=str(definicion.get("modelo_id", "")).strip(),
            entrada_mtok=float(definicion.get("entrada_mtok", 0.0)),
            salida_mtok=float(definicion.get("salida_mtok", 0.0)),
            para_que=definicion.get("nombre") or definicion.get("para_que") or
                     f"Modelo registrado para {definicion.get('cliente', 'otro')}",
            cliente=definicion.get("cliente", "otro"),
            nivel_base=definicion.get("nivel", "n2"),
            argumentos=tuple(str(a) for a in definicion.get("argumentos") or ()),
        ))
    return tuple(salida)


def _de_fabrica(propios):
    """Los de fábrica de otros agentes que no tapa un modelo registrado con la misma clave."""
    tapados = {n.clave for n in propios}
    return tuple(n for n in DE_FABRICA if n.clave not in tapados)


def disponibles(definiciones=()):
    """Los niveles integrados, los de fábrica de los otros agentes y los que añadió el usuario."""
    propios = personalizados(definiciones)
    return NIVELES + _de_fabrica(propios) + propios


def agentes(definiciones=()):
    """Nombres que puede mostrar CotejoBoard en el menú de asignación (sin agrupar: los de
    Claude, los registrados y `persona`, como siempre). Agrupado por agente, `grupos`."""
    integrados = ("opus", "sonnet", "haiku")
    propios = tuple(n.modelo for n in personalizados(definiciones) if n.modelo)
    return integrados + propios + ("persona",)


ORDEN_CLAUDE = ("opus", "sonnet", "haiku")


def grupos(definiciones=(), listos=None, primero=""):
    """El menú de «Asignar a» por agente (v1.3.0, cotejo-qixs4j): `[(cliente, [nombres])]`.

    Salen los agentes de `listos` (instalados y con sesión, `modelos_vivos.listos()`), con
    `primero` (el agente del proyecto) delante y Claude después; cada uno con sus modelos de
    fábrica y los registrados. Un modelo registrado para un cliente que Cotejo no conoce
    (`otro`) sale siempre, al final: de ese no se sabe si tiene sesión. Sin ningún agente listo
    (una máquina sin agentes, la CI) salen todos, como antes: el board sigue sirviendo para
    asignar.
    """
    propios = personalizados(definiciones)
    from . import clientes
    conocidos = list(clientes.CLIENTES)
    listos = list(conocidos if not listos else [c for c in conocidos if c in listos])
    orden = [c for c in dict.fromkeys([primero, "claude", *conocidos]) if c in listos]
    salida = []
    for cliente in orden:
        nombres = (list(ORDEN_CLAUDE) if cliente == "claude" else
                   [n.modelo for n in _de_fabrica(propios) if n.cliente == cliente][::-1])
        nombres += [n.modelo for n in propios if n.cliente == cliente and n.modelo]
        if nombres:
            salida.append((cliente, list(dict.fromkeys(nombres))))
    otros = [n.modelo for n in propios if n.cliente not in conocidos and n.modelo]
    if otros:
        salida.append(("otro", otros))
    return salida


def del_cliente(nivel, cliente, definiciones=()):
    """El modelo de `cliente` para el tamaño de `nivel` (el agente del proyecto, cotejo-qixs4j).

    Primero un registrado de ese cliente con ese nivel; si no, el de fábrica más capaz de ese
    tamaño; si no hay de ese tamaño, el más pequeño de los que son **más grandes** (ante la duda
    se escala, nunca se abarata) y, si tampoco, `nivel` tal cual. Con Claude, o sin cliente,
    `nivel` tal cual.
    """
    if not cliente or cliente == "claude" or not nivel.despachable:
        return nivel
    propios = personalizados(definiciones)
    fabrica = _de_fabrica(propios)
    # Un registrado manda. Entre los de fábrica del mismo tamaño se queda el último, que es el
    # más capaz (van de pequeño a grande): ante la duda se escala, nunca se abarata.
    exactos_propios = [n for n in propios if n.cliente == cliente
                       and (n.nivel_base or n.clave) == nivel.clave]
    if exactos_propios:
        return exactos_propios[0]
    exactos_fabrica = [n for n in fabrica if n.cliente == cliente
                       and (n.nivel_base or n.clave) == nivel.clave]
    if exactos_fabrica:
        return exactos_fabrica[-1]
    candidatos = propios + fabrica
    mayores = sorted((n for n in candidatos if n.cliente == cliente
                      and (n.nivel_base or "n2") > nivel.clave),
                     key=lambda n: n.nivel_base or "n2")
    return mayores[0] if mayores else nivel


def por_nombre(nombre, extras=(), alias_persona=None):
    """El nivel que responde a ese nombre, sea la clave (`n2`) o el alias (`sonnet`).

    Devuelve None en vez de levantar: quien llama sabe mejor que este módulo si un nombre
    desconocido es un error del usuario o una config vieja, y qué decirle.

    `alias_persona` es una lista de nombres adicionales que se tratan como #agente/persona
    (por defecto solo ["persona"]).
    """
    nombre = (nombre or "").strip().lower()
    alias_persona = alias_persona or ["persona"]
    persona_names = set([HUMANO, "persona"] + alias_persona)
    if nombre in persona_names:
        return HUMANO_NIVEL
    propios = personalizados(extras)
    por_clave = {n.clave: n for n in propios + _de_fabrica(propios)}
    por_modelo = {n.modelo: n for n in propios + _de_fabrica(propios) if n.modelo}

    def resolver(nombre):
        return (POR_CLAVE.get(nombre) or POR_MODELO.get(nombre) or por_clave.get(nombre)
                or por_modelo.get(nombre))

    nivel = resolver(nombre)
    if nivel is None and nombre in ALIAS_DE_ANTES:
        nivel = resolver(ALIAS_DE_ANTES[nombre])
    return nivel


def _instalado(cliente):
    from . import clientes
    return clientes.esta_instalado(cliente)


def catalogo(definiciones=()):
    """El catálogo como JSON, que es lo que devuelve el verbo `modelos`."""
    return [{"nivel": n.clave, "modelo": n.modelo or HUMANO, "modelo_id": n.modelo_id,
             "cliente": n.cliente if n.despachable else "",
             "nivel_base": n.nivel_base or n.clave,
             "argumentos": list(n.argumentos),
             "despachable": n.despachable,
             "cliente_instalado": _instalado(n.cliente) if n.despachable else None,
             "para_que": n.para_que,
             "usd_por_mtok": {"entrada": n.entrada_mtok, "salida": n.salida_mtok}}
            for n in disponibles(definiciones)]
