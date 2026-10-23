"""Abrir un programa en una terminal nueva que se ve, y olvidarse de él.

Lo usa el maestro. No espera ni lee nada: la terminal es de la persona que la pidió, y lo que
pase ahí se ve ahí; lo que importa a Cotejo —qué se entregó— llega por el vault, como siempre.
`start_new_session` la desprende del proceso que la abre, para que cerrar CotejoBoard no se lleve
por delante al maestro que está trabajando.
"""

import os
import shutil
import subprocess

from tareas import rutas

# El ejemplo del mensaje de error es de la plataforma en la que se lee: sugerir `alacritty -e`
# en Windows (o `cmd /c start` en Linux) manda a instalar algo que no hace falta.
EJEMPLO_TERMINAL = {
    "windows": '["cmd", "/c", "start", ""]',
}
EJEMPLO_TERMINAL_XDG = '["alacritty", "-e"]'


class SinTerminal(Exception):
    pass


def abrir(comando, directorio=None, entorno=None):
    """`entorno`: variables que se añaden a las de ahora (el inicio pone `COTEJO_FUENTE`)."""
    if not comando or shutil.which(comando[0]) is None:
        ejemplo = EJEMPLO_TERMINAL.get(rutas.sistema(), EJEMPLO_TERMINAL_XDG)
        raise SinTerminal(
            f"No encontré la terminal «{comando[0] if comando else ''}». Pon la tuya en "
            f"enrutador.maestro.terminal de la config, por ejemplo {ejemplo}.")
    env = {**os.environ, **entorno} if entorno else None
    subprocess.Popen(comando, cwd=str(directorio) if directorio else None, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
