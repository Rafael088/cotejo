"""Las guardas de fábrica en el PATH del agente que lanza el board (v1.3.0, cotejo-7yfw1e).

El agente que lanza el board tiene terminal libre en el worktree de su tarea (dec-kiik) y una
lista corta de prohibidos que cada cliente niega a su manera (`clientes.Cliente.terminal_libre`).
Esos son patrones sobre el texto del comando; debajo, para los cuatro clientes por igual, va esta
carpeta primera en el PATH (`<estado>/agente/guardas`, al lado del lanzador de `mismo_cotejo`):

- **`git`**: el `git` de verdad (`COTEJO_GIT_REAL`, buscado antes de tocar el PATH) salvo un
  `push` a la fuerza o a `main`/la rama por defecto, que se rechaza con el motivo en llano
  (`guarda_git.py`, que lee los argumentos de verdad: `git -C x push -uf`, `git push` a secas con
  la rama de destino en `main`…).
- **`sudo`, `su`, `doas`, `pkexec`**: se niegan y dicen por qué (fuera de Windows).
- **`gemini.toml`**: la política que Gemini CLI recibe con `--policy`
  (`clientes.politica_gemini_toml`).

No sustituyen a lo que niega cada cliente: quien llame a `/usr/bin/sudo` por su ruta se las
salta. Se reescriben en cada lanzamiento, como el lanzador de `cotejo`, y no tocan nada de la
persona.
"""

import os
import shutil
import sys
from pathlib import Path
from shlex import quote

from . import clientes, mismo_cotejo

ESCALAR = clientes.ESCALAR
POLITICA_GEMINI = "gemini.toml"


def carpeta():
    """`<estado>/agente/guardas`, junto al `bin` del lanzador de `cotejo`."""
    return mismo_cotejo.carpeta().parent / "guardas"


def _escribir(ruta, texto, ejecutable=False):
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(texto, encoding="utf-8")
    if ejecutable:
        temporal.chmod(0o755)
    os.replace(temporal, ruta)


def preparar(ramas=None, destino=None):
    """Escribe las guardas y la política de Gemini para estas ramas y devuelve la carpeta."""
    destino = Path(destino) if destino is not None else carpeta()
    destino.mkdir(parents=True, exist_ok=True)
    python = sys.executable or "python3"
    script = Path(__file__).resolve().with_name("guarda_git.py")
    if os.name == "nt":
        _escribir(destino / "git.cmd", f'@"{python}" -I -S "{script}" %*\r\n')
    else:
        _escribir(destino / "git", (
            "#!/bin/sh\n"
            "# Lo escribe Cotejo antes de lanzar un agente desde el board.\n"
            f"exec {quote(python)} -I -S {quote(str(script))} \"$@\"\n"), ejecutable=True)
        for orden in ESCALAR:
            _escribir(destino / orden, (
                "#!/bin/sh\n"
                "# Lo escribe Cotejo antes de lanzar un agente desde el board.\n"
                f"echo {quote(f'Cotejo: «{orden}» está prohibido. ' + clientes.AVISO)} >&2\n"
                "exit 126\n"), ejecutable=True)
    _escribir(destino / POLITICA_GEMINI, clientes.politica_gemini_toml(ramas))
    return destino


def politica_gemini(destino=None):
    return (Path(destino) if destino is not None else carpeta()) / POLITICA_GEMINI


def entorno(previo, ramas=None, base=None, destino=None):
    """`previo` (lo que ya se añade al entorno del agente, con su PATH si lo trae) con la carpeta
    de las guardas primera en el PATH, el `git` de verdad en `COTEJO_GIT_REAL` y las ramas
    protegidas en `COTEJO_RAMAS_PROTEGIDAS`. Escribe las guardas."""
    base = os.environ if base is None else base
    carpeta_ = preparar(ramas, destino)
    path = (previo or {}).get("PATH", base.get("PATH", ""))
    quitar = os.path.normcase(os.path.abspath(carpeta_))
    resto = [p for p in path.split(os.pathsep)
             if p and os.path.normcase(os.path.abspath(p)) != quitar]
    real = shutil.which("git", path=os.pathsep.join(resto)) or ""
    return {**(previo or {}),
            "PATH": os.pathsep.join([str(carpeta_), *resto]),
            "COTEJO_GUARDAS": str(carpeta_),
            "COTEJO_GIT_REAL": real,
            "COTEJO_RAMAS_PROTEGIDAS": ",".join(clientes.ramas_protegidas(ramas))}


__all__ = ["carpeta", "preparar", "politica_gemini", "entorno"]
