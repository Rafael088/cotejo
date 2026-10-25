"""Un navegador sin interfaz que arranca dentro del sandbox del agente, para que vea lo que hace
(v1.3.0, cotejo-xrmr3h; lo usa para sus capturas cotejo-0e17vu).

**Por qué Chromium se caía** (prueba del dueño, 2026-10-24: dos `SIGABRT` con core): el sandbox
de Claude Code (`sandbox.py`) mete el Bash en bubblewrap y, encima, un filtro seccomp que niega
`socket(AF_UNIX, ...)` (es lo que impide hablar con el D-Bus y el systemd del escritorio, y desde
ahí pedirles que corran algo fuera). Chromium, antes de abrir nada, crea el «ProcessSingleton»:
un socket de Unix en su carpeta de perfil. Con el `socket()` negado no lo trata como error, sino
como fallo de programa (`process_singleton_posix.cc: Check failed: socket() failed: Operation not
permitted`) y aborta. No hay ninguna opción de Chromium que se lo salte; `--no-sandbox` no cambia
nada. Sin `--no-sandbox` se cae antes por lo mismo que cualquier sandbox anidado: el filtro tampoco
deja crear espacios de nombres de usuario y el `chrome-sandbox` setuid no sirve ahí.

Abrirle a Chromium los sockets de Unix (`allowAllUnixSockets`) sería abrir justo esa puerta, así
que **no se abre nada**: el navegador del agente es **Firefox**, que no necesita sockets de Unix
para arrancar sin interfaz (su IPC va por `socketpair`, que el filtro deja) y aguanta sin
espacios de nombres (lo avisa por stderr y sigue con su seccomp). Todo lo que escribe va al perfil
que se le da, en el temporal del sandbox (`TMPDIR`, que el propio Claude ya deja escribir), y a la
captura, que va a la carpeta de trabajo. Fuera del sandbox también vale Chromium (o Chrome).

**La red**: el sandbox deja al agente sin red propia (solo el proxy hacia los servidores
permitidos), pero su `localhost` es suyo y funciona: un `python3 -m http.server` arrancado **en
el mismo comando** que el navegador se alcanza. Uno arrancado en otro comando del Bash no (cada
comando va en su sandbox y se muere con él), ni un servidor de fuera del sandbox. Por eso no hace
falta abrir `localhost` en `lanzar.sandbox.dominios`. Sin servidor, `file://` basta.

Cómo lo usa un agente (`COMO_CAPTURAR`, lo lleva la nota del sandbox en `armado.py`):

    python3 -m enrutador.navegador <archivo.html|url> captura.png [--ancho 1280 --alto 800]

o, desde cualquier repo, la línea de Firefox de `COMO_CAPTURAR`. `capturar()` es lo mismo para el
código: elige el navegador, le da un perfil de usar y tirar, lo mata si se cuelga y comprueba que
sale un PNG de verdad.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

FIREFOX = ("firefox",)
CHROMIUM = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
ESPERA = 90

MOTIVO_CHROMIUM = ("Chromium no arranca dentro del sandbox: crea un socket de Unix al empezar y "
                   "el sandbox los niega (es lo que impide hablar con el escritorio desde dentro)")
COMO_CAPTURAR = ('firefox --headless --no-remote --profile "$(mktemp -d)" '
                 '--screenshot "$PWD/captura.png" --window-size=1280,800 <url o file:///ruta>')


def encerrado(entorno=None):
    """¿Corre esto dentro del sandbox? Claude Code pone `SANDBOX_RUNTIME=1` en su Bash encerrado
    y Cotejo `COTEJO_SANDBOX=1` al agente que lanza con él."""
    entorno = os.environ if entorno is None else entorno
    return entorno.get("SANDBOX_RUNTIME") == "1" or entorno.get("COTEJO_SANDBOX") == "1"


def elegir(entorno=None, which=shutil.which):
    """`(tipo, ruta, "")` del navegador que vale aquí, o `(None, None, motivo)`.

    Dentro del sandbox solo Firefox (`MOTIVO_CHROMIUM`); fuera, Firefox y si no Chromium."""
    for nombre in FIREFOX:
        ruta = which(nombre)
        if ruta:
            return ("firefox", ruta, "")
    if encerrado(entorno):
        return (None, None, "no hay firefox en esta máquina. " + MOTIVO_CHROMIUM)
    for nombre in CHROMIUM:
        ruta = which(nombre)
        if ruta:
            return ("chromium", ruta, "")
    return (None, None, "no hay firefox ni chromium en esta máquina")


def a_url(destino):
    """Una URL tal cual; una ruta, como `file://` absoluta."""
    texto = str(destino)
    if "://" in texto or texto.startswith(("about:", "data:")):
        return texto
    return Path(texto).expanduser().resolve().as_uri()


def argv_captura(tipo, ruta, url, salida, perfil, ancho=1280, alto=800):
    """El argv que saca la captura de `url` en `salida` con el perfil `perfil`."""
    tam = f"--window-size={int(ancho)},{int(alto)}"
    if tipo == "firefox":
        return [ruta, "--headless", "--no-remote", "--profile", str(perfil),
                "--screenshot", str(salida), tam, url]
    return [ruta, "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--hide-scrollbars", f"--user-data-dir={perfil}", f"--screenshot={salida}", tam, url]


def es_png(ruta):
    """¿Hay en `ruta` un PNG que no está vacío?"""
    try:
        with open(ruta, "rb") as f:
            cabeza = f.read(len(FIRMA_PNG) + 16)
    except OSError:
        return False
    return cabeza.startswith(FIRMA_PNG) and len(cabeza) > len(FIRMA_PNG)


def capturar(destino, salida, ancho=1280, alto=800, espera=ESPERA, entorno=None,
             which=shutil.which):
    """Saca la captura de `destino` (ruta o URL) en `salida` (PNG). Devuelve
    `{"ok", "png", "navegador", "motivo"}`; nunca deja el navegador vivo ni su perfil."""
    salida = Path(salida).expanduser().resolve()
    tipo, ruta, motivo = elegir(entorno, which)
    resultado = {"ok": False, "png": str(salida), "navegador": tipo, "motivo": motivo}
    if not tipo:
        return resultado
    salida.parent.mkdir(parents=True, exist_ok=True)
    if salida.exists():
        salida.unlink()
    # El temporal de siempre: dentro del sandbox es su TMPDIR, que ya se puede escribir.
    perfil = tempfile.mkdtemp(prefix="cotejo-navegador-")
    try:
        proceso = subprocess.Popen(
            argv_captura(tipo, ruta, a_url(destino), salida, perfil, ancho, alto),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            texto, _ = proceso.communicate(timeout=espera)
        except subprocess.TimeoutExpired:
            _matar(proceso)
            texto = (proceso.communicate()[0] or b"")
            resultado["motivo"] = f"{tipo} no terminó en {espera} s"
        _matar(proceso)   # lo que dejara colgado (Firefox a veces deja hijos)
        if es_png(salida):
            resultado.update(ok=True, motivo="")
        elif not resultado["motivo"]:
            cola = texto.decode(errors="replace").strip().splitlines()[-3:]
            resultado["motivo"] = (f"{tipo} salió con {proceso.returncode} sin dejar la "
                                   f"captura: " + " / ".join(cola))
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
    return resultado


def _matar(proceso):
    try:
        os.killpg(proceso.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def main(argumentos=None):
    p = argparse.ArgumentParser(
        prog="python3 -m enrutador.navegador",
        description="Captura PNG de una página con un navegador sin interfaz (vale dentro del "
                    "sandbox del agente).")
    p.add_argument("destino", help="archivo .html o URL (file://, http://localhost:...)")
    p.add_argument("salida", help="dónde dejar el PNG (en tu carpeta de trabajo)")
    p.add_argument("--ancho", type=int, default=1280)
    p.add_argument("--alto", type=int, default=800)
    a = p.parse_args(argumentos)
    hecho = capturar(a.destino, a.salida, a.ancho, a.alto)
    print(json.dumps(hecho, ensure_ascii=False))
    return 0 if hecho["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
