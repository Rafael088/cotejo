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
        # Sin cliente pedido, el primero que haya en la máquina. Si no hay ninguno no se
        # inventa uno (ni `claude`): sin agente no hay maestro, ni siquiera para simularlo.
        # Es el mismo texto que el del board, y se dice antes de mirar tareas: un «asigna
        # tareas» no arreglaría nada.
        if not clientes.instalados():
            raise ErrorCLI(clientes.SIN_AGENTE, clientes.SIN_AGENTE_SALIDA)
        cliente = clientes.instalados()[0]
    try:
        elegido = clientes.de(cliente)
        nombre = maestro.resolver_proyecto(proyecto, cotejo.proyectos())
    except (clientes.ClienteDesconocido, maestro.SinProyecto) as error:
        raise ErrorCLI(str(error), "Mira los proyectos con `cotejo estado`.") from error
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

    directorio = cfg.directorio_de(config, nombre) or cotejo.carpeta_de(nombre)
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


