"""Lanzar un cliente sin interfaz que sigue aunque se cierre quien lo lanzó.

Lo usa el inicio de un proyecto (`enrutador/preparar.py`), la única excepción a «nada en
segundo plano» (decisión del inicio en la app, v1.3.0): el proceso va en su propia sesión
(`start_new_session`) para que cerrar la ventana de CotejoBoard no se lo lleve, aislado en su
scope de systemd como cualquier headless (`aislamiento.py`), y su salida va a un archivo, no a
una tubería: nadie tiene por qué estar leyéndola mientras corre.
"""

import os
import subprocess

from .. import aislamiento


def lanzar(comando, directorio, registro, ajustes=None, entorno=None, etiqueta=""):
    """Arranca `comando` y devuelve el `Popen`. `registro` es el archivo de su salida.

    Levanta `FileNotFoundError` si el programa no existe, igual que `Popen`.

    `PWD` va con `directorio` (cotejo-7yfw1e): `cwd` cambia la carpeta del proceso pero no esa
    variable, y OpenCode trabaja donde dice `PWD`; sin esto, corría sus comandos en la carpeta
    desde la que se abrió el board y no en el worktree de la tarea.
    """
    lanzar = aislamiento.envolver(comando, ajustes or {}, etiqueta)
    entorno = {**(entorno or {}), **({"PWD": str(directorio)} if directorio else {})}
    os.makedirs(os.path.dirname(registro), exist_ok=True)
    with open(registro, "ab") as salida:
        return subprocess.Popen(
            lanzar, cwd=str(directorio) if directorio else None,
            env={**os.environ, **(entorno or {})},
            stdin=subprocess.DEVNULL, stdout=salida, stderr=subprocess.STDOUT,
            start_new_session=True)


def lanzar_aparte(comando, directorio, salida, errores, ajustes=None, entorno=None,
                  etiqueta=""):
    """Como `lanzar`, con stderr en su propio archivo. Lo usa el maestro (cotejo-9ybn1a): la
    respuesta de un cliente sin interfaz es su stdout (Codex escribe ahí solo el mensaje
    final y el progreso en stderr), y mezclarlos la ensuciaría."""
    lanzar_ = aislamiento.envolver(comando, ajustes or {}, etiqueta)
    entorno = {**(entorno or {}), **({"PWD": str(directorio)} if directorio else {})}
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "ab") as out, open(errores, "ab") as err:
        return subprocess.Popen(
            lanzar_, cwd=str(directorio) if directorio else None,
            env={**os.environ, **entorno}, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
            start_new_session=True)
