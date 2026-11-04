"""El humo del board en Windows: lanzar un agente falso y medir lo que se ve desde fuera.

Lo corre `herramientas/probar_windows.sh` en la máquina Windows, dentro de la sesión de
escritorio (una tarea programada interactiva, lo mismo que `schtasks /it`), con el Python del
runtime instalado (`pythonw.exe`, sin consola) y el código de la rama copiada:

    pythonw herramientas/humo_windows.py vigilar --carpeta C:\\...\\humo --instalacion C:\\...\\Cotejo

`vigilar` hace de testigo: abre el board de la rama en otro proceso (`board`, con el APP_ID
`io.github.cotejoapp.CotejoPruebaHumo<pid>` y config, estado y vault propios en `--carpeta`),
le pide que mueva una tarea a Haciendo —lo que lanza el cliente falso (`pruebas/cliente_falso.py`)
con el `python.exe` de consola del runtime, como un CLI de verdad— y mientras tanto mide:

- cuántos `conhost.exe` hay antes, durante y después, y cuáles nacieron del board;
- qué ventanas de terminal nuevas aparecen (Windows Terminal o la consola clásica);
- cuánto tarda la ventana del board en atender un mensaje (`SendMessageTimeout` con WM_NULL) y
  si Windows la da por colgada (`IsHungAppWindow`); el board, por su lado, apunta el hueco más
  largo de su bucle de GLib;
- qué procesos del board siguen vivos al cerrar la ventana y al salir.

Con `--cerrar-trabajando parar|dejar` (cotejo-qtegjk) la ventana se cierra con el agente aún
trabajando, y la pregunta «pararlos o dejarlos» se contesta con eso sin diálogo. El agente va
entonces como uno de npm, `cmd.exe /c python.exe cliente_falso.py` (lo que es `opencode.cmd`),
para ver que parar mata el árbol entero y no solo el `cmd`. Lo que había del agente antes de
cerrar y lo que sigue vivo después queda en `al_cerrar.agente`.

Al final cierra lo que abrió (procesos que nacieron del board y ventanas de terminal nuevas) y
deja todo en `<carpeta>/humo.json`. No arregla nada: que hoy salgan ventanas de terminal o
bloqueos es el diagnóstico, no un fallo del humo; `ok` solo dice si el humo pudo medir.

Volcados de hilos (para ver *qué* bloquea): con `--volcar-ms N` el board vuelca todos sus hilos
(`faulthandler.dump_traceback`) cada vez que su bucle lleva N ms sin latir; con
`--faulthandler-s S`, además, `faulthandler.dump_traceback_later(S, repeat=True)`. Van a
`<carpeta>/volcados/` y `probar_windows.sh` los trae a Linux.

`suite --salida <carpeta>` corre la batería de la rama con ese mismo runtime y deja
`suite.log` y `suite.json` (su código de salida): también va en el escritorio, porque las
pruebas del board no pueden crear su ventana en la sesión de ssh (el proceso muere).

`resumen <humo.json>` imprime los números en una línea; corre en cualquier sistema.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ESQUEMA = 1
TAREA = "cotejo-humo-win"
PROYECTO = "Humo"
TEXTO = "Tarea del humo de Windows #agente/sonnet"
APP_ID = "io.github.cotejoapp.CotejoPruebaHumo"
# Las clases de ventana de una terminal: Windows Terminal y la consola de siempre (conhost).
CLASES_TERMINAL = {"CASCADIA_HOSTING_WINDOW_CLASS": "windows-terminal",
                   "ConsoleWindowClass": "consola"}
PROCESOS_TERMINAL = ("windowsterminal.exe", "openconsole.exe")
TOPE_MS = 5000          # lo más que se espera a que la ventana atienda un WM_NULL
MUESTREO_S = 0.1
UMBRALES_MS = (100, 250, 1000)
MAX_VOLCADOS = 30
HUECO_APUNTADO_MS = 100   # los huecos del bucle de más de esto se apuntan uno a uno
ESCRITO_POR_EL_AGENTE = "agente-falso.log"
TOPE_DESPACHO_S = 120   # lo más que se espera a que vuelva el despacho en segundo plano


# --- lo que no depende de Windows (lo prueba test_probar_windows.py en Linux) -------------------

def entorno_del_lanzador(instalacion, codigo, base=None):
    """El entorno que pone `empaquetado/windows/lanzador.c`, con el código de la rama.

    El board de la rama corre con el runtime instalado, igual que lo correría `cotejoboard.exe`,
    pero con `PYTHONPATH` en la copia de la rama y no en `app\\`."""
    entorno = dict(os.environ if base is None else base)
    instalacion = str(instalacion)
    for quitar in ("PYTHONHOME", "MSYSTEM"):
        entorno.pop(quitar, None)
    entorno.update({
        "PYTHONPATH": str(codigo),
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        "PYTHONSAFEPATH": "1",
        "GDK_PIXBUF_MODULEDIR": instalacion + r"\runtime\lib\gdk-pixbuf-2.0\2.10.0\loaders",
        "GDK_WIN32_PER_MONITOR_HIDPI": "1",
        "PATH": instalacion + r"\bin;" + instalacion + r"\runtime\bin;" + entorno.get("PATH", ""),
    })
    return entorno


def config_humo(carpeta, python_agente, falso, por_cmd=False):
    """La config del humo: el proyecto en su repo de mentira y el cliente falso como motor.
    Con `por_cmd`, el falso va detrás de un `cmd.exe /c`, como un cliente de npm (`.cmd`)."""
    carpeta = Path(carpeta)
    comando = [str(python_agente), str(falso)]
    if por_cmd:
        comando = ["cmd.exe", "/c", *comando]
    return {"enrutador": {
        "proyectos": {PROYECTO: str(carpeta / "repo")},
        "motores": {"headless": {"comando": comando, "aislar": False}},
    }}


def nota_humo():
    return f"---\ntipo: proyecto\n---\n\n# {PROYECTO}\n\n- [ ] {TEXTO} ^{TAREA}\n"


def entorno_del_humo(carpeta, espera_s, volcar_ms=0, faulthandler_s=0, perfil=False,
                     al_cerrar=""):
    """Lo que el humo añade al entorno del board: sus carpetas y los ganchos de volcado."""
    carpeta = Path(carpeta)
    entorno = {"COTEJO_CONFIG": str(carpeta / "config.json"),
               "COTEJO_ESTADO": str(carpeta / "estado"),
               "COTEJO_VAULT": str(carpeta / "vault"),
               "COTEJO_WORKTREES": str(carpeta / "wt"),
               "COTEJO_MOTOR": "agente",
               "COTEJO_NO_PREGUNTAR_CLI": "1",
               "FALSO_ESPERA": str(espera_s),
               # Mientras trabaja, el agente falso escribe en la carpeta que vigila el board:
               # así el humo mide también los refrescos (cotejo-72a7di).
               "FALSO_ESCRIBIR": str(carpeta / "vault" / "01-Proyectos" / ESCRITO_POR_EL_AGENTE),
               "FALSO_ESCRIBIR_CADA": "0.5"}
    if volcar_ms:
        entorno["COTEJO_HUMO_VOLCAR_MS"] = str(int(volcar_ms))
    if faulthandler_s:
        entorno["COTEJO_HUMO_FAULTHANDLER_S"] = str(faulthandler_s)
    if perfil:
        entorno["COTEJO_HUMO_PERFIL"] = "1"
    if al_cerrar:
        entorno["COTEJO_HUMO_AL_CERRAR"] = al_cerrar
    return entorno


def descendientes(procesos, raiz):
    """Los pids que cuelgan de `raiz` (sin contarla), a partir de una foto (pid, ppid)."""
    hijos = {}
    for p in procesos:
        if p["pid"] != p["ppid"]:
            hijos.setdefault(p["ppid"], []).append(p["pid"])
    vistos, pendientes = set(), [raiz]
    while pendientes:
        for hijo in hijos.get(pendientes.pop(), ()):
            if hijo not in vistos and hijo != raiz:
                vistos.add(hijo)
                pendientes.append(hijo)
    return vistos


def por_nombre(nombres):
    """{nombre: cuántos}, de más a menos."""
    cuenta = {}
    for nombre in nombres:
        cuenta[nombre] = cuenta.get(nombre, 0) + 1
    return dict(sorted(cuenta.items(), key=lambda par: (-par[1], par[0])))


def contar(procesos, nombre):
    return sum(1 for p in procesos if p["nombre"].lower() == nombre)


def de_terminal(ventanas):
    """Las ventanas visibles que son una terminal."""
    return [v for v in ventanas if v.get("visible") and v["clase"] in CLASES_TERMINAL]


def peor(latencias):
    """La peor latencia en ms; un `None` (no atendió en TOPE_MS) cuenta como TOPE_MS."""
    if not latencias:
        return None
    return round(max(TOPE_MS if m is None else m for m in latencias), 1)


def resumen_bloqueo(muestras, colgada_vista, bucle=None, soltar_en=None):
    """Lo que dicen las latencias de la ventana, `(instante, ms)` con `ms=None` si el WM_NULL
    no volvió en TOPE_MS. `soltar_en` (time.monotonic, que en Windows es el mismo reloj en los
    dos procesos) separa lo que pasó desde que se soltó la carta en Haciendo. `bucle` es lo que
    apuntó el propio board de su bucle de GLib."""
    latencias = [m for _t, m in muestras]
    timeouts = sum(1 for m in latencias if m is None)
    resumen = {"peor_ms": peor(latencias),
               "peor_ms_desde_soltar": None if soltar_en is None else
               peor([m for t, m in muestras if t >= soltar_en]),
               "colgada": bool(colgada_vista or timeouts),
               "is_hung_app_window": bool(colgada_vista),
               "sin_respuesta_en_tope": timeouts, "tope_ms": TOPE_MS,
               "muestras": len(muestras)}
    for umbral in UMBRALES_MS:
        resumen[f"mas_de_{umbral}ms"] = sum(1 for m in latencias if m is None or m > umbral)
    bucle = bucle or {}
    resumen["bucle_peor_hueco_ms"] = bucle.get("peor_hueco_ms")
    resumen["bucle_peor_hueco_desde_soltar_ms"] = bucle.get("peor_hueco_desde_soltar_ms")
    resumen["soltar_ms"] = bucle.get("soltar_ms")
    resumen["despacho_ms"] = bucle.get("despacho_ms")
    resumen["bucle_huecos"] = bucle.get("huecos", [])
    return resumen


def resultado_vacio():
    return {"esquema": ESQUEMA, "ok": False, "error": None,
            "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "windows": platform.version(),
            "agente": {}, "conhost": {}, "terminal": {}, "bloqueo": {},
            "al_cerrar": {}, "al_salir": {}, "limpieza": {}, "volcados": [], "temporales": []}


def resumen_legible(datos):
    """Una línea con lo que importa del humo.json."""
    c, t, b = datos.get("conhost", {}), datos.get("terminal", {}), datos.get("bloqueo", {})
    quedan = len(datos.get("al_salir", {}).get("procesos", []))
    cerrar = datos.get("al_cerrar", {})
    agente = cerrar.get("agente") or {}
    partes = [
        "humo " + ("ok" if datos.get("ok") else f"FALLÓ: {datos.get('error')}"),
        f"agente lanzado={datos.get('agente', {}).get('lanzado')}",
        f"conhost {c.get('antes')}→{c.get('despues')} (nuevos {c.get('nuevos')}, "
        f"del board {c.get('nuevos_del_board')})",
        f"terminales nuevas {t.get('ventanas_nuevas')}",
        f"peor bloqueo {b.get('peor_ms')} ms (bucle {b.get('bucle_peor_hueco_ms')} ms, "
        f"soltar la carta {b.get('soltar_ms')} ms"
        + (f", despacho {b['despacho_ms']} ms" if b.get("despacho_ms") is not None else "")
        + ")",
        f"colgada={b.get('colgada')}",
        *[f"refrescos {r.get('cuantos')} (peor {r.get('peor_ms')} ms)"
          for r in [datos.get("refrescos")] if r],
        f"al cerrar: board vivo={cerrar.get('board_vivo')}, "
        f"quedan {len(cerrar.get('procesos', []))}",
        *[f"cerrar trabajando ({agente['respuesta']}): agente {len(agente.get('antes', []))}"
          f"→{len(agente.get('vivos', []))} vivos, pregunta={agente.get('pregunto')}"
          for _ in [0] if agente.get("respuesta")],
        f"quedan al salir {quedan}",
        f".tmp en lanzados {len(datos.get('temporales', []))}",
        f"volcados {len(datos.get('volcados', []))}",
    ]
    return " · ".join(partes)


# --- Win32 --------------------------------------------------------------------------------------

class Win32:
    """Lo poco de user32/kernel32 que hace falta, con ctypes (no hay pywin32 en el runtime)."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self.ctypes, self.w = ctypes, w
        k32, u32 = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("user32")
        self.k32, self.u32 = k32, u32

        class Entrada(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD),
                        ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", w.LONG),
                        ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]
        self.Entrada = Entrada
        k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        k32.CreateToolhelp32Snapshot.restype = w.HANDLE
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [
            w.HANDLE, ctypes.POINTER(Entrada)]
        k32.CloseHandle.argtypes = [w.HANDLE]
        k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        k32.OpenProcess.restype = w.HANDLE
        k32.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        self.ENUM = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        u32.EnumWindows.argtypes = [self.ENUM, w.LPARAM]
        u32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        u32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        u32.IsWindowVisible.argtypes = u32.IsHungAppWindow.argtypes = [w.HWND]
        u32.IsWindow.argtypes = [w.HWND]
        u32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        u32.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
                                            ctypes.POINTER(ctypes.c_size_t)]
        u32.SendMessageTimeoutW.restype = w.LPARAM
        u32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]

    def procesos(self):
        foto = self.k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
        if not foto or foto == self.w.HANDLE(-1).value:
            return []
        lista = []
        try:
            entrada = self.Entrada()
            entrada.dwSize = self.ctypes.sizeof(entrada)
            ok = self.k32.Process32FirstW(foto, self.ctypes.byref(entrada))
            while ok:
                lista.append({"pid": entrada.th32ProcessID, "ppid": entrada.th32ParentProcessID,
                              "nombre": entrada.szExeFile})
                ok = self.k32.Process32NextW(foto, self.ctypes.byref(entrada))
        finally:
            self.k32.CloseHandle(foto)
        return lista

    def ventanas(self):
        lista = []
        clase = self.ctypes.create_unicode_buffer(256)
        titulo = self.ctypes.create_unicode_buffer(256)

        def una(hwnd, _):
            pid = self.w.DWORD()
            self.u32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(pid))
            self.u32.GetClassNameW(hwnd, clase, 256)
            self.u32.GetWindowTextW(hwnd, titulo, 256)
            lista.append({"hwnd": hwnd, "pid": pid.value, "clase": clase.value,
                          "titulo": titulo.value, "visible": bool(self.u32.IsWindowVisible(hwnd))})
            return True
        self.u32.EnumWindows(self.ENUM(una), 0)
        return lista

    def latencia_ms(self, hwnd):
        """Lo que tarda la ventana en atender un WM_NULL; None si no lo atiende en TOPE_MS."""
        resultado = self.ctypes.c_size_t()
        antes = time.perf_counter()
        ok = self.u32.SendMessageTimeoutW(hwnd, 0, 0, 0, 0, TOPE_MS, self.ctypes.byref(resultado))
        return (time.perf_counter() - antes) * 1000 if ok else None

    def colgada(self, hwnd):
        return bool(self.u32.IsHungAppWindow(hwnd))

    def existe(self, hwnd):
        return bool(self.u32.IsWindow(hwnd))

    def cerrar(self, hwnd):
        self.u32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE

    def terminar(self, pid):
        h = self.k32.OpenProcess(0x0001, False, pid)   # PROCESS_TERMINATE
        if not h:
            return False
        try:
            return bool(self.k32.TerminateProcess(h, 1))
        finally:
            self.k32.CloseHandle(h)


# --- vigilar: el testigo de fuera ----------------------------------------------------------------

class Muestreo(threading.Thread):
    """Cada MUESTREO_S: qué procesos cuelgan del board y qué ventanas de terminal hay nuevas."""

    def __init__(self, win, pid_board, base_procesos, base_ventanas):
        super().__init__(daemon=True)
        self.win, self.pid = win, pid_board
        self.base_pids = {p["pid"] for p in base_procesos}
        self.base_hwnd = {v["hwnd"] for v in base_ventanas}
        self.parar = threading.Event()
        self.vistos = {}            # pid → nombre de todo lo que colgó del board
        self.conhost_nuevos = {}    # pid → nombre de quien lo abrió
        self.terminales = {}        # hwnd → ventana de terminal que no estaba
        self.max_conhost = 0
        self.wt_max = 0

    def una(self):
        procesos = self.win.procesos()
        nombres = {p["pid"]: p["nombre"] for p in procesos}
        for pid in descendientes(procesos, self.pid):
            self.vistos.setdefault(pid, nombres.get(pid, "?"))
        for p in procesos:
            if (p["nombre"].lower() == "conhost.exe" and p["pid"] not in self.base_pids
                    and p["pid"] not in self.conhost_nuevos):
                self.conhost_nuevos[p["pid"]] = nombres.get(p["ppid"], "?")
        self.max_conhost = max(self.max_conhost, contar(procesos, "conhost.exe"))
        self.wt_max = max(self.wt_max, sum(contar(procesos, n) for n in PROCESOS_TERMINAL))
        for v in de_terminal(self.win.ventanas()):
            if v["hwnd"] not in self.base_hwnd and v["hwnd"] not in self.terminales:
                v["proceso"] = nombres.get(v["pid"], "?")
                v["segundo"] = round(time.monotonic() - self.inicio, 2)
                self.terminales[v["hwnd"]] = v

    def run(self):
        self.inicio = time.monotonic()
        while not self.parar.is_set():
            try:
                self.una()
            except OSError:
                pass
            self.parar.wait(MUESTREO_S)


class Pulso(threading.Thread):
    """Mide sin parar cuánto tarda la ventana del board en atender un mensaje."""

    def __init__(self, win, hwnd):
        super().__init__(daemon=True)
        self.win, self.hwnd = win, hwnd
        self.parar = threading.Event()
        self.muestras = []
        self.colgada = False

    def run(self):
        while not self.parar.is_set():
            instante = time.monotonic()
            self.muestras.append((instante, self.win.latencia_ms(self.hwnd)))
            self.colgada = self.colgada or self.win.colgada(self.hwnd)
            self.parar.wait(0.05)


def preparar(carpeta, instalacion, codigo, por_cmd=False):
    """Vault, repo y config del humo en `carpeta`, que se vacía antes."""
    import shutil
    if carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)
    (carpeta / "vault" / "01-Proyectos").mkdir(parents=True)
    (carpeta / "volcados").mkdir()
    (carpeta / "vault" / "01-Proyectos" / f"{PROYECTO}.md").write_text(nota_humo(),
                                                                         encoding="utf-8")
    repo = carpeta / "repo"
    repo.mkdir()
    sin_consola = {"creationflags": 0x08000000}   # CREATE_NO_WINDOW: el humo no suma conhost
    git = ["git", "-c", "user.name=Humo", "-c", "user.email=humo@cotejo"]
    (repo / "LEEME").write_text("humo\n", encoding="utf-8")
    for orden in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run(git + orden, cwd=repo, check=True, capture_output=True, **sin_consola)
    python_agente = Path(instalacion) / "runtime" / "bin" / "python.exe"
    falso = Path(codigo) / "pruebas" / "cliente_falso.py"
    (carpeta / "config.json").write_text(
        json.dumps(config_humo(carpeta, python_agente, falso, por_cmd), indent=2),
        encoding="utf-8")


def ventana_del_board(win, pid, tope_s=90):
    limite = time.monotonic() + tope_s
    while time.monotonic() < limite:
        propias = [v for v in win.ventanas() if v["pid"] == pid and v["visible"]]
        if propias:
            return max(propias, key=lambda v: bool(v["titulo"]))
        time.sleep(0.2)
    return None


def leer_json(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def esperar_a(condicion, tope_s, paso=0.2):
    limite = time.monotonic() + tope_s
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(paso)
    return condicion()


def arbol_del_agente(procesos, vistos):
    """Lo del agente que colgaba del board y sigue vivo: su `cmd.exe`, su `python.exe` y lo
    que ellos lanzaron (sin los `git`, que vienen y van, ni los `conhost`)."""
    nombres = {p["pid"]: p["nombre"] for p in procesos}
    return [{"pid": pid, "nombre": nombre} for pid, nombre in sorted(vistos.items())
            if nombres.get(pid) == nombre
            and nombre.lower() in ("cmd.exe", "python.exe", "opencode.exe", "node.exe")]


def vigilar(args):
    carpeta = Path(args.carpeta)
    salida = Path(args.salida) if args.salida else carpeta.parent / "humo.json"
    datos = resultado_vacio()
    inicio = time.monotonic()
    win = Win32()
    board = muestreo = pulso = None
    try:
        cerrar_trabajando = args.cerrar_trabajando
        preparar(carpeta, args.instalacion, args.codigo, por_cmd=bool(cerrar_trabajando))
        base_procesos, base_ventanas = win.procesos(), win.ventanas()
        datos["conhost"]["antes"] = contar(base_procesos, "conhost.exe")
        datos["terminal"]["procesos_antes"] = sum(contar(base_procesos, n)
                                                  for n in PROCESOS_TERMINAL)
        entorno = entorno_del_lanzador(args.instalacion, args.codigo)
        entorno.update(entorno_del_humo(carpeta, args.espera, args.volcar_ms, args.faulthandler_s,
                                        args.perfil, cerrar_trabajando))
        pythonw = Path(args.instalacion) / "runtime" / "bin" / "pythonw.exe"
        registro = open(carpeta / "board.log", "w", encoding="utf-8")
        board = subprocess.Popen([str(pythonw), str(Path(__file__).resolve()), "board",
                                  "--carpeta", str(carpeta)], env=entorno, cwd=str(carpeta),
                                 stdout=registro, stderr=subprocess.STDOUT)
        datos["board_pid"] = board.pid
        muestreo = Muestreo(win, board.pid, base_procesos, base_ventanas)
        muestreo.start()
        ventana = ventana_del_board(win, board.pid)
        if ventana is None:
            raise RuntimeError("el board no abrió ninguna ventana en 90 s (mira board.log)")
        datos["ventana"] = {"clase": ventana["clase"], "titulo": ventana["titulo"]}
        pulso = Pulso(win, ventana["hwnd"])
        pulso.start()
        estado = carpeta / "board.json"
        if cerrar_trabajando:
            # Cerrar con el agente aún trabajando: en cuanto está lanzado, y un poco después.
            esperar_a(lambda: (leer_json(estado) or {}).get("fase") in ("trabajando", "fallo")
                      or board.poll() is not None, 90)
            time.sleep(2.0)
        else:
            # Lanzar, trabajar FALSO_ESPERA segundos y volver: con margen para el worktree.
            esperar_a(lambda: (leer_json(estado) or {}).get("fase") in ("terminado", "fallo")
                      or board.poll() is not None, args.espera + 90)
            time.sleep(1.0)   # lo que el board haga justo al volver el agente, también cuenta
        pulso.parar.set()
        pulso.join(TOPE_MS / 1000 + 1)
        muestreo.una()
        agente_antes = arbol_del_agente(win.procesos(), muestreo.vistos)
        win.cerrar(ventana["hwnd"])
        esperar_a(lambda: board.poll() is not None, 10)
        time.sleep(3)
        vivos = {p["pid"]: p["nombre"] for p in win.procesos()}
        datos["al_cerrar"] = {
            "board_vivo": board.poll() is None,
            "procesos": [{"pid": pid, "nombre": nombre} for pid, nombre in muestreo.vistos.items()
                         if vivos.get(pid) == nombre]}
        if cerrar_trabajando:
            datos["al_cerrar"]["agente"] = {
                "respuesta": cerrar_trabajando,
                "pregunto": (leer_json(estado) or {}).get("pregunta_al_cerrar"),
                "antes": agente_antes,
                "vivos": [p for p in agente_antes if vivos.get(p["pid"]) == p["nombre"]]}
        (carpeta / "salir").write_text("1", encoding="utf-8")
        try:
            board.wait(20)
        except subprocess.TimeoutExpired:
            pass
        muestreo.parar.set()
        muestreo.join(2)
        muestreo.una()
        despues = win.procesos()
        vivos = {p["pid"]: p["nombre"] for p in despues}
        quedan = [{"pid": pid, "nombre": nombre} for pid, nombre in muestreo.vistos.items()
                  if vivos.get(pid) == nombre]
        if board.poll() is None:
            quedan.insert(0, {"pid": board.pid, "nombre": "pythonw.exe (el board)"})
        datos["al_salir"] = {"board_salio": board.poll() is not None, "procesos": quedan}
        datos["conhost"].update({
            "despues": contar(despues, "conhost.exe"), "max_durante": muestreo.max_conhost,
            "nuevos": len(muestreo.conhost_nuevos),
            "nuevos_del_board": sum(1 for pid in muestreo.conhost_nuevos
                                    if pid in muestreo.vistos),
            "abiertos_por": por_nombre(muestreo.conhost_nuevos.values())})
        datos["terminal"].update({
            "ventanas_nuevas": len(muestreo.terminales),
            "ventanas": [{k: v[k] for k in ("clase", "titulo", "proceso", "segundo")}
                         for v in muestreo.terminales.values()],
            "procesos_max_durante": muestreo.wt_max,
            "procesos_despues": sum(contar(despues, n) for n in PROCESOS_TERMINAL)})
        board_json = leer_json(estado) or {}
        datos["agente"] = board_json.get("agente", {})
        datos["agente"]["espera_s"] = args.espera
        datos["bloqueo"] = resumen_bloqueo(pulso.muestras, pulso.colgada,
                                           board_json.get("bucle"), board_json.get("soltar_en"))
        datos["refrescos"] = board_json.get("refrescos", {})
        datos["procesos_vistos"] = sorted({n for n in muestreo.vistos.values()})
        datos["temporales"] = sorted(p.name for p in (carpeta / "estado" / "lanzados")
                                     .glob("*.tmp"))
        datos["ok"] = bool(datos["agente"].get("lanzado"))
        if not datos["ok"]:
            datos["error"] = board_json.get("error") or "el board no llegó a lanzar el agente"
    except Exception as error:   # el humo deja su JSON aunque falle: así se sabe por qué
        datos["error"] = f"{type(error).__name__}: {error}"
        datos["traza"] = traceback.format_exc()
    finally:
        datos["limpieza"] = limpiar(win, board, muestreo)
        datos["volcados"] = sorted(p.name for p in (carpeta / "volcados").glob("*.txt"))
        datos["duracion_s"] = round(time.monotonic() - inicio, 1)
        salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


def limpiar(win, board, muestreo):
    """Nada del humo se queda vivo en la máquina de la persona."""
    hecho = {"terminados": [], "ventanas_cerradas": 0}
    if muestreo is not None:
        muestreo.parar.set()
        vivos = {p["pid"]: p["nombre"] for p in win.procesos()}
        for pid, nombre in muestreo.vistos.items():
            if vivos.get(pid) == nombre and win.terminar(pid):
                hecho["terminados"].append(nombre)
        for hwnd in muestreo.terminales:
            if win.existe(hwnd):
                win.cerrar(hwnd)
                hecho["ventanas_cerradas"] += 1
    if board is not None and board.poll() is None:
        board.kill()
        hecho["terminados"].append("pythonw.exe (el board)")
    return hecho


# --- board: el board de la rama, dentro de su propio proceso -------------------------------------

def board(args):
    carpeta = Path(args.carpeta)
    estado_ruta = carpeta / "board.json"
    estado = {"fase": "abriendo", "agente": {"lanzado": False}, "soltar_en": None,
              "bucle": {"peor_hueco_ms": 0, "peor_hueco_desde_soltar_ms": None,
                        "soltar_ms": None}}

    def guardar(**cambios):
        estado.update(cambios)
        estado_ruta.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")

    guardar()
    volcados = carpeta / "volcados"
    volcados.mkdir(exist_ok=True)
    # El último latido del bucle; None mientras el board no se ve (el arranque no cuenta).
    ultimo = [None]
    ganchos(volcados, ultimo)

    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gio, GLib, Gtk
        from tareas import lanzados
        from tareas.app import aplicacion
        from tareas.app.piezas import TareaArrastrada
    except Exception:
        guardar(fase="fallo", error=traceback.format_exc())
        return 1

    aplicacion.App.poner_lo_del_usuario = lambda self: None   # nada del $HOME de la persona
    respuesta = os.environ.get("COTEJO_HUMO_AL_CERRAR")
    if respuesta:
        # La pregunta «pararlos o dejarlos» se contesta sola (cotejo-qtegjk): anota con qué
        # agentes se preguntó y responde lo que pidió el testigo.
        from tareas.app.ventana import Board

        def contestar(board, vivos):
            guardar(pregunta_al_cerrar=[r.get("id") for r in vivos])
            board.al_responder_cierre(respuesta, vivos)

        Board.preguntar_al_cerrar = contestar
    medir_refrescos(aplicacion.App, estado, volcados)
    app = aplicacion.App()
    app.set_application_id(f"{APP_ID}{os.getpid()}")
    app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
    app.desde_cero = False

    def latido():
        ahora = time.monotonic()
        if app.board is None or not app.board.get_visible():
            ultimo[0] = None
            return True
        if ultimo[0] is not None:
            hueco = round((ahora - ultimo[0]) * 1000, 1)
            bucle = estado["bucle"]
            bucle["peor_hueco_ms"] = max(bucle["peor_hueco_ms"], hueco)
            soltar_en = estado["soltar_en"]
            if soltar_en is not None and ahora >= soltar_en:
                bucle["peor_hueco_desde_soltar_ms"] = max(
                    bucle["peor_hueco_desde_soltar_ms"] or 0, hueco)
            if hueco > HUECO_APUNTADO_MS and len(bucle.setdefault("huecos", [])) < 40:
                # Cuándo (s desde soltar la carta, o desde abrir si aún no) y cuánto.
                desde = soltar_en if soltar_en is not None else 0
                bucle["huecos"].append([round(ultimo[0] - desde, 2), hueco])
        ultimo[0] = ahora
        return True

    def lanzar():
        b = app.board
        if b is None:
            return True
        try:
            b.ver_pestana("tablero")
            lista = b.columnas["pendiente"][0]
            fila = next(f for f in b.cartas(lista) if f.tarea.id == TAREA)
            antes = estado["soltar_en"] = time.monotonic()
            hecho = b.al_soltar(None, TareaArrastrada(fila.proyecto, fila.tarea), 0, 0,
                                "en-curso", Gtk.Box())
            estado["bucle"]["soltar_ms"] = round((time.monotonic() - antes) * 1000, 1)
            estado["agente"]["soltar_ok"] = bool(hecho)
        except Exception:
            guardar(fase="fallo", error=traceback.format_exc())
            return False
        # El despacho corre en segundo plano desde cotejo-72a7di: se espera a que vuelva (o, en
        # una rama de antes, ya volvió y esto ve el registro a la primera).
        GLib.timeout_add(100, lanzado, time.monotonic())
        return False

    def lanzado(desde):
        try:
            registro = lanzados.leer(TAREA) or {}
            en_marcha = bool(getattr(app.board, "lanzando", None))
            if en_marcha and time.monotonic() - desde < TOPE_DESPACHO_S:
                return True
            estado["bucle"]["despacho_ms"] = round((time.monotonic() - estado["soltar_en"])
                                                   * 1000, 1)
            guardar(fase="trabajando", agente={
                "lanzado": isinstance(registro.get("pid"), int),
                "soltar_ok": estado["agente"].get("soltar_ok"),
                "pid": registro.get("pid"), "fase": registro.get("fase"),
                "motivo": registro.get("motivo")})
            if not estado["agente"]["lanzado"]:
                guardar(fase="fallo", error=f"no se lanzó: {registro or 'sin registro'}")
        except Exception:
            guardar(fase="fallo", error=traceback.format_exc())
        return False

    def vigilar_fin():
        registro = lanzados.leer(TAREA) or {}
        if estado["fase"] == "trabajando" and registro.get("fin"):
            estado["agente"].update(termino=True, fin=registro.get("fin"))
            guardar(fase="terminado")
        elif estado["fase"] in ("trabajando", "terminado"):
            guardar()   # que el testigo vea el peor hueco al día
        if (carpeta / "salir").exists():
            guardar()
            app.quit()
            return False
        return True

    GLib.timeout_add(20, latido)
    GLib.timeout_add(2500, lanzar)
    GLib.timeout_add(200, vigilar_fin)
    codigo = app.run([sys.argv[0], "--board"])
    guardar()
    return codigo


def medir_refrescos(clase, estado, volcados):
    """Cuánto tarda cada `refrescar` del board (en el hilo de GTK): el peor y cuántos hubo. Con
    `COTEJO_HUMO_PERFIL=1`, además, cProfile de todos ellos en `volcados/perfil.txt`."""
    import cProfile
    import io
    import pstats
    original = clase.refrescar
    perfil = cProfile.Profile() if os.environ.get("COTEJO_HUMO_PERFIL") == "1" else None
    datos = estado.setdefault("refrescos", {"cuantos": 0, "peor_ms": 0.0, "total_ms": 0.0})

    def refrescar(self, *args, **kwargs):
        antes = time.monotonic()
        try:
            if perfil is None:
                return original(self, *args, **kwargs)
            return perfil.runcall(original, self, *args, **kwargs)
        finally:
            ms = (time.monotonic() - antes) * 1000
            datos["cuantos"] += 1
            if len(datos.setdefault("lista", [])) < 60:
                desde = estado.get("soltar_en")
                datos["lista"].append([round(antes - desde, 2) if desde else None, round(ms, 1)])
            datos["peor_ms"] = round(max(datos["peor_ms"], ms), 1)
            datos["total_ms"] = round(datos["total_ms"] + ms, 1)
            if perfil is not None:
                texto = io.StringIO()
                pstats.Stats(perfil, stream=texto).sort_stats("cumulative").print_stats(45)
                (volcados / "perfil.txt").write_text(texto.getvalue(), encoding="utf-8")

    clase.refrescar = refrescar


def ganchos(volcados, ultimo):
    """Los volcados de hilos que pidió el humo (`COTEJO_HUMO_VOLCAR_MS`, `..._FAULTHANDLER_S`)."""
    import faulthandler
    abiertos = []
    segundos = float(os.environ.get("COTEJO_HUMO_FAULTHANDLER_S") or 0)
    if segundos > 0:
        archivo = open(volcados / "faulthandler.txt", "w", encoding="utf-8")
        abiertos.append(archivo)
        faulthandler.dump_traceback_later(segundos, repeat=True, file=archivo)
    umbral = float(os.environ.get("COTEJO_HUMO_VOLCAR_MS") or 0) / 1000
    if umbral <= 0:
        return abiertos

    def perro():
        # Mientras el bucle siga parado, un volcado más cada `umbral`: la serie dice por dónde
        # va pasando el hilo principal durante un mismo bloqueo, no solo dónde empezó.
        hechos, bloqueo, del_bloqueo, siguiente = 0, None, 0, umbral
        while hechos < MAX_VOLCADOS:
            time.sleep(min(umbral / 4, 0.05))
            visto = ultimo[0]
            if visto is None:     # el board aún no se ve: el arranque no se vuelca
                continue
            if visto != bloqueo:
                bloqueo, del_bloqueo, siguiente = visto, 0, umbral
            hueco = time.monotonic() - visto
            if hueco > siguiente:
                hechos += 1
                del_bloqueo += 1
                siguiente += umbral
                nombre = f"bloqueo-{hechos:02d}.txt"
                with open(volcados / nombre, "w", encoding="utf-8") as archivo:
                    archivo.write(f"el bucle lleva {hueco * 1000:.0f} ms sin latir "
                                  f"(volcado {del_bloqueo} de este bloqueo)\n")
                    archivo.flush()
                    faulthandler.dump_traceback(file=archivo, all_threads=True)
    threading.Thread(target=perro, daemon=True).start()
    return abiertos


# --- suite: la batería de pruebas, en el escritorio ---------------------------------------------

def orden_de_la_suite(python, patron=None):
    orden = [str(python), "-m", "unittest", "discover", "-v", "-s", "pruebas"]
    return orden + (["-p", patron] if patron else [])


CODIGOS_NT = {0xC000013A: "STATUS_CONTROL_C_EXIT (le llegó un Ctrl+C)",
              0xC0000374: "STATUS_HEAP_CORRUPTION (el proceso se cayó)",
              0xC0000005: "STATUS_ACCESS_VIOLATION (el proceso se cayó)",
              0xC0000409: "STATUS_STACK_BUFFER_OVERRUN (el proceso se cayó)"}


def resumen_suite(texto, codigo=None):
    """Lo que dice un `unittest -v` (aunque se cortara a medias): cuántas pasaron, cuáles no y,
    si murió sin su línea «Ran», en qué prueba estaba."""
    import re
    resultado = {"ok": 0, "fallos": [], "omitidas": 0, "terminada": False, "ultima": None,
                 "codigo": codigo, "codigo_explicado": CODIGOS_NT.get(codigo)}
    patron = re.compile(r"^(test\w*) \(([\w.]+)\)")
    for linea in texto.splitlines():
        prueba = patron.match(linea)
        if prueba:
            resultado["ultima"] = prueba.group(2)
        if " ... ok" in linea or linea == "ok":
            resultado["ok"] += 1
        elif " ... skipped" in linea or linea.startswith("skipped "):
            resultado["omitidas"] += 1
        elif linea.startswith(("ERROR: ", "FAIL: ")):
            resultado["fallos"].append(linea)
        elif linea.startswith("Ran "):
            resultado["terminada"] = True
            resultado["ran"] = linea
    if not resultado["terminada"]:
        # Sin el informe final no hay líneas ERROR:/FAIL:; se cuentan las del progreso.
        resultado["fallos"] = [f"{tipo}: {nombre}" for nombre, tipo in re.findall(
            r"^test\w* \(([\w.]+)\) \.\.\. (ERROR|FAIL)", texto, re.M)]
    return resultado


def resumen_suite_legible(r):
    lineas = [f"suite: {r['ok']} bien, {len(r['fallos'])} con error o fallo, "
              f"{r['omitidas']} omitidas" + (f" · {r['ran']}" if r.get("ran") else "")]
    if not r["terminada"]:
        lineas.append(f"NO TERMINÓ: murió en {r['ultima']} con código {r['codigo']}"
                      + (f" = {r['codigo_explicado']}" if r["codigo_explicado"] else ""))
    lineas += [f"  {f}" for f in r["fallos"][:60]]
    if len(r["fallos"]) > 60:
        lineas.append(f"  … y {len(r['fallos']) - 60} más (en suite.log)")
    return "\n".join(lineas)


def suite(args):
    """La batería con el runtime instalado y el código de la rama, en esta sesión.

    Se corre desde `pythonw` (sin consola, para no abrir una en el escritorio) y la batería va en
    `python.exe` con CREATE_NO_WINDOW: su consola existe pero no se ve, y la heredan los git y
    los clientes falsos que lancen las pruebas, así que tampoco abren ventanas. Va además en un
    grupo de procesos propio (CREATE_NEW_PROCESS_GROUP), que no atiende Ctrl+C: una prueba que
    mira si un pid vive con `os.kill(pid, 0)` le manda en Windows un CTRL_C_EVENT a toda la
    consola, y sin esto la batería entera moría a medias con 0xC000013A."""
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    python = Path(args.instalacion) / "runtime" / "bin" / "python.exe"
    entorno = entorno_del_lanzador(args.instalacion, args.codigo)
    # Sin esto, el aviso de asyncio de PyGObject se repite en cada prueba del board y el
    # registro pasa de los 100 MB.
    entorno.setdefault("PYTHONWARNINGS", "ignore::DeprecationWarning")
    inicio = time.monotonic()
    datos = {"codigo": None, "tope_s": args.tope, "agotada": False}
    with open(salida / "suite.log", "w", encoding="utf-8") as registro:
        proceso = subprocess.Popen(orden_de_la_suite(python, args.patron), cwd=args.codigo,
                                   env=entorno, stdout=registro, stderr=subprocess.STDOUT,
                                   creationflags=0x08000000 | 0x00000200)
        try:
            datos["codigo"] = proceso.wait(args.tope)
        except subprocess.TimeoutExpired:
            datos["agotada"] = True
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proceso.pid)],
                           capture_output=True, creationflags=0x08000000)
            datos["codigo"] = proceso.wait(30)
    datos["segundos"] = round(time.monotonic() - inicio, 1)
    (salida / "suite.json").write_text(json.dumps(datos), encoding="utf-8")
    return 0


# --- la puerta -----------------------------------------------------------------------------------

def argumentos(argv=None):
    p = argparse.ArgumentParser(description="Humo del board en Windows (ver el docstring).")
    sub = p.add_subparsers(dest="modo", required=True)
    v = sub.add_parser("vigilar", help="abrir el board, lanzar el falso y medir")
    v.add_argument("--carpeta", required=True, help="carpeta de trabajo del humo (se vacía)")
    v.add_argument("--instalacion", required=True, help=r"%%LOCALAPPDATA%%\Programs\Cotejo")
    v.add_argument("--codigo", default=str(Path(__file__).resolve().parent.parent),
                   help="la copia de la rama (por defecto, la de este archivo)")
    v.add_argument("--salida", help="dónde dejar humo.json (por defecto, junto a --carpeta)")
    v.add_argument("--espera", type=float, default=8, help="segundos que trabaja el falso")
    v.add_argument("--volcar-ms", type=int, default=0,
                   help="volcar los hilos del board si su bucle pasa estos ms sin latir")
    v.add_argument("--faulthandler-s", type=float, default=0,
                   help="faulthandler.dump_traceback_later cada estos segundos")
    v.add_argument("--perfil", type=int, default=0,
                   help="1: perfilar (cProfile) cada refresco del board en volcados/perfil.txt")
    v.add_argument("--cerrar-trabajando", choices=("", "parar", "dejar"), default="",
                   help="cerrar con el agente trabajando y contestar esto a la pregunta")
    b = sub.add_parser("board", help="(lo lanza vigilar) el board de la rama")
    b.add_argument("--carpeta", required=True)
    s = sub.add_parser("suite", help="la batería de la rama con el runtime instalado")
    s.add_argument("--instalacion", required=True)
    s.add_argument("--codigo", default=str(Path(__file__).resolve().parent.parent))
    s.add_argument("--salida", required=True, help="carpeta para suite.log y suite.json")
    s.add_argument("--patron", help="-p de unittest")
    s.add_argument("--tope", type=float, default=1800, help="segundos como mucho")
    rs = sub.add_parser("resumen-suite", help="qué dice un suite.log (y su suite.json)")
    rs.add_argument("log")
    rs.add_argument("json", nargs="?")
    r = sub.add_parser("resumen", help="una línea con lo que dice un humo.json")
    r.add_argument("archivo")
    return p.parse_args(argv)


def main(argv=None):
    args = argumentos(argv)
    if args.modo == "resumen-suite":
        codigo = (leer_json(args.json) or {}).get("codigo") if args.json else None
        try:
            texto = Path(args.log).read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(f"no pude leer {args.log}", file=sys.stderr)
            return 2
        r = resumen_suite(texto, codigo)
        print(resumen_suite_legible(r))
        return 0 if r["terminada"] and not r["fallos"] and codigo in (0, None) else 1
    if args.modo == "resumen":
        datos = leer_json(args.archivo)
        if datos is None:
            print(f"no pude leer {args.archivo}", file=sys.stderr)
            return 2
        print(resumen_legible(datos))
        return 0 if datos.get("ok") else 1
    if sys.platform != "win32":
        print("el humo solo corre en Windows (resumen corre en cualquiera)", file=sys.stderr)
        return 2
    return {"vigilar": vigilar, "board": board, "suite": suite}[args.modo](args)


if __name__ == "__main__":
    sys.exit(main())
