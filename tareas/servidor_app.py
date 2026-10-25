"""Arrancar, esperar y parar la app de un proyecto para «Ver mi app» (v1.3.0, cotejo-vn4qd2).

Sin GTK. `Servidores` lleva un proceso por proyecto: si ya está vivo se reutiliza, y se para
con `parar` (el botón «Parar») o con `parar_todos` (al cerrar el board, y por `atexit` si el
proceso sale sin cerrarlo). El log de cada uno va a `rutas.estado()/ver-app/<proyecto>.log`.

Lo que se corre sale del repo de la persona (`tareas/como_se_abre.py`), así que va sin shell
(`shlex.split`), en la carpeta del proyecto, en su propio grupo de procesos (parar se lleva
también a los hijos, como el servidor que lanza `npm run dev`) y nunca con `sudo` (se niega
antes). Una página estática la sirve Cotejo con `servidor_estatico.py` en un puerto libre de
127.0.0.1: como `http.server`, pero sin servir nada oculto (`.git`, `.cotejo`) ni listar carpetas.

`abrir` bloquea hasta que la app responde o se rinde (por eso el board lo llama en un hilo) y
**no** abre el navegador: devuelve un `Resultado` con qué abrir (`abrir`) y la frase en llano,
y quien lo llama lo abre fuera del sandbox con el lanzador del sistema.
"""

import atexit
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import rutas

TOPE_SERVIDOR = 60      # segundos que se espera a que la app responda
TOPE_PROGRAMA = 8       # sin dirección: si no dice ninguna en este tiempo, es una ventana
PASO = 0.2
_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?[^\s'\"<>]*")
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass
class Resultado:
    """Lo que pasó, para decirlo en llano. `abrir` es una dirección o una ruta, o ""."""

    ok: bool
    texto: str
    abrir: str = ""
    log: str = ""
    corriendo: bool = False


@dataclass
class _Corriendo:
    proceso: subprocess.Popen
    clave: tuple
    url: str
    log: Path


def puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def responde(url, tope=0.5):
    """True si algo escucha en el puerto de `url`."""
    partes = urlsplit(url)
    host = partes.hostname or "127.0.0.1"
    host = "127.0.0.1" if host in ("0.0.0.0", "localhost") else host
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        with socket.create_connection((host, puerto), timeout=tope):
            return True
    except OSError:
        return False


def url_del_log(texto):
    """La primera dirección local que dijo la app en su salida (Vite, Next…), o ""."""
    m = _URL_RE.search(_ANSI_RE.sub("", texto or ""))
    return m.group(0).rstrip(".,;)").replace("0.0.0.0", "127.0.0.1") if m else ""


def _cola(log, lineas=6):
    try:
        texto = _ANSI_RE.sub("", Path(log).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return ""
    return "\n".join(t for t in texto.strip().splitlines()[-lineas:])


def _slug(nombre):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", nombre).strip("-") or "proyecto"


def _con_que_esperar(texto, como):
    return f"{texto} Deberías ver: {como.que_esperar}" if como.que_esperar else texto


def _rematar_grupo(pgid, espera):
    """Espera a que el grupo (los hijos, como el servidor de `npm run dev`) termine; si no, KILL."""
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        try:
            os.killpg(pgid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class Servidores:
    """Un proceso por proyecto, vivo mientras el board lo necesite."""

    def __init__(self, carpeta_logs=None, tope_servidor=TOPE_SERVIDOR,
                 tope_programa=TOPE_PROGRAMA):
        self.carpeta_logs = Path(carpeta_logs) if carpeta_logs else rutas.estado() / "ver-app"
        self.tope_servidor = tope_servidor
        self.tope_programa = tope_programa
        self.corriendo = {}
        atexit.register(self.parar_todos)

    # --- consultar -----------------------------------------------------------------------------

    def vivo(self, nombre):
        uno = self.corriendo.get(nombre)
        return uno is not None and uno.proceso.poll() is None

    def url(self, nombre):
        return self.corriendo[nombre].url if self.vivo(nombre) else ""

    # --- abrir ---------------------------------------------------------------------------------

    def abrir(self, nombre, plan):
        """Arranca (o reutiliza) la app del `plan` (`como_se_abre.Plan`) y espera a que responda."""
        if not plan.ok:
            return Resultado(False, plan.motivo)
        como, carpeta = plan.como, Path(plan.carpeta)
        tipo = como.tipo
        if tipo == "enlace":
            return Resultado(True, _con_que_esperar("Abrí tu app en el navegador.", como),
                             abrir=como.url)
        if tipo == "archivo":
            ruta = carpeta / como.url
            if not ruta.exists():
                return Resultado(False, f"No encuentro «{como.url}» en la carpeta de tu proyecto. "
                                        "Pídele a un agente que corrija cómo se abre tu app.")
            return Resultado(True, _con_que_esperar("Abrí tu app.", como), abrir=str(ruta))
        if tipo == "pagina":
            if not (carpeta / como.url).is_file():
                return Resultado(False, f"No encuentro «{como.url}» en la carpeta de tu proyecto.")
            puerto = puerto_libre()
            argv = [sys.executable, str(Path(__file__).with_name("servidor_estatico.py")),
                    str(puerto), str(carpeta)]
            url = f"http://127.0.0.1:{puerto}/{como.url}"
            return self._arrancar(nombre, ("pagina", str(carpeta), como.url), argv, carpeta,
                                  url, como, tope=10)
        donde = (carpeta / como.carpeta) if como.carpeta else carpeta
        if not donde.is_dir():
            return Resultado(False, f"No encuentro la carpeta «{como.carpeta}» de tu proyecto.")
        argv = como.argv()
        if shutil.which(argv[0], path=os.environ.get("PATH")) is None and not (donde / argv[0]).is_file():
            return Resultado(False, f"No encuentro «{argv[0]}» en este equipo, y tu app lo "
                                    "necesita para abrirse. Pídele a un agente que te diga cómo "
                                    "instalarlo.")
        clave = (tipo, str(donde), como.comando, como.url)
        tope = self.tope_programa if (tipo == "programa" and como.origen != "deducido") \
            else self.tope_servidor
        return self._arrancar(nombre, clave, argv, donde, como.url, como, tope)

    def _arrancar(self, nombre, clave, argv, donde, url, como, tope):
        uno = self.corriendo.get(nombre)
        if uno is not None and self.vivo(nombre) and uno.clave == clave:
            if not uno.url or responde(uno.url):
                return Resultado(True, _con_que_esperar("Tu app ya estaba abierta.", como),
                                 abrir=uno.url, log=str(uno.log), corriendo=True)
        self.parar(nombre)
        if url and clave[0] == "servidor" and responde(url):
            # Algo ya escucha ahí (la abrió la persona en una terminal): no se lanza otra.
            return Resultado(True, _con_que_esperar("Tu app ya estaba abierta.", como), abrir=url)
        self.carpeta_logs.mkdir(parents=True, exist_ok=True)
        log = self.carpeta_logs / f"{_slug(nombre)}.log"
        extra = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                 if sys.platform == "win32" else {"start_new_session": True})
        with open(log, "w", encoding="utf-8") as salida:
            try:
                proceso = subprocess.Popen(argv, cwd=str(donde), stdin=subprocess.DEVNULL,
                                           stdout=salida, stderr=subprocess.STDOUT, **extra)
            except OSError as error:
                return Resultado(False, f"Tu app no arrancó: {error.strerror or error}.",
                                 log=str(log))
        self.corriendo[nombre] = _Corriendo(proceso, clave, url, log)
        return self._esperar(nombre, como, tope)

    def _esperar(self, nombre, como, tope):
        uno = self.corriendo[nombre]
        limite = time.monotonic() + tope
        while time.monotonic() < limite:
            codigo = uno.proceso.poll()
            if not uno.url:
                try:
                    uno.url = url_del_log(uno.log.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
            if uno.url and responde(uno.url):
                return Resultado(True, _con_que_esperar(
                    "Abrí tu app en el navegador.", como), abrir=uno.url, log=str(uno.log),
                    corriendo=True)
            if codigo is not None:
                del self.corriendo[nombre]
                cola = _cola(uno.log)
                if codigo == 0 and como.tipo == "programa" and not uno.url:
                    return Resultado(True, "Tu app se abrió y ya terminó."
                                     + (f" Lo último que dijo:\n{cola}" if cola else ""),
                                     log=str(uno.log))
                return Resultado(False, "Tu app no arrancó."
                                 + (f" Lo último que dijo:\n{cola}" if cola else ""),
                                 log=str(uno.log))
            time.sleep(PASO)
        if como.tipo == "programa" and not uno.url and como.origen != "deducido":
            return Resultado(True, _con_que_esperar("Tu app está abierta.", como),
                             log=str(uno.log), corriendo=True)
        self.parar(nombre)
        donde = f" en {uno.url}" if uno.url else ""
        return Resultado(False, f"Tu app tardó más de {int(tope)} segundos en responder{donde} "
                                "y la paré. Lo que dijo está en su registro.", log=str(uno.log))

    # --- parar ---------------------------------------------------------------------------------

    def parar(self, nombre, espera=3):
        """Para la app de `nombre` y a sus hijos. True si había una viva."""
        uno = self.corriendo.pop(nombre, None)
        if uno is None or uno.proceso.poll() is not None:
            return False
        proceso = uno.proceso
        try:
            if sys.platform == "win32":
                proceso.terminate()
            else:
                os.killpg(proceso.pid, signal.SIGTERM)
            proceso.wait(espera)
        except subprocess.TimeoutExpired:
            if sys.platform != "win32":
                os.killpg(proceso.pid, signal.SIGKILL)
            else:
                proceso.kill()
            proceso.wait(espera)
        except (ProcessLookupError, PermissionError):
            pass
        if sys.platform != "win32":
            _rematar_grupo(proceso.pid, espera)
        return True

    def parar_todos(self):
        for nombre in list(self.corriendo):
            self.parar(nombre)
