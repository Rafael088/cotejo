"""Qué es «mandarle la tarea a un modelo», sin decir todavía a través de qué.

Misma frontera que la capa Fuente de Cotejo, por la misma razón: mientras «despachar» signifique
«lanzar `claude -p`», el enrutador solo sirve en una máquina con Claude Code instalado. Con la
interfaz en medio, mandar la tarea por otra vía —un servicio, una cola, otra herramienta— es un
archivo nuevo en `motores/` y una clave en la config.

El registro es un diccionario explícito y no un `importlib` que recorra la carpeta. Un import
dinámico deja de encontrar los módulos en cuanto el proyecto se congela en un binario, que es
exactamente a donde va Cotejo; un diccionario los referencia y el empaquetador los ve.
"""

from dataclasses import dataclass, field


@dataclass
class Encargo:
    """Lo que se le manda a un modelo: qué hacer, quién lo hace y dónde."""

    prompt: str
    modelo: str
    modelo_id: str = ""
    directorio: object = None   # Path o None (None = donde estés)
    tarea_id: str = ""
    proyecto: str = ""
    cliente: str = "claude"     # quién sabe ejecutar el modelo (ver `clientes.py`)


@dataclass
class Resultado:
    ok: bool
    comando: list = field(default_factory=list)
    codigo: int = 0
    salida: str = ""
    error: str = ""
    duracion_ms: int = 0
    ejecutado: bool = True   # falso en los motores que no llegan a lanzar nada


class Motor:
    """Lo que tiene que saber hacer un motor. Cuatro líneas, a propósito."""

    nombre = ""

    # Si `ejecutar()` abre de verdad un cliente de IA que no se puede deshacer (un proceso, una
    # instancia). Los motores con esto en `True` no se llaman en un ensayo (`--simular`): en su
    # lugar se enseña `argv()`, que es lo único que les hace falta implementar aparte para eso.
    # `agente` y `simulado` se quedan en `False` porque su `ejecutar()` ya no lanza nada de por
    # sí, ensayo o no.
    LANZA = False

    def __init__(self, ajustes=None):
        self.ajustes = ajustes or {}
        # Lo que `despachar` quiere saber en cuanto el proceso existe, antes de que termine:
        # `al_lanzar(pid, comando)`. Solo lo llaman los motores que lanzan y esperan (headless);
        # si el proceso muere sin volver, esa anotación es lo único que queda de él.
        self.al_lanzar = None

    def ejecutar(self, encargo):  # pragma: no cover - interfaz
        raise NotImplementedError

    def comprobar(self, encargo):
        """Lo que impediría lanzar este encargo, en castellano, o "" si nada.

        `despachar` lo pregunta **antes** de tomar la tarea: si el cliente del modelo no está
        instalado, descubrirlo después deja la tarea en «Haciéndola» a nombre de alguien que
        nunca llegó a empezar.
        """
        return ""


def registro():
    """Los motores disponibles, por nombre."""
    from .motores import agente, claude_cli, sesion, simulado
    return {
        agente.Agente.nombre: agente.Agente,
        sesion.Sesion.nombre: sesion.Sesion,
        claude_cli.ClaudeCLI.nombre: claude_cli.ClaudeCLI,
        simulado.Simulado.nombre: simulado.Simulado,
    }


class MotorDesconocido(Exception):
    pass


def abrir(nombre, config):
    disponibles = registro()
    clase = disponibles.get(nombre)
    if clase is None:
        raise MotorDesconocido(
            f"«{nombre}» no es un motor. Los que hay: {', '.join(sorted(disponibles))}.")
    return clase((config.get("motores") or {}).get(nombre, {}))
