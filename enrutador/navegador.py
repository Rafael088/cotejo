"""Capturas PNG de una entrega, hechas por CotejoBoard **fuera** del sandbox del agente.

El agente entrega con `--captura-desde <archivo|url>` y no arranca ningún navegador: esa petición
queda en la bitácora y `capturar_pendientes()` la completa aquí fuera, con una imagen móvil y otra
de escritorio por destino. Así la entrega ya no depende de que un navegador aguante el sandbox.

La prueba anterior emulaba esa jaula con bubblewrap y daba verde, pero en el sandbox real de
Claude Code Firefox 155 terminaba sin PNG (clone EPERM, WebRender y dconf de solo lectura;
reproducido el 2026-10-27, cotejo-v40nc1). No se abren sockets, espacios de nombres ni escritura
para rodearlo: se quita el navegador de dentro. Chromium sigue sin ser una alternativa ahí, porque
su ProcessSingleton necesita el socket de Unix que el seccomp de Claude niega.

`capturar()` es la pieza de más abajo: elige Firefox (o Chromium fuera del sandbox), le da un
perfil de usar y tirar, lo mata si se cuelga y comprueba que sale un PNG de verdad. La línea
`COMO_CAPTURAR` queda para diagnóstico directo, no en el encargo de los agentes.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import types
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


def disponible(entorno=None, which=shutil.which):
    """¿Hay un navegador que valga aquí? Se evalúa al llamar, no al importar el módulo."""
    return elegir(entorno, which)[0] is not None


def disponible_para_el_agente(which=shutil.which):
    """¿Puede el agente ver su trabajo? Se mira como si estuviera encerrado (solo Firefox): el
    encargo y la nota se arman fuera del sandbox, y prometerle Chromium a un agente encerrado
    es darle un comando que se cae."""
    return disponible({"COTEJO_SANDBOX": "1"}, which)


def a_url(destino):
    """Una URL tal cual; una ruta, como `file://` absoluta."""
    texto = str(destino)
    if "://" in texto or texto.startswith(("about:", "data:")):
        return texto
    return Path(texto).expanduser().resolve().as_uri()


# El perfil de captura no puede salir a internet: la captura corre fuera del sandbox del agente
# y un HTML del worktree podría pedir `https://ajeno.com/?d=<secreto>`. Todo va a un proxy
# muerto salvo lo local; los nombres son los de Firefox (comprobados en `greprefs.js` y
# `libxul.so`, no inventados). `allow_hijacking_localhost` en false deja que lo local no pase
# por el proxy, y se apagan prefetch, DNS prefetch y conexiones especulativas.
PREFERENCIAS = {
    "network.proxy.type": 1,
    "network.proxy.http": "127.0.0.1",
    "network.proxy.http_port": 9,
    "network.proxy.ssl": "127.0.0.1",
    "network.proxy.ssl_port": 9,
    "network.proxy.no_proxies_on": "localhost, 127.0.0.1, [::1]",
    "network.proxy.allow_hijacking_localhost": False,
    "network.prefetch-next": False,
    "network.dns.disablePrefetch": True,
    "network.dns.disablePrefetchFromHTTPS": True,
    "network.http.speculative-parallel-limit": 0,
}


def prefs_del_perfil():
    """El `user.js` que se deja en el perfil temporal antes de arrancar Firefox."""
    return "".join(f"user_pref({json.dumps(clave)}, "
                   f"{json.dumps(valor, ensure_ascii=False)});\n"
                   for clave, valor in PREFERENCIAS.items())


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
        (Path(perfil) / "user.js").write_text(prefs_del_perfil(), encoding="utf-8")
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


# --- peticiones de la entrega: el navegador corre aquí fuera, nunca en el Bash del agente --------

TAMANOS = ((390, 844), (1280, 800))
_CAPTURAS_EN_CURSO = set()
_CAPTURAS_CANDADO = threading.Lock()
_CAPTURAS_HILO = None


def _carpeta_de_la_entrega(entrega, trabajo=None):
    """Dónde se resuelven los archivos relativos: el worktree de la entrega, no el repo principal."""
    if trabajo:
        return Path(trabajo).expanduser().resolve()
    from tareas import lanzados
    registro = lanzados.leer(entrega.get("id", "")) or {}
    donde = registro.get("trabajo") or (entrega.get("git") or {}).get("repo")
    return Path(donde or os.getcwd()).expanduser().resolve()


def _destino(texto, trabajo):
    """URL local o archivo dentro del trabajo. Lo demás no se abre aunque el agente lo pida."""
    from tareas import capturas
    return capturas.destino_seguro(texto, trabajo)


def _anotar_resultado(entrega, guardadas, avisos):
    """Otra línea append-only; `bitacora.ultima_entrega` la junta con la entrega al leer."""
    from tareas import bitacora
    tarea = types.SimpleNamespace(
        id=entrega.get("id", ""), texto=entrega.get("texto", ""),
        donde=entrega.get("nota", ""), agente=entrega.get("agente", ""))
    proyecto = types.SimpleNamespace(nombre=entrega.get("proyecto", ""))
    bitacora.anotar("capturar", proyecto, tarea, entrega_cuando=entrega.get("cuando"),
                    capturas=guardadas, capturas_avisos=avisos)


def capturar_entrega(entrega, trabajo=None, sacar=None):
    """Saca fuera del sandbox las capturas que pidió una entrega y anota imágenes o motivos.

    Nunca cambia la tarea ni levanta un error por el navegador: la entrega ya está hecha y una
    captura fallida debe quedar explicada, no convertida en un bloqueo. None si otro hilo ya la
    está capturando.
    """
    clave = (entrega.get("id", ""), entrega.get("cuando"))
    with _CAPTURAS_CANDADO:
        if clave in _CAPTURAS_EN_CURSO:
            return None
        _CAPTURAS_EN_CURSO.add(clave)
    try:
        from tareas import capturas
        sacar = sacar or capturar
        base = _carpeta_de_la_entrega(entrega, trabajo)
        rutas, avisos = [], []
        with tempfile.TemporaryDirectory(prefix="cotejo-capturas-") as temporal:
            for numero, pedido in enumerate(entrega.get("capturas_solicitadas") or (), 1):
                try:
                    destino = _destino(pedido, base)
                except ValueError as error:
                    avisos.append(str(error))
                    continue
                for ancho, alto in TAMANOS:
                    salida = Path(temporal) / f"{numero}-{ancho}.png"
                    try:
                        hecho = sacar(destino, salida, ancho=ancho, alto=alto, entorno={})
                    except Exception as error:  # noqa: BLE001 — una captura no deshace una entrega
                        hecho = {"ok": False, "motivo": str(error)}
                    if hecho.get("ok") and es_png(salida):
                        rutas.append(str(salida))
                    else:
                        avisos.append(f"{pedido} ({ancho}×{alto}): "
                                      f"{hecho.get('motivo') or 'no salió el PNG'}")
            if rutas:
                try:
                    # Lo que ya venía (una `--captura` del agente) se copia antes: `guardar`
                    # rehace la carpeta de capturas y borraría los originales a medio copiar.
                    anteriores = []
                    for numero_antes, anterior in enumerate(entrega.get("capturas") or ()):
                        ruta = anterior.get("ruta") if isinstance(anterior, dict) else None
                        if ruta and Path(ruta).is_file():
                            copia = Path(temporal) / f"antes-{numero_antes}.png"
                            shutil.copyfile(ruta, copia)
                            anteriores.append(str(copia))
                    guardadas = capturas.guardar(entrega["id"], anteriores + rutas)
                except (KeyError, OSError, ValueError) as error:
                    guardadas, avisos = [], avisos + [f"No pude guardar las capturas: {error}"]
            else:
                guardadas = []
        _anotar_resultado(entrega, guardadas, avisos)
        return {"capturas": guardadas, "capturas_avisos": avisos}
    finally:
        with _CAPTURAS_CANDADO:
            _CAPTURAS_EN_CURSO.discard(clave)


def capturar_pendientes():
    """Completa todas las peticiones aún sin resultado; devuelve sus resultados."""
    from tareas import bitacora
    return [resultado for entrega in bitacora.pendientes_de_captura()
            if (resultado := capturar_entrega(entrega)) is not None]


def programar_capturas():
    """Lo mismo sin bloquear el refresco del board; un solo trabajador a la vez."""
    global _CAPTURAS_HILO
    from tareas import bitacora
    with _CAPTURAS_CANDADO:
        if _CAPTURAS_HILO and _CAPTURAS_HILO.is_alive():
            return _CAPTURAS_HILO
        if not bitacora.pendientes_de_captura():
            return None
        _CAPTURAS_HILO = threading.Thread(target=capturar_pendientes,
                                          name="capturas-de-entregas", daemon=True)
        _CAPTURAS_HILO.start()
        return _CAPTURAS_HILO


def esperar_capturas(timeout=120):
    """Espera al trabajador de `programar_capturas` (pruebas y cierre ordenado)."""
    hilo = _CAPTURAS_HILO
    if hilo:
        hilo.join(timeout)
    return not (hilo and hilo.is_alive())


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
