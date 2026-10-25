"""Qué hacer con la ficha abierta cuando el board se repinta (v1.3.0, cotejo-v66btg).

La ficha de una tarea (detalle o revisión) se arma con la tarea tal como estaba al abrirla. Si
mientras está abierta la tarea cambia de columna —el agente entrega, termina sin entregar, alguien
la mueve—, la cabecera y las acciones quedan viejas. Aquí está la decisión, sin GTK: dada la
ficha abierta y las tareas recién leídas, decir si sigue igual, si hay que mostrarla en el estado
nuevo o si la tarea ya no está. La ventana (`app/detalle.py`) solo ejecuta lo que se decide.
"""

from . import modelo

DETALLE = "detalle"
REVISION = "revision"

IGUAL = "igual"
CAMBIA = "cambia"
DESAPARECE = "desaparece"


def vista_de(tarea, hay_entrega):
    """Qué ficha le toca a la tarea ahora: la revisión si está en Para comprobar con una
    entrega que revisar (como al pulsarla en el board), y el detalle en cualquier otro caso."""
    if tarea.columna == "por-validar" and hay_entrega:
        return REVISION
    return DETALLE


def buscar(proyectos, tarea_id):
    """(proyecto, tarea) con ese id, entre las pendientes y las hechas; None si no está.
    Compara con el prefijo de ahora (`foco-x` y `cotejo-x` son la misma tarea)."""
    buscado = modelo.id_actual(tarea_id)
    if not buscado:
        return None
    for proyecto in proyectos:
        for tarea in list(proyecto.tareas) + list(proyecto.hechas):
            if modelo.id_actual(tarea.id) == buscado:
                return proyecto, tarea
    return None


def decidir(abierta, proyectos, hay_entrega):
    """Qué hacer con la ficha `abierta` = (id, vista, columna) ante las `proyectos` recién leídas.

    Devuelve `(IGUAL,)`, `(CAMBIA, proyecto, tarea, vista)` o `(DESAPARECE,)`. Cambia si la tarea
    cambió de columna o si ahora le toca otra ficha (le llegó la entrega estando en Para
    comprobar). `hay_entrega(tarea)` dice si hay una entrega que revisar.
    """
    tarea_id, vista, columna = abierta
    hallada = buscar(proyectos, tarea_id)
    if hallada is None:
        return (DESAPARECE,)
    proyecto, tarea = hallada
    nueva = vista_de(tarea, hay_entrega(tarea))
    if tarea.columna != columna or nueva != vista:
        return (CAMBIA, proyecto, tarea, nueva)
    return (IGUAL,)
