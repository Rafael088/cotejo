"""`python -m tareas` y el comando `cotejo`: la CLI, salvo que se pida la ventana.

La frontera va al revés de como iba: antes había una lista de verbos que se libraban de GTK y
todo lo demás caía en la app, así que un verbo nuevo que alguien olvidara apuntar arrancaba la
interfaz sin que nadie lo notara. Ahora lo que se apunta es lo poco que es de la ventana
(`board.es_del_board`) y todo lo demás es de la CLI, que no importa GTK. En una máquina sin
PyGObject un verbo nuevo funciona igual, y uno mal escrito lo rechaza argparse en vez de
abrir una ventana. `pruebas/test_nucleo_sin_gtk.py` lo vigila verbo por verbo.
"""

import sys

from .board import es_del_board


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    if es_del_board(argumentos):
        from .board import main as board
        return board()
    from .cli import main as cli
    return cli()


if __name__ == "__main__":
    sys.exit(main())
