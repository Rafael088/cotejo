"""Cotejo del repo, con sus datos aparte: lo que se usa para desarrollar.

    python3 herramientas/cotejo_dev.py [lo mismo que a `cotejo`]

El Cotejo de todos los días es la versión publicada, instalada como cualquier usuario; este es
el del código que se está tocando. Para que uno no pise al otro, el de desarrollo:

- usa el código de **este** checkout (el repo o el worktree donde vive este archivo), nunca la
  instalación;
- lee y escribe en su propia carpeta (`<estado>/../cotejo-dev`, en Linux
  `~/.local/state/cotejo-dev`): config, estado, bitácora, `board.json` y worktrees;
- trabaja sobre un vault de prueba (`herramientas/vault_prueba.py`), que crea la primera vez;
- abre el board con otro APP_ID, así que convive con el board publicado en vez de traerlo al
  frente (GTK es de instancia única por APP_ID).

Cada variable se pone solo si no viene puesta: `COTEJO_VAULT=/otro/vault cotejo-dev tareas`
apunta a otro vault en una sola invocación, como con el comando de siempre.
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_ID_DEV = "io.github.cotejoapp.CotejoDev"


def preparar():
    """Pone el entorno del Cotejo de desarrollo y devuelve su carpeta."""
    sys.path.insert(0, str(REPO))
    from tareas import rutas  # después de tocar sys.path: el del repo, no el instalado
    from herramientas import vault_prueba

    carpeta = Path(os.environ.get("COTEJO_DEV") or rutas.estado().parent / "cotejo-dev")
    vault = carpeta / "vault"
    if not vault.exists():
        vault_prueba.crear(vault)
    os.environ.setdefault("COTEJO_CONFIG", str(carpeta / "config.json"))
    os.environ.setdefault("COTEJO_ESTADO", str(carpeta / "estado"))
    os.environ.setdefault("COTEJO_VAULT", str(vault))
    os.environ.setdefault("COTEJO_WORKTREES", str(carpeta / "wt"))
    return carpeta


def main(argumentos):
    preparar()
    from tareas import __main__ as entrada, board

    if board.es_del_board(argumentos):
        from tareas.app import aplicacion
        aplicacion.APP_ID = APP_ID_DEV
    sys.argv = ["cotejo-dev", *argumentos]
    return entrada.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
