"""Los clientes de IA que saben ejecutar un modelo, y cómo se les habla desde la línea de comandos.

El catálogo guarda de cada modelo **qué cliente lo ejecuta** (`claude`, `opencode`, `codex`…),
pero hasta aquí nadie usaba ese dato: los motores lanzaban `claude` siempre, así que despachar
una tarea asignada a `#agente/kimi-k2.7-code` acababa en `claude --model kimi-k2.7-code`, que no
existe. Este módulo es la tabla que faltaba: con qué se le pide una tarea a cada cliente sin
interfaz (lo que usa el motor `headless`) y con qué se le abre en una terminal con una primera
instrucción (lo que usa `maestro`).

Aquí no se lanza nada —eso sigue siendo solo de `motores/`—; solo se arman listas de argumentos.

Dos formas de nombrar el modelo, igual que en `niveles.Nivel`: Claude Code entiende el alias
(`opus`), que sobrevive a que salga un modelo nuevo; el resto quiere el id que entiende su
proveedor (`opencode-go/kimi-k2.7-code`).
"""

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Cliente:
    nombre: str
    ejecutable: str
    # Sin interfaz: <ejecutable> <sin_interfaz> <modelo> <extra> <prompt_sin_interfaz> <prompt>
    sin_interfaz: tuple
    bandera_modelo: str
    prompt_sin_interfaz: tuple = ()
    # En una terminal, con una primera instrucción y la sesión abierta para seguir hablando.
    prompt_interactivo: tuple = ()
    usa_alias: bool = False
    titulo: str = ""   # cómo se llama en el board

    def modelo_de(self, modelo, modelo_id):
        """El nombre del modelo tal como lo entiende este cliente."""
        if self.usa_alias:
            # Un alias de Claude (`opus`) si lo es; si es un modelo de Claude registrado a
            # mano, su id.
            from .niveles import POR_MODELO
            return modelo if modelo in POR_MODELO else (modelo_id or modelo)
        return modelo_id or modelo

    def argv_sin_interfaz(self, modelo, prompt, comando=None, extra=()):
        return (list(comando or [self.ejecutable]) + list(self.sin_interfaz) +
                [self.bandera_modelo, modelo] + list(extra) +
                list(self.prompt_sin_interfaz) + [prompt])

    def argv_interactivo(self, prompt, modelo="", comando=None, extra=()):
        con_modelo = [self.bandera_modelo, modelo] if modelo else []
        return (list(comando or [self.ejecutable]) + con_modelo + list(extra) +
                list(self.prompt_interactivo) + [prompt])

    @property
    def instalado(self):
        return shutil.which(self.ejecutable) is not None


CLIENTES = {
    "claude": Cliente("claude", "claude", ("-p",), "--model", usa_alias=True,
                      titulo="Claude Code"),
    "opencode": Cliente("opencode", "opencode", ("run",), "-m",
                        prompt_interactivo=("--prompt",), titulo="OpenCode"),
    "codex": Cliente("codex", "codex", ("exec",), "-m", titulo="Codex"),
    "gemini": Cliente("gemini", "gemini", (), "-m", prompt_sin_interfaz=("-p",),
                      prompt_interactivo=("-i",), titulo="Gemini CLI"),
}


class ClienteDesconocido(Exception):
    pass


def de(nombre):
    """El cliente con ese nombre. Levanta con los que sí hay, para que el error diga qué hacer."""
    cliente = CLIENTES.get((nombre or "claude").strip().lower())
    if cliente is None:
        raise ClienteDesconocido(
            f"No sé cómo lanzar el cliente «{nombre}». Los que sé: "
            f"{', '.join(sorted(CLIENTES))}.")
    return cliente


def instalados():
    """Los nombres de los clientes que esta máquina tiene en el PATH, en el orden de la tabla."""
    return [nombre for nombre, cliente in CLIENTES.items() if cliente.instalado]


def esta_instalado(nombre):
    """¿Está en el PATH el cliente con ese nombre? Un cliente registrado a mano que esta tabla
    no conoce se busca por su nombre, que es lo único que de él se sabe."""
    cliente = CLIENTES.get((nombre or "").strip().lower())
    return cliente.instalado if cliente else shutil.which(nombre or "") is not None


# Lo que dicen el board y `cotejo maestro` cuando no hay ningún agente de terminal: una sola
# fuente para que digan lo mismo. No se inventa un comando de instalación: cada agente se
# instala como dice su propia documentación.
SIN_AGENTE = "El maestro necesita un agente de terminal y no encontré ninguno"
SIN_AGENTE_SALIDA = ("Instala uno (Claude Code, Codex, Gemini CLI u opencode) y vuelve a probar; "
                     "mientras tanto puedes trabajar las tareas desde cualquier agente con MCP")
SIN_AGENTE_TEXTO = f"{SIN_AGENTE}. {SIN_AGENTE_SALIDA}."


def aviso_sin_agentes():
    """El aviso de que esta máquina no tiene ningún agente de terminal, o "" si hay alguno.

    Es un aviso y no un error: Cotejo funciona sin maestro, y la decisión del enrutador no
    depende de la máquina (`despachable` no cambia). Solo dice que despachar no llegaría a nada.
    """
    if instalados():
        return ""
    return (f"No encontré ningún agente de terminal ({', '.join(CLIENTES)}) en el PATH: "
            f"puedes ver, decidir y entregar tareas, pero despachar o abrir el maestro "
            f"necesita instalar uno.")
