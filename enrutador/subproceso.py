"""Lanzar procesos sin que en Windows salga una consola por cada uno (cotejo-gckm21).

En Windows, un programa de consola (`git.exe`, `cmd.exe`, `python.exe`, un cliente de npm)
lanzado desde uno que no tiene consola —el board, que es una ventana GTK— abre la suya propia:
una ventana de Terminal vacía por proceso. Al arrastrar una carta a Haciendo salían 8–9 (los
`git` de `worktrees` y el `python.exe` del agente). Los shims `.cmd`/`.bat` de npm se leen aquí
y se sustituyen por su `.exe`, o por `node` y el script, para no pasar argumentos por `cmd.exe`.

Toda llamada a `subprocess` del paquete pasa por aquí (`pruebas/test_subproceso.py` lo exige
recorriendo el código). En Windows se añade `CREATE_NO_WINDOW`: el hijo tiene consola, pero sin
ventana, y lo que él lance (sus `git` u otros hijos) hereda esa misma consola invisible en
lugar de abrir otra. Por eso no se usa `DETACHED_PROCESS`: un hijo sin consola haría que cada
nieto de consola abriera la suya.

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
import re
import subprocess
import sys
from pathlib import Path
# Para quien no necesita más de `subprocess` que esto: con importar el helper le basta.
from subprocess import DEVNULL, PIPE, STDOUT, SubprocessError, TimeoutExpired  # noqa: F401

# Los valores de la API de Windows; `subprocess.CREATE_NO_WINDOW` solo existe allí.
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
# Los que pueden ir sin consola (ver arriba): por el nombre del programa, sin extensión.
SIN_CONSOLA = {"git", "taskkill"}
PATHEXT_POR_DEFECTO = ".COM;.EXE;.BAT;.CMD"


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
            _variable(entorno, "PATHEXT", PATHEXT_POR_DEFECTO))


@functools.lru_cache(maxsize=64)
def _which(programa, path, pathext):
    """Resuelve como Windows, con el PATH y PATHEXT que recibirá el hijo: carpeta por carpeta, y
    en cada una las extensiones de PATHEXT antes que el nombre pelado.

    El nombre pelado va al final porque npm deja, junto a `opencode.cmd`, un `opencode` sin
    extensión que es un script de sh: Windows no lo ejecuta, y `shutil.which(mode=F_OK)` lo
    daba por bueno (en el Windows real, 06-nov). Se mira a mano, con `isfile`, para que la
    prueba en Linux no tenga que hacer ejecutable el `.cmd`.
    """
    if ntpath.dirname(programa):
        carpetas, programa = [ntpath.dirname(programa)], ntpath.basename(programa)
    else:
        carpetas = [c.strip().strip('"') for c in path.split(";") if c.strip()]
    if ntpath.splitext(programa)[1]:
        extensiones = [""]
    else:
        extensiones = [e.strip() for e in pathext.split(";") if e.strip()] + [""]
    for carpeta in carpetas:
        for extension in extensiones:
            # Windows no distingue mayúsculas; el sistema de archivos de la prueba en Linux sí.
            for candidata in dict.fromkeys((extension, extension.lower())):
                ruta = os.path.join(carpeta, programa + candidata)
                try:
                    if os.path.isfile(ruta):
                        return ruta
                except (OSError, ValueError):
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


_EJECUTABLE_NPM = re.compile(
    r'^\s*@?"(?P<programa>%dp0%[\\/][^"\r\n]+\.exe)"\s+%\*\s*$',
    re.IGNORECASE | re.MULTILINE)
_NODE_NPM = re.compile(
    r'"%_prog%"\s+"(?P<script>%dp0%[\\/][^"\r\n]+\.js)"\s+%\*\s*$',
    re.IGNORECASE | re.MULTILINE)


def _ruta_del_shim(shim, expresion):
    r"""Convierte ``%dp0%\ruta`` en una ruta junto al shim, también en pruebas POSIX."""
    relativo = re.sub(r"^%dp0%[\\/]", "", expresion, flags=re.IGNORECASE)
    partes = [parte for parte in re.split(r"[\\/]", relativo) if parte]
    return str(Path(shim).parent.joinpath(*partes))


def _leer_shim_npm(shim):
    """Devuelve el argv real de los dos formatos de shim npm que Cotejo admite."""
    try:
        texto = Path(shim).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise OSError(f"No sé lanzar {shim} sin cmd.exe: no pude leerlo ({error})") from error

    ejecutable = _EJECUTABLE_NPM.search(texto)
    if ejecutable:
        return [_ruta_del_shim(shim, ejecutable.group("programa"))]

    node = _NODE_NPM.search(texto)
    if node:
        node_local = Path(shim).with_name("node.exe")
        programa = str(node_local) if node_local.is_file() else "node"
        return [programa, _ruta_del_shim(shim, node.group("script"))]

    raise OSError(
        f"No sé lanzar {shim} sin cmd.exe: no reconozco el ejecutable del shim de npm")


def _resolver(argv, entorno=None):
    """En Windows sustituye un shim `.cmd`/`.bat` por lo que lanza, nunca por `cmd.exe`."""
    if not en_windows() or isinstance(argv, (str, bytes)) or not argv:
        return argv
    try:
        programa = os.fspath(argv[0])
    except TypeError:
        return argv
    if not isinstance(programa, str):
        return argv
    ruta = _which(programa, *_camino(entorno))
    if not ruta or not ruta.lower().endswith((".cmd", ".bat")):
        return argv
    return [*_leer_shim_npm(ruta), *argv[1:]]


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
    """Copia la llamada y sustituye su argv sin mutar los objetos de quien llama."""
    kwargs = dict(kwargs)
    argv = _resolver(_argv(args, kwargs), kwargs.get("env"))
    if args:
        args = (argv, *args[1:])
    elif "args" in kwargs:
        kwargs["args"] = argv
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
