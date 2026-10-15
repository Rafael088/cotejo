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
2026-06-24), no de memoria. Están aquí para que `modelos` y `plan` puedan poner un número
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
    exacto (`claude-opus-5`) es lo que hace falta para hablar de precios y para dejar en la
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

    @property
    def despachable(self):
        return bool(self.modelo)


NIVELES = (
    Nivel("n0", "", "", 0.0, 0.0,
          "Lo que ningún modelo puede hacer: comprar, firmar, llamar a alguien, tocar algo "
          "físico, abrir una cuenta o decidir por ti."),
    Nivel("n1", "haiku", "claude-haiku-4-5", 1.0, 5.0,
          "Trabajo mecánico y acotado: anotar, renombrar, cambiar un print, documentar un paso "
          "que ya sabes."),
    Nivel("n2", "sonnet", "claude-sonnet-5", 2.0, 10.0,
          "El trabajo normal de código: un cambio en uno o dos archivos, con sus pruebas. Es "
          "también el default seguro."),
    Nivel("n3", "opus", "claude-opus-5", 5.0, 25.0,
          "Arquitectura, contratos, cambios que cruzan varios archivos y lo que haya que "
          "diseñar antes de escribir."),
)

POR_CLAVE = {n.clave: n for n in NIVELES}
POR_MODELO = {n.modelo: n for n in NIVELES if n.modelo}

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
        ))
    return tuple(salida)


def disponibles(definiciones=()):
    """Los niveles integrados y los modelos que añadió el usuario."""
    return NIVELES + personalizados(definiciones)


def agentes(definiciones=()):
    """Nombres que puede mostrar CotejoBoard en el menú de asignación."""
    integrados = ("opus", "sonnet", "haiku")
    propios = tuple(n.modelo for n in personalizados(definiciones) if n.modelo)
    return integrados + propios + ("persona",)


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
    por_clave = {n.clave: n for n in propios}
    por_modelo = {n.modelo: n for n in propios if n.modelo}
    return POR_CLAVE.get(nombre) or POR_MODELO.get(nombre) or por_clave.get(nombre) or \
        por_modelo.get(nombre)


def _instalado(cliente):
    from . import clientes
    return clientes.esta_instalado(cliente)


def catalogo(definiciones=()):
    """El catálogo como JSON, que es lo que devuelve el verbo `modelos`."""
    return [{"nivel": n.clave, "modelo": n.modelo or HUMANO, "modelo_id": n.modelo_id,
             "cliente": n.cliente if n.despachable else "",
             "nivel_base": n.nivel_base or n.clave,
             "despachable": n.despachable,
             "cliente_instalado": _instalado(n.cliente) if n.despachable else None,
             "para_que": n.para_que,
             "usd_por_mtok": {"entrada": n.entrada_mtok, "salida": n.salida_mtok}}
            for n in disponibles(definiciones)]
