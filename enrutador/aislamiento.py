"""Aislar en su propio *scope* de systemd el proceso que lanza un headless (cotejo-flccw4).

Un headless que se desboca en memoria —un bucle sin salida, un contexto enorme— puede tirar un
OOM del kernel, y el OOM killer no distingue a quién mata dentro del mismo *cgroup*: si cae el
proceso del maestro, o el de otro headless que estaba trabajando bien, una tarea ajena se pierde
por culpa de la que se desbocó. `systemd-run --user --scope` mete el proceso en su propio
*cgroup* con un tope de memoria (`MemoryMax`) y le dice a systemd que, si el OOM killer actúa
ahí dentro, no se lleve detrás la unidad entera (`OOMPolicy=continue`): el límite y la muerte se
quedan dentro del scope de ese headless.

Solo en Linux, y solo si hay un systemd de usuario que de verdad contesta: `systemd-run` puede
estar instalado y aun así no servir —sin haber iniciado sesión, sin `loginctl enable-linger`, en
un contenedor sin init—, y ahí **no** hay que envolver nada, porque systemd-run fallaría en cada
despacho y el headless dejaría de funcionar donde antes sí. En Windows, en macOS o sin esa
sesión, se lanza el proceso tal cual se hacía antes de esta tarea.

`--scope` hace que `systemd-run` ejecute el comando **en su propio proceso** (`execve`, no un
hijo nuevo que lance aparte): el pid que `subprocess.Popen` devuelve para "systemd-run ..."
termina siendo, en cuanto el exec ocurre, el pid real del cliente (comprobado a mano: lanzar
`systemd-run --user --scope -- sleep N` y mirar que `$!` es el pid de `sleep`, no el de
systemd-run). Por eso quien anota el lanzamiento (`Motor.al_lanzar`, en
`enrutador/motores/claude_cli.py`) tiene que seguir recibiendo el argv **del cliente**, nunca el
de systemd-run: si `programa` pasara a ser `"systemd-run"`, `enrutador/procesos.vivo` compararía
un pid que de verdad sigue vivo contra `/proc/<pid>/cmdline`, que después del exec ya es el del
cliente, y `revisar` daría la tarea por perdida estando en marcha. `claude_cli.py` no le pasa a
`al_lanzar` el argv que de verdad se ejecuta (el que devuelve `envolver`), sino el original; este
módulo no toca esa costura, solo construye el prefijo.
"""

import os
import shutil
import subprocess
import sys
import uuid


def disponible():
    """Si esta máquina puede aislar: Linux, `systemd-run` en el `PATH` y una sesión que contesta.

    `systemctl --user is-system-running` no lanza nada: solo pregunta. "running" es lo normal;
    "degraded" significa que alguna unidad de usuario falló pero el manager sigue contestando, y
    contestar es lo único que hace falta para poder crear un scope.
    """
    if not sys.platform.startswith("linux") or shutil.which("systemd-run") is None:
        return False
    try:
        resultado = subprocess.run(
            ["systemctl", "--user", "--no-pager", "is-system-running"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return resultado.stdout.strip() in {"running", "degraded"}


def _nombre_unidad(tarea_id):
    """Un nombre de unidad legible en `systemctl --user list-units`, y único por lanzamiento.

    Sin el sufijo, dos despachos seguidos de la misma tarea (un reintento) chocarían contra una
    unidad que systemd todavía no terminó de limpiar.
    """
    base = "".join(c if c.isalnum() or c in ":_.-" else "_" for c in (tarea_id or "tarea"))
    return f"cotejo-headless-{base}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def envolver(comando, ajustes, tarea_id=""):
    """El argv con el que lanzar `comando`: con el prefijo de systemd-run, o el mismo si no toca.

    `ajustes` es `motores.headless` tal cual llega al motor (`Motor.ajustes`), no el de un
    cliente dentro de `motores.headless.clientes`: ese solo trae el binario y sus argumentos, y
    el aislamiento es una propiedad de cómo se lanza un headless, no de cuál.
    """
    comando = list(comando)
    if ajustes.get("aislar", True) is False or not disponible():
        return comando
    memoria_max = ajustes.get("memoria_max") or "50%"
    return (["systemd-run", "--user", "--scope", "--quiet",
             f"--unit={_nombre_unidad(tarea_id)}",
             "-p", f"MemoryMax={memoria_max}", "-p", "OOMPolicy=continue", "--"]
            + comando)
