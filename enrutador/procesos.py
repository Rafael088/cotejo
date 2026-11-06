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
Allí se mira el ejecutable del pid (`QueryFullProcessImageNameW`) y, si se anotó al lanzar,
cuándo nació (`GetProcessTimes`): un pid reciclado es de otro programa o nació en otro momento,
y no es el agente. Sin esto, parar a un agente con el pid ya reciclado cerró el Chrome de la
persona entero con `taskkill /T` (cotejo-hrnx1m).

`nacimiento(pid)` es esa hora (en Linux, el `starttime` de `/proc/<pid>/stat`): quien
lanza la anota junto al pid (`nacio` en el registro) y `vivo`/`terminar` la comparan.
"""

import os
import signal
import socket
import sys
from pathlib import Path


def nacimiento(pid):
    """Cuándo nació `pid`, como un número que solo vale para compararlo con otro de la misma
    máquina (FILETIME en Windows, `starttime` en Linux), o None si no se sabe."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if sys.platform == "win32":
        info = _api_windows().info(pid)
        return info["creado"] if info else None
    try:
        crudo = (Path("/proc") / str(pid) / "stat").read_text()
        return int(crudo.rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        return None


def vivo(pid, programa="", creado=None):
    """True si `pid` existe y, si se puede saber, sigue siendo `programa` (su nombre o ruta) y
    nació cuando `creado` (lo que dio `nacimiento(pid)` al lanzarlo)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _es_el_de_windows(_api_windows().info(pid), programa, creado)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # existe, pero es de otro usuario
    except OSError:
        return False
    if creado is not None:
        ahora = nacimiento(pid)
        if ahora is not None and ahora != creado:
            return False   # el mismo pid, otro proceso
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
    return not vivo(linea["pid"], linea.get("programa", ""), linea.get("nacio"))


def terminar(pid, programa="", creado=None):
    """Para el proceso `pid` y lo que lanzó si sigue siendo `programa` (y nació en `creado`).

    Devuelve True si había algo que parar. Comprueba antes con `vivo`: un pid reciclado es de
    otro programa, y a ese no se le manda nada.

    En POSIX se para su grupo si lo encabeza (los agentes van con `start_new_session`: sus
    hijos y nietos están en él). En Windows no hay grupos que matar y `os.kill` solo cierra ese
    proceso: un agente de npm es `cmd.exe /c opencode.cmd`, y parar el `cmd` dejaba vivo el
    `opencode.exe` (cotejo-qtegjk). Allí se recorre el árbol a mano (`_terminar_arbol_windows`):
    `taskkill /T` se fía del ppid, que en Windows no cambia al morir el padre, y con un pid
    reciclado se llevaba por delante el árbol de otro programa (cotejo-hrnx1m).
    """
    if sys.platform == "win32":
        return _terminar_en_windows(pid, programa, creado)
    if not vivo(pid, programa, creado):
        return False
    pid = int(pid)
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True


def descendientes(foto, raiz, nacimientos):
    """Los pids que cuelgan de `raiz` (sin contarla) en una foto [(pid, ppid)], con
    `nacimientos(pid)` → cuándo nació (o None). Un hijo solo cuenta si se sabe cuándo nacieron él y su
    padre y nació después (o a la vez): es lo que dice Windows para fiarse de un ppid, que
    sobrevive a la muerte del padre aunque su pid ya sea de otro (como `humo_windows`)."""
    hijos = {}
    for pid, ppid in foto:
        if pid != ppid:
            hijos.setdefault(ppid, []).append(pid)
    vistos, pendientes = set(), [raiz]
    while pendientes:
        padre = pendientes.pop()
        for hijo in hijos.get(padre, ()):
            if hijo in vistos or hijo == raiz:
                continue
            nacio, nacio_padre = nacimientos(hijo), nacimientos(padre)
            if nacio is None or nacio_padre is None or nacio < nacio_padre:
                continue   # no se sabe, o nació antes que su «padre»: es de otro
            vistos.add(hijo)
            pendientes.append(hijo)
    return vistos


def _terminar_en_windows(pid, programa, creado):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    api = _api_windows()
    info = api.info(pid)
    # Para parar se exige más que para «vivo»: con un nombre que pedir, hay que haberlo leído.
    if not _es_el_de_windows(info, programa, creado, estricto=True):
        return False
    return _terminar_arbol_windows(api, pid, info["creado"])


def _terminar_arbol_windows(api, raiz, nacio_raiz):
    """Para `raiz` y lo que cuelga de ella. La foto y los nacimientos se toman antes de parar
    nada; después, cada uno se para solo si su pid sigue siendo el de la foto (`api.matar`
    compara la hora de nacimiento con la manija ya abierta, así que no hay hueco para que se
    recicle entre mirar y parar). La raíz primero, para que no lance más."""
    nacimientos = {raiz: nacio_raiz}

    def cuando(pid):   # solo se pregunta por los que cuelgan del árbol, no por toda la foto
        if pid not in nacimientos:
            info = api.info(pid)
            nacimientos[pid] = info["creado"] if info else None
        return nacimientos[pid]

    arbol = descendientes(api.foto(), raiz, cuando)
    parada = api.matar(raiz, nacio_raiz)
    for pid in sorted(arbol):
        api.matar(pid, nacimientos[pid])
    return parada


EXTENSIONES_WINDOWS = (".exe", ".cmd", ".bat", ".com")


def _es_el_de_windows(info, programa, creado, estricto=False):
    """¿`info` (lo de `_ApiWindows.info`) es el proceso que se lanzó como `programa`?"""
    if not info or not info["vivo"]:
        return False
    if creado is not None and info["creado"] is not None and info["creado"] != creado:
        return False   # el mismo pid, otro proceso
    if not programa:
        return True
    if not info["imagen"]:
        return not estricto   # sin saber qué es: vivo es vivo, pero no se para
    return es_su_imagen(info["imagen"], programa)


def es_su_imagen(imagen, programa):
    """¿El ejecutable `imagen` (ruta de Windows) es el de `programa` (como se anotó: nombre o
    ruta, con o sin extensión)? Un `.cmd`/`.bat` lo corre un `cmd.exe`, y un nombre sin
    extensión puede ser uno de ellos (el `opencode` de npm es `opencode.cmd`)."""
    def nombre(ruta):
        return str(ruta).replace("\\", "/").rsplit("/", 1)[-1].lower()

    def sin_extension(n):
        for ext in EXTENSIONES_WINDOWS:
            if n.endswith(ext):
                return n[:-len(ext)], ext
        return n, ""

    de_imagen, _ = sin_extension(nombre(imagen))
    de_programa, ext = sin_extension(nombre(programa))
    if de_imagen == de_programa:
        return True
    return de_imagen == "cmd" and ext in ("", ".cmd", ".bat")


class _ApiWindows:
    """Lo poco de kernel32 que hace falta, con los tipos puestos (en 64 bits una manija sin
    `restype` se truncaba a 32)."""

    CONSULTAR = 0x1000        # PROCESS_QUERY_LIMITED_INFORMATION
    PARAR = 0x0001            # PROCESS_TERMINATE
    SIGUE = 259               # STILL_ACTIVE

    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.ctypes, self.w = ctypes, w
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32 = k32

        class Entrada(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD),
                        ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG),
                        ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]
        self.Entrada = Entrada
        k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        k32.OpenProcess.restype = w.HANDLE
        k32.CloseHandle.argtypes = [w.HANDLE]
        k32.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        k32.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
        k32.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR,
                                                   ctypes.POINTER(w.DWORD)]
        k32.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        k32.CreateToolhelp32Snapshot.restype = w.HANDLE
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [
            w.HANDLE, ctypes.POINTER(Entrada)]

    def _nacio(self, manija):
        t = [self.w.FILETIME() for _ in range(4)]
        if not self.k32.GetProcessTimes(manija, *[self.ctypes.byref(x) for x in t]):
            return None
        return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime

    def _sigue(self, manija):
        codigo = self.w.DWORD()
        if not self.k32.GetExitCodeProcess(manija, self.ctypes.byref(codigo)):
            return False
        return codigo.value == self.SIGUE

    def info(self, pid):
        """{vivo, creado, imagen} de `pid`, o None si no se puede abrir (no existe)."""
        manija = self.k32.OpenProcess(self.CONSULTAR, False, pid)
        if not manija:
            return None
        try:
            ruta = self.ctypes.create_unicode_buffer(32768)
            largo = self.w.DWORD(len(ruta))
            imagen = (ruta.value if self.k32.QueryFullProcessImageNameW(
                manija, 0, ruta, self.ctypes.byref(largo)) else None)
            return {"vivo": self._sigue(manija), "creado": self._nacio(manija),
                    "imagen": imagen}
        finally:
            self.k32.CloseHandle(manija)

    def foto(self):
        """[(pid, ppid)] de todos los procesos."""
        foto = self.k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
        if not foto or foto == self.w.HANDLE(-1).value:
            return []
        lista = []
        try:
            entrada = self.Entrada()
            entrada.dwSize = self.ctypes.sizeof(entrada)
            ok = self.k32.Process32FirstW(foto, self.ctypes.byref(entrada))
            while ok:
                lista.append((entrada.th32ProcessID, entrada.th32ParentProcessID))
                ok = self.k32.Process32NextW(foto, self.ctypes.byref(entrada))
        finally:
            self.k32.CloseHandle(foto)
        return lista

    def matar(self, pid, nacio):
        """Para `pid` si nació en `nacio`. La comprobación y el `TerminateProcess` van por la
        misma manija: mientras está abierta, ese pid no se puede reciclar."""
        manija = self.k32.OpenProcess(self.PARAR | self.CONSULTAR, False, pid)
        if not manija:
            return False
        try:
            if nacio is None or self._nacio(manija) != nacio or not self._sigue(manija):
                return False
            return bool(self.k32.TerminateProcess(manija, 1))
        finally:
            self.k32.CloseHandle(manija)


_API = None


def _api_windows():
    global _API
    if _API is None:
        _API = _ApiWindows()
    return _API


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
