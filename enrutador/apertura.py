"""Abrir el maestro de un proyecto: la parte de `abrir_maestro` que no necesita `verbos`.

Vive aparte porque `verbos.py` está congelado en su tope de líneas (`test_tamano_de_modulos`).
`verbos.abrir_maestro` sigue siendo la puerta que usan la CLI y CotejoBoard: prepara la config
y las reglas y llama aquí.
"""

from tareas.cli import ESQUEMA, ErrorCLI
from . import clientes, config as cfg, decision, maestro
from .motores import terminal

# Mismo valor que `verbos.LO_DIJO_UNA_PERSONA`: una persona lo dijo (override o asignación).
LO_DIJO_UNA_PERSONA = ("override", "asignacion")


def abrir(config, cotejo, humano, nivel, propios, proyecto, cliente, modelo, simular,
          indicacion):
    pedido = bool(cliente)
    if not pedido:
        # Sin cliente pedido, el primero que haya en la máquina; si no hay ninguno, `claude`
        # solo para poder armar el ensayo (no se le nombra a nadie como si lo hubiera pedido).
        cliente = (clientes.instalados() or ["claude"])[0]
    try:
        elegido = clientes.de(cliente)
        nombre = maestro.resolver_proyecto(proyecto, cotejo.proyectos())
    except (clientes.ClienteDesconocido, maestro.SinProyecto) as error:
        raise ErrorCLI(str(error), "Mira los proyectos con `cotejo estado`.") from error
    if not pedido and not simular and not clientes.instalados():
        # Antes de mirar tareas: sin agente no hay maestro que abrir, y decirlo primero evita
        # un «asigna tareas» que no arregla nada.
        raise ErrorCLI(clientes.aviso_sin_agentes(),
                       "Instala uno (por ejemplo Claude Code) y repite `cotejo maestro`; "
                       "`--simular` enseña qué abriría sin necesitarlo.")
    ajustes = config.get("maestro") or {}
    if modelo is None:
        modelo = (ajustes.get("modelos") or {}).get(elegido.nombre, "")

    asignadas = []
    for tarea in cotejo.tareas(nombre, "pendiente"):
        if tarea.get("proyecto") != nombre:
            continue
        elegida = decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                                    niveles_extra=propios,
                                    alias_persona=config.get("alias_persona"))
        if elegida.por in LO_DIJO_UNA_PERSONA and elegida.despachable:
            asignadas.append({"id": tarea.get("id"), "texto": tarea.get("texto"),
                              "modelo": elegida.nivel.modelo, "cliente": elegida.nivel.cliente})
    if not asignadas:
        raise ErrorCLI(f"«{nombre}» no tiene tareas pendientes asignadas a un modelo",
                       "Asígnalas antes —en CotejoBoard, ⋮ → Asignar a, o "
                       "`cotejo asignar <id> <modelo>`—: el maestro solo reparte lo que una "
                       "persona ya asignó.")

    directorio = cfg.directorio_de(config, nombre)
    comando = maestro.argv(elegido.nombre,
                           maestro.instruccion(nombre, asignadas, directorio, indicacion),
                           modelo, ajustes.get("terminal") or ())
    faltan = sorted({t["cliente"] for t in asignadas
                     if t["cliente"] in clientes.CLIENTES
                     and not clientes.CLIENTES[t["cliente"]].instalado}
                    | ({t["cliente"] for t in asignadas} - set(clientes.CLIENTES)))
    salida = {"esquema": ESQUEMA, "proyecto": nombre, "cliente": elegido.nombre,
              "modelo": modelo, "directorio": str(directorio) if directorio else None,
              "asignadas": asignadas, "comando": comando, "abierto": False}
    if indicacion:
        salida["indicacion"] = " ".join(indicacion.split())
    if faltan:
        salida["clientes_que_faltan"] = faltan
    if simular:
        return salida
    if not elegido.instalado:
        raise ErrorCLI(f"«{elegido.nombre}» no está instalado en esta máquina",
                       f"Los que sí: {', '.join(clientes.instalados()) or 'ninguno'}.")
    try:
        terminal.abrir(comando, directorio)
    except terminal.SinTerminal as error:
        raise ErrorCLI(str(error), "Luego repite `cotejo maestro`.") from error
    salida["abierto"] = True
    return salida


