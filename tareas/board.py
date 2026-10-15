"""La puerta de CotejoBoard, y lo único del núcleo que sabe que existe una ventana.

Cotejo se reparte en dos: el **núcleo** (la CLI, el modelo, la configuración, las fuentes, el
enrutador y `estado.json`), que corre con Python a secas, y la **interfaz** (el paquete `tareas/app/`), que
necesita PyGObject, GTK 4 y libadwaita. Cada una tiene su punto de entrada:

- `cotejo` → `tareas.cli:main`. Lo que llama un agente o un script. No carga GTK nunca.
- `cotejoboard` → `tareas.board:main`. La ventana. Solo aquí se importa `tareas.app`.

`python -m tareas` (`tareas.__main__`, lo que `install.sh` pone detrás de `cotejo` y
`tareas-obsidian`) sirve para las dos cosas, y reparte con `es_del_board`: así la barra y el
`.desktop`, que llaman a `tareas-obsidian --board` o sin argumentos, no se enteran del cambio.

Un instalador arma con esto lo que toque: CLI sola (`install.sh --sin-board`: sin PyGObject ni
GTK y sin `cotejoboard`, y `cotejo` va directo a `tareas.cli`) o CLI y board (Linux con
escritorio, Windows). Este
módulo no importa nada de la interfaz al cargarse, así que puede vivir en los dos.
"""

import sys

# Las opciones que declara `App` (`add_main_option`). Si la app gana una, va aquí también.
OPCIONES_DEL_BOARD = frozenset({"--board", "--fondo"})


def es_del_board(argumentos):
    """¿Esta invocación de `python -m tareas` es para la ventana?

    Sin argumentos se abre o se cierra el board (lo que hace el `.desktop`). Con `--board` o
    `--fondo`, o con las opciones propias de GApplication, también. Cualquier otra cosa es de
    la CLI, incluida una que no existe: argparse la rechaza con su uso, que es mejor que
    abrir una ventana por un verbo mal escrito.
    """
    if not argumentos:
        return True
    primero = argumentos[0]
    return primero in OPCIONES_DEL_BOARD or primero.startswith("--gapplication")


def main():
    from .app import main as app
    return app()


if __name__ == "__main__":
    sys.exit(main())
