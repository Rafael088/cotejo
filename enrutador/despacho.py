"""Las piezas de `despachar` que no son el orden de los pasos: qué se comprueba antes de tomar
la tarea, con qué motivo se suelta si el cliente falla y qué se le dice a quien despachó.

Viven aparte de `verbos.py` para que el verbo se lea de arriba abajo como lo que es —decidir,
comprobar, tomar, lanzar, contar— y para que añadir una comprobación previa sea tocar este
archivo y no la mitad de `cmd_despachar`.
"""

from tareas import worktrees
from tareas.cli import ErrorCLI

# Cuánto de lo que dijo el cliente cabe en el motivo de soltar: es texto para una carta del
# board y para el siguiente encargo, no el volcado entero (ese queda en la bitácora de
# despachos, en «salida» y «error»).
MOTIVO_MAX = 400


def antes_de_tomar(motor_elegido, encargo, plan_wt):
    """Lo que impediría lanzar este despacho, como pares `(rechazo, problema)`; nada si nada.

    `despachar` rechaza con el primero **antes** de tomar la tarea, que es lo que la deja
    pendiente e intacta. Una comprobación nueva (que el repo tenga commits, por ejemplo) es un
    `yield` más aquí, con su propia clave de rechazo para la bitácora de despachos; `plan_wt`
    es el worktree que se crearía (None si no se aísla) y `encargo.directorio`, dónde se va a
    trabajar.
    """
    problema = motor_elegido.comprobar(encargo)
    if problema:
        yield "motor", problema
    # Sin commits no hay HEAD y `git worktree add` falla con «referencia inválida: HEAD» y un
    # consejo que no apunta a la causa (v1.2.5). Solo importa si se va a aislar.
    if plan_wt and worktrees.sin_commits(plan_wt["repo"]):
        yield "sin_commits", (f"El repo {plan_wt['repo']} no tiene ningún commit: haz uno "
                              f"(`git commit --allow-empty -m inicial`) y vuelve a despachar.")


def motivo_del_fallo(motor_nombre, resultado):
    """Por qué se suelta una tarea cuyo cliente falló, con lo que dijo él, recortado."""
    dicho = " ".join(" ".join(
        parte for parte in (resultado.error, resultado.salida) if parte).split())
    if len(dicho) > MOTIVO_MAX:
        dicho = dicho[:MOTIVO_MAX - 1].rstrip() + "…"
    return (f"El despacho con --motor {motor_nombre} falló (código {resultado.codigo})"
            + (f": {dicho}" if dicho else ", sin decir por qué."))


def soltar_si_fallo(cotejo, tarea_id, motor_nombre, resultado, modelo, asignada, avisos):
    """Suelta la tarea que tomó un despacho cuyo cliente falló. Devuelve si la soltó.

    Sin esto quedaba «Haciéndola» a nombre de un modelo que no la iba a hacer y sin decir por
    qué (cotejo-fyj565). El motivo es lo que dijo el cliente, recortado. Solo se suelta si
    sigue en curso a nombre de `modelo`: si el cliente la entregó o la bloqueó antes de salir
    con error, eso se respeta; y si la línea cambió mientras corría, no se pisa y se avisa.
    """
    try:
        return cotejo.soltar(tarea_id, motivo_del_fallo(motor_nombre, resultado),
                             agente=modelo, asignada=asignada)
    except ErrorCLI as error:
        avisos.append(f"No pude soltar la tarea tras el fallo del cliente: {error}")
        return False


def nota(tarea_id, modelo, motor_nombre, ensayo, ok, soltada):
    """La `nota_para_el_agente` de `despachar`: qué hacer ahora con lo que acaba de pasar."""
    if ensayo:
        return (f"Simulado con --motor {motor_nombre}: no se tomó la tarea ni se ejecutó "
                f"nada.")
    if not ok:
        # Nunca «Instancia abierta» ni «ya está tomada» cuando no lo está (cotejo-fyj565).
        return (f"El cliente de {modelo} falló y nadie está haciendo la tarea. "
                + ("Se soltó: vuelve a estar pendiente, con lo que dijo el cliente como motivo. "
                   "Arregla eso (o usa otro --motor) antes de despacharla otra vez."
                   if soltada else
                   f"No se soltó porque ya no estaba «Haciéndola» a nombre de {modelo}: mira "
                   f"en CotejoBoard cómo quedó."))
    cierre = (f"El enrutador no entrega: cuando esté hecha, `cotejo entregar {tarea_id} "
              f"--evidencia \"...\"`; si no se pudo, `bloquear` con el motivo.")
    if motor_nombre == "agente":
        # Con `agente` nadie se pone a trabajar solo: si quien despachó es una persona en una
        # terminal y no un agente, la tarea se queda «Haciéndola» sin nadie detrás.
        return (f"La tarea ya quedó tomada en Cotejo a nombre de {modelo}, y el encargo está en "
                f"«salida». Si ese es el modelo en el que corres, ponte con ella. Si no, "
                f"pásasela a quien sí —un subagente con ese modelo, o `--motor sesion`—, porque "
                f"una sesión no puede cambiarse de modelo a sí misma. Si quien despachó es una "
                f"persona y no un agente que la vaya a hacer, devuélvela ya con `cotejo bloquear "
                f"{tarea_id} --motivo \"...\"`, o se queda «Haciéndola» sin que nadie la haga. "
                + cierre)
    if motor_nombre == "sesion":
        return (f"Instancia abierta en {modelo}, trabajando por su cuenta. Ábrela con `claude "
                f"attach` si quieres verla; el resultado aparece en CotejoBoard, no aquí.")
    return f"La tarea quedó tomada por {modelo}. " + cierre
