"""Lanzar procesos sin que en Windows salga una consola por cada uno (cotejo-gckm21).

En Windows, un programa de consola (`git.exe`, `cmd.exe`, `python.exe`, el `.cmd` de un
cliente de npm) lanzado desde uno que no tiene consola —el board, que es una ventana GTK—
abre la suya propia: una ventana de Terminal vacía por proceso. Al arrastrar una carta a
Haciendo salían 8–9 (los `git` de `worktrees` y el `python.exe` del agente).

Toda llamada a `subprocess` del paquete pasa por aquí (`pruebas/test_subproceso.py` lo exige
recorriendo el código). En Windows se añade `CREATE_NO_WINDOW`: el hijo tiene consola, pero sin
ventana, y lo que él lance (el nieto: el cliente del agente, sus `git`, un `cmd /c`) hereda esa
misma consola invisible en lugar de abrir otra. Por eso no se usa `DETACHED_PROCESS`: un hijo
sin consola haría que cada nieto de consola abriera la suya.

`start_new_session=True` es de POSIX (Python lo ignora en Windows). Aquí se traduce: en
Windows es `CREATE_NEW_PROCESS_GROUP`, que lo separa del grupo de Ctrl+C de quien lo lanza; en
POSIX se queda como está. Fuera de Windows no se toca nada de lo que se pasa.

Una terminal que la persona tiene que ver (el maestro: `cmd /c start "" …`) también va con el
flag: el `cmd` intermedio no se ve, y `start` abre la ventana del programa, que es la que
importa.
"""

import subprocess
import sys

# Los valores de la API de Windows; `subprocess.CREATE_NO_WINDOW` solo existe allí.
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def en_windows():
    return sys.platform == "win32"


def opciones(kwargs):
    """Los `kwargs` de `subprocess` con lo de Windows puesto. Devuelve una copia."""
    kwargs = dict(kwargs)
    if not en_windows():
        return kwargs
    flags = kwargs.pop("creationflags", 0) or 0
    flags |= CREATE_NO_WINDOW
    if kwargs.pop("start_new_session", False):
        flags |= CREATE_NEW_PROCESS_GROUP
    kwargs["creationflags"] = flags
    return kwargs


# Se busca `subprocess.X` al llamar, no al importar: así un `mock.patch("subprocess.run")` de
# las pruebas sigue valiendo para todo el paquete.

def run(*args, **kwargs):
    return subprocess.run(*args, **opciones(kwargs))


def Popen(*args, **kwargs):
    return subprocess.Popen(*args, **opciones(kwargs))


def call(*args, **kwargs):
    return subprocess.call(*args, **opciones(kwargs))


def check_call(*args, **kwargs):
    return subprocess.check_call(*args, **opciones(kwargs))


def check_output(*args, **kwargs):
    return subprocess.check_output(*args, **opciones(kwargs))
