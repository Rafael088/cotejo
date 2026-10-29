"""¿Sigue vivo el proceso que se lanzó para una tarea?

Lo pregunta `revisar` por los despachos headless que se anotaron al lanzar y nunca al terminar:
si el cliente murió (un OOM, la máquina reiniciada, alguien que lo mató) la tarea se queda en
«Haciéndola» a nombre de un modelo que ya no la está haciendo, y sin esto solo se descubría a
los días, como «colgada».

Un pid se recicla. Por eso, donde se puede mirar qué programa es (`/proc/<pid>/cmdline` en
Linux), un pid vivo que ya es otro programa cuenta como muerto. Donde no, vivo es vivo: más vale
una «trabajando» de más que dar por perdida una tarea que alguien sigue haciendo.

Con `systemd-run --scope` de por medio hay un instante en que el pid ya es el del cliente pero
su `/proc/<pid>/cmdline` todavía es el del envoltorio («systemd-run … -- cliente»): ese caso
también cuenta como vivo, o el board diría «murió» justo al lanzar (cotejo-ovw2xt).

En Windows no se usa `os.kill(pid, 0)`: allí la señal 0 es CTRL_C_EVENT y la mandaría de verdad.
"""

import os
import signal
import socket
import sys
from pathlib import Path


def vivo(pid, programa=""):
    """True si `pid` existe y, si se puede saber, sigue siendo `programa` (su nombre o ruta)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _vivo_en_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # existe, pero es de otro usuario
    except OSError:
        return False
    return _es_el_mismo(pid, programa)


def anotado_muerto(linea):
    """¿Una anotación con `fase: "lanzado"`, `pid`, `programa` y `host` (la de un despacho o la
    de un inicio en segundo plano) es de un proceso que ya no está?

    Solo se puede saber en la máquina que lo lanzó: el vault puede estar sincronizado con otra,
    y allí ese pid es de cualquiera. Desde otra máquina no se da por muerto.
    """
    if linea.get("fase") != "lanzado" or not linea.get("pid"):
        return False
    if linea.get("host") and linea["host"] != socket.gethostname():
        return False
    return not vivo(linea["pid"], linea.get("programa", ""))


def terminar(pid, programa=""):
    """Para el proceso `pid` (y su grupo, si lo encabeza) si sigue siendo `programa`.

    Devuelve True si había algo que parar. Comprueba antes con `vivo`: un pid reciclado es de
    otro programa, y a ese no se le manda nada.
    """
    if not vivo(pid, programa):
        return False
    pid = int(pid)
    try:
        if sys.platform != "win32" and os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def _es_el_mismo(pid, programa):
    if not programa:
        return True
    try:
        crudo = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    except OSError:
        return True  # sin /proc (macOS) no se puede saber: vivo es vivo
    partes = [p for p in crudo.decode(errors="replace").split("\0") if p]
    nombre = Path(programa).name
    # El cliente puede ser un script (`node …/claude`, `python …/codex`): basta con que el
    # nombre esté en cualquiera de las primeras palabras.
    if any(Path(p).name == nombre for p in partes[:3]):
        return True
    # `systemd-run --scope` hace `execve` sobre sí mismo, pero entre que `Popen` vuelve del
    # `fork` y ese exec termina, `/proc/<pid>/cmdline` todavía dice «systemd-run … -- cliente»:
    # ahí el pid ya es el del cliente aunque su argv aún sea el del envoltorio. Sin esto,
    # `lanzados.estado` lo daba por muerto justo al lanzar (cotejo-ovw2xt).
    if partes and Path(partes[0]).name == "systemd-run":
        try:
            resto = partes[partes.index("--") + 1:]
        except ValueError:
            return False
        return any(Path(p).name == nombre for p in resto[:3])
    return False


def _vivo_en_windows(pid):
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION, STILL_ACTIVE = 0x1000, 259
    manija = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not manija:
        return False
    try:
        codigo = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(manija, ctypes.byref(codigo)):
            return False
        return codigo.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(manija)
