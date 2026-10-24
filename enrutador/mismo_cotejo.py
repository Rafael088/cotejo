"""El agente que lanza el board usa el mismo Cotejo que el board (v1.3.0, cotejo-w7oeio).

El agente de «Preparar» (y el de «Abrir en terminal») llama a `cotejo` por su nombre: así lo
pide el prompt y así lo deja pasar `--allowedTools Bash(cotejo:*)`. Si en el PATH hay otro
Cotejo —el instalado cuando la persona prueba el board del repo con `cotejo-dev`, o una versión
vieja que quedó en `~/.local/bin`—, el agente hablaba con ese, que puede no tener los verbos que
el prompt nombra (`anotar --pieza`) ni escribir los pasos donde los lee la pantalla Preparando.

Por eso, antes de lanzar, se escribe un **lanzador** `cotejo` en `<estado>/agente/bin` que
ejecuta el código de este mismo proceso —`sys.executable` con la carpeta de donde se importó
`tareas`— y esa carpeta va primera en el PATH del agente. Vale igual instalado (el Python del
sistema y el paquete instalado), en desarrollo (el checkout de `cotejo-dev`) y en un paquete
que traiga su propio Python (AppImage, Windows): en los tres, `sys.executable` y `tareas.__file__`
son los que está corriendo el board. Se reescribe en cada lanzamiento, así que siempre apunta al
board que lanzó, y vive en la carpeta de estado de ese board (la de `cotejo-dev` es otra).

`otro` mira qué `cotejo` habría encontrado el agente sin el lanzador y, si es de otra versión,
lo deja anotado para que Preparando lo diga en llano (`tareas.preparando.aviso_otro_cotejo`). No cambia nada de la persona:
el otro Cotejo sigue donde estaba.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tareas
from tareas import __version__

NOMBRE = "cotejo"


def carpeta():
    """Dónde va el lanzador: en la carpeta de estado del board que lanza, al lado de las
    preparaciones (`<estado>/agente/bin`)."""
    from tareas import preparacion
    return Path(preparacion.CARPETA).parent / "agente" / "bin"


def raiz():
    """La carpeta desde la que se importó el paquete `tareas` (y `enrutador`) de este proceso."""
    return Path(tareas.__file__).resolve().parent.parent


def _escribir(ruta, texto, ejecutable=False):
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(texto, encoding="utf-8")
    if ejecutable:
        temporal.chmod(0o755)
    os.replace(temporal, ruta)


def preparar_lanzador(destino=None):
    """Escribe el lanzador y devuelve su carpeta. Es idempotente y atómico."""
    destino = Path(destino) if destino is not None else carpeta()
    destino.mkdir(parents=True, exist_ok=True)
    python = sys.executable or "python3"
    _escribir(destino / "lanzador.py", (
        "# Lo escribe Cotejo antes de lanzar un agente: el mismo Cotejo que el board.\n"
        "import sys\n"
        f"sys.path.insert(0, {str(raiz())!r})\n"
        "sys.argv[0] = 'cotejo'\n"
        "from tareas.__main__ import main\n"
        "sys.exit(main())\n"))
    lanzador = destino / "lanzador.py"
    if os.name == "nt":
        _escribir(destino / f"{NOMBRE}.cmd", f'@"{python}" "{lanzador}" %*\r\n')
    else:
        from shlex import quote
        _escribir(destino / NOMBRE, (
            "#!/bin/sh\n"
            "# Lo escribe Cotejo antes de lanzar un agente: el mismo Cotejo que el board.\n"
            f"exec {quote(python)} {quote(str(lanzador))} \"$@\"\n"), ejecutable=True)
    return destino


def _sin(path, quitar):
    """El PATH sin la carpeta del lanzador (por si ya venía de un lanzamiento anterior)."""
    quitar = os.path.normcase(os.path.abspath(quitar))
    return os.pathsep.join(p for p in (path or "").split(os.pathsep)
                           if p and os.path.normcase(os.path.abspath(p)) != quitar)


def entorno(extra=None, base=None, destino=None):
    """Las variables que se añaden al entorno del agente: `extra` (p. ej. `COTEJO_FUENTE`) y un
    PATH con el lanzador primero. Escribe el lanzador."""
    base = os.environ if base is None else base
    bin_ = preparar_lanzador(destino)
    return {**(extra or {}),
            "PATH": os.pathsep.join(filter(None, [str(bin_), _sin(base.get("PATH", ""), bin_)]))}


def _version(ruta):
    try:
        salida = subprocess.run([ruta, "--version"], capture_output=True, text=True, timeout=10,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"\d+\.\d+(?:\.\d+)?\S*", (salida.stdout or "") + (salida.stderr or ""))
    return m.group(0) if m else ""


def otro(base=None, destino=None):
    """El `cotejo` que el agente habría usado sin el lanzador, si es de otra versión que este:
    `{"ruta", "version", "esta"}`; `None` si no hay otro o es la misma versión."""
    base = os.environ if base is None else base
    destino = Path(destino) if destino is not None else carpeta()
    ruta = shutil.which(NOMBRE, path=_sin(base.get("PATH", ""), destino))
    if not ruta:
        return None
    version = _version(ruta)
    if version == __version__:
        return None
    return {"ruta": ruta, "version": version, "esta": __version__}


__all__ = ["carpeta", "raiz", "preparar_lanzador", "entorno", "otro"]
