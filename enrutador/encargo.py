"""El texto que recibe el modelo al que se le manda una tarea.

Un encargo no es el texto de la tarea a secas. Un modelo que recibe «Arreglar el medidor de
ahorro» y nada más empieza por averiguar dónde está el medidor, qué es Cotejo y si puede tocar el
vault — y eso es exactamente el contexto que este enrutador existe para no pagar tres veces.

Así que el encargo trae lo que el modelo necesitaba preguntar: qué tarea es y cómo se llama,
qué proyecto, dónde trabajar, por qué le tocó a él, si la tarea vuelve rechazada y con qué
motivo, y cómo se cierra el ciclo en Cotejo. Todo eso son unos 300 tokens que ahorran varias
vueltas de exploración.

Lo que el encargo **no** dice es cómo hacer la tarea. Quien decide eso es el modelo, que para
eso se eligió.

Sí lleva, si quien despacha la pone, **una nota suya**. Hizo falta el primer día de uso real: la
tarea decía «crear el repo del enrutador» y el repo ya existía, así que mandarla tal cual era
pedir que se rehiciera trabajo bueno. Lo que faltaba no estaba en la tarea —estaba en la cabeza
de quien reparte—, y sin un sitio donde ponerlo la única salida era saltarse el enrutador y
lanzar el proceso a mano. La nota va al final y aparte, para que se lea como lo que es: el
contexto de hoy, no el enunciado.
"""

from tareas.como_se_abre import FORMATO as COMO_SE_ABRE

from . import navegador

MANTENER_COMO_SE_ABRE = """Si tu trabajo cambia cómo se abre la app (el comando, la dirección o lo que se ve al
abrirla), actualiza la sección «## Cómo se abre» de la arquitectura del proyecto: el botón «Ver
mi app» de la persona la usa tal cual. `cotejo contexto` te da el id de la arquitectura; luego
`cotejo leer <arq-id>` y `cotejo editar <arq-id> --version <hash> --texto "..."` con el texto
entero. Si aún no la tiene y ya sabes cómo se abre, añádela. El formato:

""" + COMO_SE_ABRE

CIERRE = """Cuando termines, entrégala en Cotejo con evidencia que otro pueda repetir —los
archivos que tocaste, el comando de las pruebas con su salida, el hash del commit—:

    cotejo entregar {id} --evidencia "..."

{capturas}Si te atascasSi te atascas, no la dejes a medias: devuélvela con el motivo, que es lo que evita que el
siguiente se estrelle contra lo mismo:

    cotejo bloquear {id} --motivo "qué lo impide y qué haría falta"

No la marques como hecha. No hay verbo para eso y es a propósito: `[x]` lo pone una persona en
CotejoBoard después de comprobar."""


CON_NAVEGADOR = """Si tu trabajo se ve (una web, una app, una pantalla), saca capturas con un navegador sin
interfaz (el comando, si hace falta, va en la nota de arriba) —una en móvil (~390×844) y otra en
escritorio (~1280×800)— y pásalas al entregar, una `--captura` por PNG: Cotejo las guarda y
quien comprueba las ve grandes sin abrir nada.

    cotejo entregar {id} --evidencia "..." --captura movil.png --captura escritorio.png

"""

SIN_NAVEGADOR = """Si tu trabajo se ve (una web, una app, una pantalla), en esta máquina no hay navegador
sin interfaz para sacarle capturas: no las pidas ni las inventes. Dilo en la entrega y propón a
la persona instalar Firefox.

"""


def cierre(id_, navegador_disponible=None):
    """El cierre del encargo; pide capturas solo si hay con qué sacarlas."""
    hay = (navegador.disponible_para_el_agente() if navegador_disponible is None
           else navegador_disponible)
    return CIERRE.format(id=id_, capturas=(CON_NAVEGADOR if hay else SIN_NAVEGADOR).format(id=id_))


def armar(tarea, decision, directorio=None, nota="", worktree=None):
    """El encargo completo, en el orden en que le sirve a quien lo lee.

    Con `worktree` (B3), la carpeta de trabajo es la suya y no la del repo: decirle solo «el
    proyecto vive en X» lo mandaría a trabajar en el árbol que comparten todos.
    """
    partes = [
        f"Tarea de Cotejo {tarea.get('id', '')} — proyecto {tarea.get('proyecto', '?')}.",
        "",
        tarea.get("texto", "").strip(),
        "",
        f"Ya está tomada a tu nombre ({decision.nivel.modelo}), así que la columna dice que la "
        f"estás haciendo: empieza por el trabajo, no por tomarla.",
        f"Te tocó a ti porque {decision.razon}.",
    ]
    if worktree:
        partes.append(
            f"Trabaja en {worktree['ruta']}, el worktree de esta tarea (rama {worktree['rama']}), "
            f"no en {worktree['repo']}: esa carpeta y esa rama son solo tuyas. Haz ahí tus "
            f"commits y entrega desde ahí.")
    elif directorio:
        partes.append(f"El proyecto vive en {directorio}; trabaja ahí.")
    if tarea.get("motivo"):
        partes += [
            "",
            "Esta tarea volvió atrás. Lee por qué antes de rehacerla, o terminará igual:",
            f"  {tarea['motivo'].strip()}",
        ]
    if tarea.get("evidencia"):
        partes += ["", f"Lo que se entregó la vez anterior: {tarea['evidencia'].strip()}"]
    if nota:
        partes += ["", "Lo que añade quien te reparte la tarea, y que no está en su enunciado:",
                   "", nota.strip()]
    partes += ["", MANTENER_COMO_SE_ABRE, "", cierre(tarea.get("id", "<id>"))]
    return "\n".join(partes)
