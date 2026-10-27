"""Instalar un agente y abrir su inicio de sesión desde la pantalla «equipo» (v1.3.0, cotejo-2j6un7).

Sin GTK. La pantalla (`tareas/app/equipo.py`) pinta; aquí se decide **qué** se corre y se corre.

**Instalar** corre el instalador oficial que documenta cada proyecto, tal cual, y nada más:

- Claude Code: `curl -fsSL https://claude.ai/install.sh | bash`
  (fuente: https://code.claude.com/docs/en/setup, «Native Install (Recommended)»). Instala en
  `~/.local/bin/claude` y se niega a correr con sudo.
- Codex: `curl -fsSL https://chatgpt.com/codex/install.sh | sh`
  (fuente: https://developers.openai.com/codex/cli, el «standalone installer» de macOS/Linux).
  Instala en `~/.local/bin/codex`; con `CODEX_NON_INTERACTIVE=1`, que el propio script documenta,
  no pregunta «Start Codex now?».
- OpenCode: `curl -fsSL https://opencode.ai/install | bash` (fuente: https://opencode.ai/docs/,
  «Install script»). Instala en `~/.opencode/bin/opencode`.
- Gemini CLI **no**: su instalación oficial es `npm install -g @google/gemini-cli`
  (https://github.com/google-gemini/gemini-cli), que según dónde tenga npm su prefijo pide
  permisos de administrador; se queda en su enlace, como git. La pantalla dice en llano si falta
  npm.

Los tres instalan en la carpeta de la persona, sin sudo. Nunca se usa una shell: el script se
descarga con `urllib` a `<estado>/agentes/<agente>.sh` y se ejecuta con `bash`/`sh` sobre ese
archivo, sin terminal (`stdin` vacío, sesión propia: si el script quiere preguntar, no puede y
sigue con lo de por defecto), con tope (`TOPE_INSTALAR`), cancelable y con todo lo que dice en
`<estado>/agentes/<agente>.log` y, línea a línea, en la pantalla. Delante en su PATH van
`sudo`, `su`, `doas` y `pkexec` de mentira que se niegan (`MARCA_SIN_PERMISOS`): si el
instalador pide permisos de administrador, Cotejo no los da y lo dice en llano con el enlace a la
página oficial.

Lo instalado queda en una carpeta (`~/.local/bin`, `~/.opencode/bin`) que el escritorio puede no
tener en el PATH hasta la próxima sesión: `sumar_al_path` añade al PATH de este proceso la de
cada agente cuyo ejecutable esté ahí, para que el board (y lo que lance) lo encuentre ya.

**Iniciar sesión** es el comando oficial de cada CLI que abre el navegador (`SESIONES`):

- Claude Code: `claude auth login` (https://code.claude.com/docs/en/cli-reference). Puede pedir
  pegar un código en la terminal si el navegador no vuelve: va en una terminal.
- Codex: `codex login` (https://developers.openai.com/codex/auth): abre el navegador y recibe la
  sesión por `localhost`, sin terminal. Se corre como el instalador, con su salida en pantalla
  (ahí sale el enlace si el navegador no se abrió).
- OpenCode: `opencode auth login` (https://opencode.ai/docs/cli/): pregunta el proveedor en la
  terminal: va en una terminal.
- Gemini CLI: `gemini` (https://github.com/google-gemini/gemini-cli): la sesión se inicia al
  abrirlo («Sign in with Google»): va en una terminal.

La terminal es la del maestro (`enrutador.maestro.terminal` de la config, por defecto
`xdg-terminal-exec`, la que el escritorio tenga por preferida) o, si no está,
`x-terminal-emulator -e`. Sin ninguna, se devuelve el comando para copiarlo. Si quedó lista lo
sabe `enrutador.modelos_vivos.sesion`, que la pantalla consulta cada pocos segundos.
"""

import os
import re
import shutil
import signal
import subprocess
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from shlex import join as unir

from . import rutas

TOPE_INSTALAR = 600        # segundos como mucho por instalador
TOPE_SESION = 900          # lo que se espera a que la persona termine en el navegador
TOPE_DESCARGA = 60
MAX_LINEAS = 200           # las que se guardan en memoria; el log las tiene todas
MARCA_SIN_PERMISOS = "COTEJO-SIN-PERMISOS"
ESCALAR = ("sudo", "su", "doas", "pkexec")
RECOMENDADO = "claude"     # a quien no tiene ninguno se le sugiere este

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\r")


@dataclass(frozen=True)
class Instalador:
    url: str               # el script oficial, tal cual lo documenta el proyecto
    interprete: str        # con qué lo manda a correr la documentación (`| bash`, `| sh`)
    carpeta: object        # dónde deja el ejecutable: función de la casa
    fuente: str            # la página oficial que documenta el comando
    entorno: tuple = ()    # variables que el propio script documenta


def _bin_opencode(casa):
    return Path(casa) / ".opencode" / "bin"


INSTALADORES = {
    "claude": Instalador("https://claude.ai/install.sh", "bash", rutas.bin_local,
                         "https://code.claude.com/docs/en/setup"),
    "codex": Instalador("https://chatgpt.com/codex/install.sh", "sh", rutas.bin_local,
                        "https://developers.openai.com/codex/cli",
                        (("CODEX_NON_INTERACTIVE", "1"),)),
    "opencode": Instalador("https://opencode.ai/install", "bash", _bin_opencode,
                           "https://opencode.ai/docs/"),
}


@dataclass(frozen=True)
class Sesion:
    argumentos: tuple      # lo que va detrás del ejecutable
    en_terminal: bool      # pide escribir algo (o puede pedirlo): va en una terminal
    fuente: str


SESIONES = {
    "claude": Sesion(("auth", "login"), True, "https://code.claude.com/docs/en/cli-reference"),
    "codex": Sesion(("login",), False, "https://developers.openai.com/codex/auth"),
    "opencode": Sesion(("auth", "login"), True, "https://opencode.ai/docs/cli/"),
    "gemini": Sesion((), True, "https://github.com/google-gemini/gemini-cli"),
}

# Lo que necesita un agente sin instalador aquí para instalarse (se dice si falta).
NECESITA = {"gemini": "npm"}


# --- dónde ------------------------------------------------------------------------------------

def _casa(casa=None):
    return Path(casa) if casa is not None else Path(os.environ.get("HOME") or Path.home())


def carpeta():
    """`<estado>/agentes`: los scripts descargados y sus registros."""
    return rutas.estado() / "agentes"


def _ejecutable(clave):
    from enrutador import clientes
    return clientes.de(clave).ejecutable


def ruta_oficial(clave, casa=None):
    """Dónde deja el ejecutable el instalador oficial (None si no hay instalador)."""
    instalador = INSTALADORES.get(clave)
    if instalador is None:
        return None
    return instalador.carpeta(_casa(casa)) / _ejecutable(clave)


def sumar_al_path(entorno=None, casa=None):
    """Pone en el PATH (de `entorno`, por defecto el de este proceso) la carpeta de cada agente
    instalado por su instalador oficial que aún no esté. Devuelve las carpetas añadidas."""
    entorno = os.environ if entorno is None else entorno
    partes = [p for p in entorno.get("PATH", "").split(os.pathsep) if p]
    sumadas = []
    for clave in INSTALADORES:
        ruta = ruta_oficial(clave, casa)
        if ruta is None or not os.access(ruta, os.X_OK):
            continue
        dir_ = str(ruta.parent)
        if dir_ not in partes and dir_ not in sumadas:
            sumadas.append(dir_)
    if sumadas:
        entorno["PATH"] = os.pathsep.join(sumadas + partes)
    return sumadas


def puede_instalar(clave):
    """¿Sabe Cotejo correr el instalador oficial de este agente en este sistema?"""
    instalador = INSTALADORES.get(clave)
    return (instalador is not None and rutas.sistema() != "windows"
            and shutil.which(instalador.interprete) is not None)


def falta_para_instalar(clave):
    """Lo que hace falta y no está («npm»), o ""."""
    necesita = NECESITA.get(clave)
    return necesita if necesita and shutil.which(necesita) is None else ""


# --- correr algo y enseñar lo que dice ------------------------------------------------------------

def limpiar(linea):
    return ANSI.sub("", linea).rstrip()


@dataclass
class Trabajo:
    """Un proceso que se ve: el instalador o `codex login`. Los avisos (`al_linea`,
    `al_terminar`) llegan desde el hilo; la pantalla los pasa por `GLib.idle_add`."""
    clave: str
    que: str                          # "instalar" o "sesion"
    al_linea: object = None
    al_terminar: object = None
    tope: int = TOPE_INSTALAR
    lineas: list = field(default_factory=list)
    estado: str = "corriendo"         # corriendo | hecho | fallo | cancelado | tarde |
    #                                   sin_permisos | sin_descarga
    codigo: int = None
    log: Path = None
    proceso: object = None
    _hilo: object = None
    _cancelado: bool = False
    _tarde: bool = False

    @property
    def corriendo(self):
        return self.estado == "corriendo"

    def decir(self, linea):
        linea = limpiar(linea)
        if not linea:
            return
        self.lineas.append(linea)
        del self.lineas[:-MAX_LINEAS]
        if self.log is not None:
            try:
                with open(self.log, "a", encoding="utf-8") as archivo:
                    archivo.write(linea + "\n")
            except OSError:
                pass
        if self.al_linea:
            self.al_linea(self, linea)

    def cancelar(self):
        self._cancelado = True
        self._matar()

    def _matar(self):
        proceso = self.proceso
        if proceso is None or proceso.poll() is not None:
            return
        try:
            os.killpg(proceso.pid, signal.SIGTERM)
        except (OSError, AttributeError):
            try:
                proceso.terminate()
            except OSError:
                pass

    def esperar(self, tope=None):
        if self._hilo is not None:
            self._hilo.join(tope)
        return self.estado

    def _correr(self, argv, entorno, preparar=None):
        try:
            if preparar is not None and not preparar():
                return
            if self._cancelado:
                self.estado = "cancelado"
                return
            try:
                self.proceso = subprocess.Popen(
                    argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, errors="replace", env=entorno,
                    start_new_session=True)
            except OSError as error:
                self.decir(f"No se pudo arrancar: {error}")
                self.estado = "fallo"
                return
            reloj = threading.Timer(self.tope, self._se_paso)
            reloj.daemon = True
            reloj.start()
            sin_permisos = False
            try:
                for linea in self.proceso.stdout:
                    if MARCA_SIN_PERMISOS in linea:
                        sin_permisos = True
                        continue
                    self.decir(linea)
                self.codigo = self.proceso.wait()
            finally:
                reloj.cancel()
                self.proceso.stdout.close()
            if self._cancelado:
                self.estado = "cancelado"
            elif self._tarde:
                self.estado = "tarde"
            elif sin_permisos and self.codigo != 0:
                self.estado = "sin_permisos"
            else:
                self.estado = "hecho" if self.codigo == 0 else "fallo"
        finally:
            if self.estado == "corriendo":
                self.estado = "fallo"
            if self.al_terminar:
                self.al_terminar(self)

    def _se_paso(self):
        self._tarde = True
        self._matar()

    def arrancar(self, argv, entorno, preparar=None):
        self._hilo = threading.Thread(target=self._correr, args=(argv, entorno, preparar),
                                      daemon=True)
        self._hilo.start()
        return self


def _guardas(destino):
    """`sudo`, `su`, `doas` y `pkexec` que se niegan: van primeros en el PATH del instalador."""
    destino.mkdir(parents=True, exist_ok=True)
    for orden in ESCALAR:
        ruta = destino / orden
        ruta.write_text("#!/bin/sh\n# Lo escribe Cotejo: un instalador no sube privilegios.\n"
                        f"echo {MARCA_SIN_PERMISOS} >&2\nexit 126\n", encoding="utf-8")
        ruta.chmod(0o755)
    return destino


def descargar(url, destino, tope=TOPE_DESCARGA):
    """Baja el script oficial a `destino` (solo https). Las pruebas lo sustituyen."""
    if not url.startswith("https://"):
        raise OSError("solo se descarga por https")
    peticion = urllib.request.Request(url, headers={"User-Agent": "Cotejo"})
    with urllib.request.urlopen(peticion, timeout=tope) as respuesta:
        datos = respuesta.read()
    destino.write_bytes(datos)


def _es_script(ruta):
    try:
        inicio = ruta.read_bytes()[:64].lstrip()
    except OSError:
        return False
    return bool(inicio) and not inicio.startswith(b"<")


def instalar(clave, al_linea=None, al_terminar=None, tope=TOPE_INSTALAR):
    """Arranca el instalador oficial en un hilo y devuelve el `Trabajo`."""
    instalador = INSTALADORES[clave]
    dir_ = carpeta()
    dir_.mkdir(parents=True, exist_ok=True)
    script = dir_ / f"{clave}.sh"
    trabajo = Trabajo(clave, "instalar", al_linea, al_terminar, tope, log=dir_ / f"{clave}.log")
    try:
        trabajo.log.write_text("", encoding="utf-8")
    except OSError:
        trabajo.log = None
    guardas = _guardas(dir_ / "sin-permisos")
    entorno = {**os.environ, **dict(instalador.entorno), "NO_COLOR": "1", "TERM": "dumb",
               "PATH": os.pathsep.join([str(guardas), os.environ.get("PATH", "")])}

    def preparar():
        trabajo.decir(f"Descargando el instalador oficial: {instalador.url}")
        try:
            descargar(instalador.url, script)
        except (OSError, ValueError) as error:
            trabajo.decir(f"No pude descargarlo ({error}).")
            trabajo.estado = "sin_descarga"
            return False
        if not _es_script(script):
            trabajo.decir("Lo que llegó no es un instalador (parece una página web).")
            trabajo.estado = "sin_descarga"
            return False
        trabajo.decir(f"Corriendo: {instalador.interprete} {script.name}")
        return True

    return trabajo.arrancar([instalador.interprete, str(script)], entorno, preparar)


def resultado(trabajo, ahora_instalado=None):
    """Lo que se le dice a la persona cuando un trabajo termina, en llano."""
    titulo = _titulo(trabajo.clave)
    if trabajo.que == "sesion":
        return {"hecho": "Listo: terminó el inicio de sesión.",
                "cancelado": "Cancelado.",
                "tarde": "Se cansó de esperar al navegador y lo paré. Puedes volver a intentarlo.",
                }.get(trabajo.estado, "No se pudo iniciar sesión: lo de arriba es lo que dijo.")
    pagina = INSTALADORES[trabajo.clave].fuente if trabajo.clave in INSTALADORES else ""
    if trabajo.estado == "hecho":
        if ahora_instalado is False:
            return (f"El instalador terminó pero no encuentro {titulo}. Cierra Cotejo, vuelve a "
                    f"abrirlo y revisa otra vez.")
        return f"{titulo} quedó instalado. Ahora inicia sesión."
    if trabajo.estado == "sin_permisos":
        return (f"El instalador pidió permisos de administrador (sudo). Cotejo nunca los usa: "
                f"instálalo desde su página oficial, {pagina}")
    if trabajo.estado == "sin_descarga":
        return "No pude descargar el instalador. ¿Hay internet? Prueba otra vez en un rato."
    if trabajo.estado == "tarde":
        return f"Tardó más de {trabajo.tope // 60} minutos y lo paré. Prueba otra vez."
    if trabajo.estado == "cancelado":
        return "Cancelado. No quedó nada a medias que tengas que limpiar."
    donde = f" El registro completo está en {trabajo.log}." if trabajo.log else ""
    return f"El instalador falló (código {trabajo.codigo}).{donde}"


def _titulo(clave):
    from enrutador import clientes
    cliente = clientes.CLIENTES.get(clave)
    return (cliente.titulo if cliente and cliente.titulo else clave)


# --- iniciar sesión -----------------------------------------------------------------------------

def comando_sesion(clave):
    """El comando oficial de inicio de sesión, con el ejecutable que haya (lista)."""
    sesion = SESIONES[clave]
    ejecutable = _ejecutable(clave)
    ruta = shutil.which(ejecutable)
    if ruta is None:
        oficial = ruta_oficial(clave)
        ruta = str(oficial) if oficial is not None and os.access(oficial, os.X_OK) else ejecutable
    return [ruta, *sesion.argumentos]


def texto_para_copiar(clave):
    return unir([_ejecutable(clave), *SESIONES[clave].argumentos])


def terminal():
    """Con qué abrir una terminal, o None: la del maestro (config), o `xdg-terminal-exec`, o
    `x-terminal-emulator -e`."""
    candidatos = []
    try:
        from enrutador import config as cfg
        propia = (cfg.cargar().get("maestro") or {}).get("terminal")
        if propia:
            candidatos.append(list(propia))
    except Exception:  # noqa: BLE001  (una config rota no impide iniciar sesión)
        pass
    candidatos += [["xdg-terminal-exec"], ["x-terminal-emulator", "-e"]]
    for candidato in candidatos:
        if candidato and shutil.which(candidato[0]):
            return candidato
    return None


@dataclass(frozen=True)
class Apertura:
    """Qué pasó al pedir «Iniciar sesión»."""
    como: str                  # "terminal" | "fondo" | "copiar"
    comando: str               # el comando, para enseñarlo o copiarlo
    trabajo: object = None     # con "fondo", el `Trabajo`


def iniciar_sesion(clave, al_linea=None, al_terminar=None, tope=TOPE_SESION, abrir=None):
    """Abre el inicio de sesión oficial. `abrir(argv)` lanza la terminal (por defecto,
    `enrutador.motores.terminal.abrir`; las pruebas lo sustituyen)."""
    sesion = SESIONES[clave]
    argv = comando_sesion(clave)
    texto = texto_para_copiar(clave)
    if not sesion.en_terminal:
        trabajo = Trabajo(clave, "sesion", al_linea, al_terminar, tope)
        entorno = {**os.environ, "NO_COLOR": "1"}
        return Apertura("fondo", texto, trabajo.arrancar(argv, entorno))
    con = terminal()
    if con is None:
        return Apertura("copiar", texto)
    if abrir is None:
        from enrutador.motores import terminal as motor
        abrir = motor.abrir
    try:
        abrir(con + argv)
    except Exception:  # noqa: BLE001  (sin terminal que se deje abrir: se copia)
        return Apertura("copiar", texto)
    return Apertura("terminal", texto)

