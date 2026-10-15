"""El maestro: un agente abierto en una terminal que reparte las tareas asignadas de un proyecto.

Es el caso «ponte con las tareas de este proyecto» sin tener que escribirlo: una persona elige un
proyecto en CotejoBoard, pulsa el botón y elige con qué cliente (Claude Code, OpenCode, Codex…).
Se abre ese cliente **en una terminal que se ve**, con una primera instrucción: despachar, una a
una, las tareas pendientes que una persona ya asignó a un modelo, cada una con el cliente que
ejecuta ese modelo (`despachar --motor headless`).

Por qué así y no de otra manera:

- **Solo las asignadas.** Que un modelo haga una tarea lo decide una persona escribiendo
  `#agente/<modelo>`; las reglas solo proponen. El maestro no usa `--auto` ni `--modelo`, y
  `despachar` se niega de todos modos con lo que no está asignado.
- **En una terminal, nunca en segundo plano.** El motor por defecto no lanza nada porque mandar
  trabajo a un proceso que nadie ve es justo lo que no se quería. El maestro es una persona
  pidiéndolo con un botón, y lo que se abre se puede leer, interrumpir y corregir.
- **El maestro tampoco finaliza.** Reparte y comprueba que cada modelo entregó; si uno no pudo
  (se quedó sin permisos, se cortó), el maestro mira qué hizo y entrega con evidencia o bloquea
  con motivo. `[x]` sigue siendo de una persona.

Aquí no se lanza nada: se arma la instrucción y la línea de comandos. Lanzar es de `motores/`.
"""

from . import clientes


class SinProyecto(Exception):
    pass


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


def instruccion(proyecto, asignadas, directorio=None, indicacion=""):
    """Lo que lee el maestro al abrirse. `asignadas` son filas de `plan --solo-asignadas`.

    `indicacion` es lo que la persona le escribió al abrirlo (la barra del maestro en el board,
    `--indicacion` en la CLI). Va después de la lista y antes de las reglas: acota qué repartir
    o en qué orden, pero no le da permiso para saltarse ninguna de ellas.
    """
    comillas = f'"{proyecto}"'
    lista = "\n".join(f"  - {t['id']} → {t['modelo']}: {t['texto']}" for t in asignadas)
    partes = [
        f"Eres el maestro de las tareas del proyecto «{proyecto}» en Cotejo. Tu trabajo es "
        f"repartirlas a los modelos que tienen asignados y comprobar que las entregan; no las "
        f"hagas tú.",
        "",
        f"Te tocan solo las pendientes que una persona ya asignó a un modelo. Ahora mismo son "
        f"{len(asignadas)}:",
        lista,
        "",
        f"Si pasa un rato, vuelve a mirarlas: cotejo plan --proyecto {comillas} --solo-asignadas",
    ]
    indicacion = " ".join((indicacion or "").split())
    if indicacion:
        partes += [
            "",
            f"La persona te dejó esta indicación al abrirte: «{indicacion}». Síguela para elegir "
            "cuáles repartir y en qué orden, siempre dentro de las reglas de abajo: si pide algo "
            "que no está en la lista de arriba (una tarea sin modelo asignado, por ejemplo), no lo "
            "despaches y díselo al final.",
        ]
    if directorio:
        partes.append(f"El proyecto vive en {directorio}; trabaja ahí.")
    else:
        partes.append(
            "Cotejo no sabe en qué carpeta vive el código de este proyecto (falta en "
            "enrutador.proyectos de la config), y cada despacho corre donde estés tú. Antes "
            "de despachar nada, pregúntale a la persona en qué carpeta trabajar y muévete ahí.")
    partes += [
        "",
        "Para cada una, despáchala a su modelo. Cotejo lanza el cliente que lo ejecuta "
        "(claude -p, opencode run, codex exec, gemini -p) y le pasa el encargo:",
        "",
        "    cotejo despachar <id> --motor headless",
        "",
        "Cada despacho espera a que el modelo termine (hasta 30 minutos). Si puedes correr "
        "comandos en segundo plano, lanza varios a la vez, pero no dos que toquen los mismos "
        "archivos; si no, uno tras otro. Antes de cada tanda pregunta cuántos caben en esta "
        "máquina sin llevarla al OOM, y lanza solo esos (con caben 0, espera a que vuelva "
        "alguno):",
        "",
        f"    cotejo capacidad --proyecto {comillas}",
        "",
        "No despaches nada más: ni las que no tienen modelo asignado ni las de una persona, y "
        "sin --auto ni --modelo —el modelo lo eligió una persona—. Si despachar se niega, "
        "déjala y di por qué al final.",
        "",
        "Cuando vuelva cada despacho, comprueba que el modelo la entregó:",
        "",
        f"    cotejo tareas --proyecto {comillas} --estado por-validar",
        "",
        "Si no la entregó, mira qué hizo —su salida viene en el JSON de despachar; en el "
        "proyecto, git status y git diff— y:",
        "  - si está hecha y lo puedes demostrar: cotejo entregar <id> --evidencia \"...\"",
        "  - si no: cotejo bloquear <id> --motivo \"qué falta y qué haría falta\"",
        "",
        "No la marques como hecha: no hay verbo para eso y es a propósito. [x] lo pone una "
        "persona en CotejoBoard después de comprobar.",
        "",
        "Al terminar, resume en pocas líneas qué se entregó, qué se bloqueó y por qué.",
    ]
    return "\n".join(partes)


def argv(cliente, prompt, modelo="", terminal=()):
    """La línea de comandos que abre el cliente con la instrucción, dentro de la terminal."""
    return list(terminal) + clientes.de(cliente).argv_interactivo(prompt, modelo)
