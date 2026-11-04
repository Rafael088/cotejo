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

A `git` (y a `taskkill`) se le da `DETACHED_PROCESS`: sin consola ninguna, ni siquiera
invisible, así que tampoco hay un `conhost.exe` por llamada —un agente lanzado desde el board
hace ocho—. Se puede porque Git para Windows, cuando no tiene consola, lanza lo suyo (`sh`, un
hook, `ssh`) con `CREATE_NO_WINDOW`: el nieto no abre ventana (`pruebas/test_subproceso.py` lo
comprueba en Windows). A cualquier otro programa no: un cliente de npm, `python.exe` o `cmd`
sin consola harían que cada hijo suyo de consola abriera una ventana.

`start_new_session=True` es de POSIX (Python lo ignora en Windows). Aquí se traduce: en
Windows es `CREATE_NEW_PROCESS_GROUP`, que lo separa del grupo de Ctrl+C de quien lo lanza; en
POSIX se queda como está. Fuera de Windows no se toca nada de lo que se pasa.

Una terminal que la persona tiene que ver (el maestro: `cmd /c start "" …`) también va con el
flag: el `cmd` intermedio no se ve, y `start` abre la ventana del programa, que es la que
importa.
"""

import functools
import ntpath
import os
import shutil
import subprocess
import sys
# Para quien no necesita más de `subprocess` que esto: con importar el helper le basta.
from subprocess import DEVNULL, PIPE, STDOUT, SubprocessError, TimeoutExpired  # noqa: F401

# Los valores de la API de Windows; `subprocess.CREATE_NO_WINDOW` solo existe allí.
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
# Los que pueden ir sin consola (ver arriba): por el nombre del programa, sin extensión.
SIN_CONSOLA = {"git", "taskkill"}


def en_windows():
    return sys.platform == "win32"


def _variable(entorno, nombre, defecto=""):
    """Lee una variable como Windows: sus nombres no distinguen mayúsculas."""
    if entorno is None:
        entorno = os.environ
    for clave, valor in entorno.items():
        if str(clave).upper() == nombre:
            return str(valor)
    return defecto


def _camino(entorno=None):
    return (_variable(entorno, "PATH", os.defpath),
            _variable(entorno, "PATHEXT", ".COM;.EXE;.BAT;.CMD"))


@functools.lru_cache(maxsize=32)
def _which(programa, path, pathext):
    """`which`, cacheado por el entorno que de verdad recibirá el hijo.

    Al simular Windows en las pruebas, `os.pathsep` sigue siendo el de Linux. El segundo
    intento explícito también hace que el `.cmd` falso del PATH se encuentre en ese caso y
    respeta un PATHEXT propio del `env`, no solo el del proceso padre.
    """
    try:
        ruta = shutil.which(programa, path=path)
    except (OSError, ValueError, AttributeError, TypeError, NameError):
        # `NameError` solo aparece al simular win32 sobre Linux: allí no existe `_winapi`.
        ruta = None
    if ruta:
        return ruta
    try:
        extensiones = pathext.replace(";", os.pathsep).split(os.pathsep)
        for extension in extensiones:
            extension = extension.strip()
            if extension:
                # En Windows el disco no distingue `.CMD` de `.cmd`; el Linux de la prueba
                # sí, aunque `sys.platform` esté simulado.
                for candidata in dict.fromkeys((extension, extension.lower())):
                    ruta = shutil.which(programa + candidata, mode=os.F_OK, path=path)
                    if ruta:
                        return ruta
    except (OSError, ValueError, AttributeError, TypeError, NameError):
        pass
    return None


def sin_consola(argv, entorno=None):
    """¿Puede ir `argv` con `DETACHED_PROCESS`? Solo si es uno de `SIN_CONSOLA` y lo que se va a
    ejecutar es su `.exe`: un `git.cmd` lo correría un `cmd.exe` sin consola, y el `git.exe` que
    él lanzara abriría la suya."""
    if isinstance(argv, (str, bytes)) or not argv:
        return False
    programa = str(argv[0])
    nombre = programa.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if nombre.endswith(".exe"):
        return nombre[:-4] in SIN_CONSOLA
    if nombre not in SIN_CONSOLA:
        return False
    return _es_exe(programa, *_camino(entorno))


@functools.lru_cache(maxsize=32)
def _es_exe(programa, _path, _pathext):
    # Con caché por PATH: en Windows `which` prueba cada extensión en cada carpeta, y el board
    # lanza ocho git seguidos al soltar una carta.
    ruta = _which(programa, _path, _pathext)
    return bool(ruta) and ruta.lower().endswith(".exe")


def _resolver(argv, entorno=None):
    """Resuelve el primer elemento de un argv como lo haría el PATH del hijo en Windows.

    `CreateProcess` no aplica PATHEXT al nombre que recibe. Además, un `.cmd`/`.bat` necesita
    el intérprete de comandos; `shell=True` es el camino de `subprocess` que lo prepara y cita.
    Devuelve `(argv, shell)`; fuera de los argv de lista no cambia nada.
    """
    if not en_windows() or isinstance(argv, (str, bytes)) or not argv:
        return argv, False
    try:
        programa = os.fspath(argv[0])
    except TypeError:
        return argv, False
    if not isinstance(programa, str):
        return argv, False
    # Una ruta o una extensión expresa ya dicen exactamente qué quiso lanzar quien llamó.
    if ntpath.dirname(programa) or ntpath.splitext(programa)[1]:
        return argv, False
    ruta = _which(programa, *_camino(entorno))
    if not ruta:
        return argv, False
    resuelto = [ruta, *argv[1:]]
    return resuelto, ruta.lower().endswith((".cmd", ".bat"))


def opciones(kwargs, argv=None):
    """Los `kwargs` de `subprocess` con lo de Windows puesto. Devuelve una copia."""
    kwargs = dict(kwargs)
    if not en_windows():
        return kwargs
    flags = kwargs.pop("creationflags", 0) or 0
    flags |= DETACHED_PROCESS if sin_consola(argv, kwargs.get("env")) else CREATE_NO_WINDOW
    if kwargs.pop("start_new_session", False):
        flags |= CREATE_NEW_PROCESS_GROUP
    kwargs["creationflags"] = flags
    return kwargs


def _argv(args, kwargs):
    return args[0] if args else kwargs.get("args")


def _preparar(args, kwargs):
    """Copia la llamada y sustituye su argv sin mutar la lista ni el dict de quien llama."""
    kwargs = dict(kwargs)
    argv, shell = _resolver(_argv(args, kwargs), kwargs.get("env"))
    if args:
        args = (argv, *args[1:])
    elif "args" in kwargs:
        kwargs["args"] = argv
    if shell:
        kwargs["shell"] = True
    return args, opciones(kwargs, argv)


# Se busca `subprocess.X` al llamar, no al importar: así un `mock.patch("subprocess.run")` de
# las pruebas sigue valiendo para todo el paquete.

def run(*args, **kwargs):
    args, kwargs = _preparar(args, kwargs)
    return subprocess.run(*args, **kwargs)


def Popen(*args, **kwargs):
    args, kwargs = _preparar(args, kwargs)
    return subprocess.Popen(*args, **kwargs)


def call(*args, **kwargs):
    args, kwargs = _preparar(args, kwargs)
    return subprocess.call(*args, **kwargs)


def check_call(*args, **kwargs):
    args, kwargs = _preparar(args, kwargs)
    return subprocess.check_call(*args, **kwargs)


def check_output(*args, **kwargs):
    args, kwargs = _preparar(args, kwargs)
    return subprocess.check_output(*args, **kwargs)
