"""Señal de vida del agente en la ficha (v1.3.0, cotejo-21y2ah), sin GTK.

Un agente lanzado desde el board puede pasar minutos sin escribir nada (está pensando) y la
ficha se quedaba en «Empezó con…»: parecía que no había arrancado. Aquí se decide qué enseñar:
cuánto lleva, cuánto hace que se movió y **qué está haciendo**.

**Nunca se dice que un agente vivo está «colgado»**: era una adivinanza que no le sirve a nadie
(¿y qué hago si sale?). Un agente vivo está trabajando; pasados 2 min sin escribir, «Pensando…»,
sin sugerir nada. Lo único que es un hecho es que el proceso ya no existe (`lanzados.MURIO`):
«Se cerró sin entregar», y la ficha ofrece «Retomar», que lanza un agente nuevo que sigue donde
quedó (`retomar.py`).

**Último movimiento** = fecha de modificación del `.log` del agente: el agente escribe una línea
por evento y el sistema anota la hora sin leer nada; un `stat` por segundo no cuesta. La
actividad del worktree se descartó (recorrerlo es caro y quien piensa o lee no toca archivos) y
la bitácora (solo se escribe al entregar o bloquear). Sin log todavía, se cuenta desde `ts`.

**Qué está haciendo** sale de la última línea útil de la cola del log (los últimos 16 KB, nunca
entero) y solo para Claude, que es el único cliente que lanza el board en `stream-json`
(`enrutador/config.py`, `lanzar.argumentos_extra`): su última herramienta en llano («Editando
tareas/app/lanzar.py», «Corriendo: pytest…»). Los logs de OpenCode, Codex y Gemini son texto
libre sin estructura: ahí no se inventa nada y se enseña solo el tiempo. Las rutas van relativas
al worktree (o solo el nombre del archivo) y el comando, con el worktree y el home abreviados. Se
guarda en caché por (log, mtime, tamaño): mientras el log no cambia no se vuelve a leer.
"""

import json
import os
import time

from . import lanzados

PENSANDO_DESDE = 120      # segundos sin escribir para decir «Pensando…»
COLA = 16 * 1024          # cuánto del final del log se mira
RECORTE_COMANDO = 80

ACTIVO, PENSANDO, MURIO = "activo", "pensando", "murio"

_CACHE = {}               # {log: ((mtime, tamaño), descripción)}


def duracion(segundos):
    """«45 s», «3 min», «1 h 05 min»."""
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min"
    return f"{segundos // 3600} h {segundos % 3600 // 60:02d} min"


def ultimo_movimiento(registro):
    """Cuándo escribió por última vez (mtime del log), o el momento del lanzamiento si aún no
    hay log. None si no hay de dónde sacarlo."""
    try:
        return os.path.getmtime(registro.get("log") or "")
    except (OSError, TypeError, ValueError):
        pass
    try:
        return float(registro.get("ts"))
    except (TypeError, ValueError):
        return None


def nivel(silencio):
    return PENSANDO if silencio >= PENSANDO_DESDE else ACTIVO


# --- qué está haciendo ---------------------------------------------------------------------------

def _raiz(registro):
    ruta = (registro.get("worktree") or {}).get("ruta") or registro.get("directorio") or ""
    return str(ruta).rstrip("/")


def _corto(ruta, raiz):
    """Ruta relativa al worktree; fuera de él, solo el nombre del archivo."""
    ruta = str(ruta)
    if raiz and ruta.startswith(raiz + "/"):
        return ruta[len(raiz) + 1:]
    return os.path.basename(ruta.rstrip("/")) or ruta


def _comando(texto, raiz):
    texto = " ".join(str(texto).split())
    if raiz:
        texto = texto.replace(raiz, ".")
    casa = os.path.expanduser("~")
    if casa and casa != "/":
        texto = texto.replace(casa, "~")
    return texto if len(texto) <= RECORTE_COMANDO else texto[:RECORTE_COMANDO - 1].rstrip() + "…"


def _herramienta(nombre, entrada, raiz):
    entrada = entrada if isinstance(entrada, dict) else {}
    archivo = entrada.get("file_path") or entrada.get("notebook_path") or entrada.get("path")
    if nombre in ("Edit", "MultiEdit", "NotebookEdit") and archivo:
        return f"Editando {_corto(archivo, raiz)}"
    if nombre == "Write" and archivo:
        return f"Escribiendo {_corto(archivo, raiz)}"
    if nombre == "Read" and archivo:
        return f"Leyendo {_corto(archivo, raiz)}"
    if nombre == "Bash" and entrada.get("command"):
        return f"Corriendo: {_comando(entrada['command'], raiz)}"
    if nombre in ("Grep", "Glob", "LS"):
        return "Buscando en el código"
    if nombre in ("WebFetch", "WebSearch"):
        return "Buscando en la web"
    if nombre in ("Task", "Agent"):
        return "Consultando a un subagente"
    if nombre == "TodoWrite":
        return "Ordenando su lista de pasos"
    return f"Usando {nombre}" if nombre else ""


def descripcion_de(linea, raiz=""):
    """Lo que dice una línea del log de Claude (stream-json) que hace el agente, o None si la
    línea no es un paso suyo (el resultado de una herramienta, el cierre, texto sin estructura)."""
    texto = linea.strip()
    if not texto.startswith("{"):
        return None
    try:
        datos = json.loads(texto)
    except ValueError:
        return None
    if not isinstance(datos, dict) or datos.get("type") != "assistant":
        return None
    contenido = (datos.get("message") or {}).get("content") or ()
    for parte in reversed([p for p in contenido if isinstance(p, dict)]):
        if parte.get("type") == "tool_use":
            return _herramienta(parte.get("name"), parte.get("input"), raiz) or None
        if parte.get("type") == "text" and str(parte.get("text", "")).strip():
            return "Escribiendo su respuesta"
    return None


def que_hace(registro):
    """Qué está haciendo el agente, en una frase, o "" si no se sabe (cliente sin stream-json,
    log vacío…). Lee solo la cola del log y repite la lectura solo si el log cambió."""
    ruta = (registro or {}).get("log")
    if not ruta:
        return ""
    try:
        info = os.stat(ruta)
    except OSError:
        return ""
    huella = (info.st_mtime, info.st_size)
    previo = _CACHE.get(ruta)
    if previo and previo[0] == huella:
        return previo[1]
    try:
        with open(ruta, "rb") as archivo:
            inicio = max(0, info.st_size - COLA)
            archivo.seek(inicio)
            crudo = archivo.read()
    except OSError:
        return ""
    lineas = crudo.decode("utf-8", "replace").split("\n")
    if inicio:
        lineas = lineas[1:]          # la primera puede venir cortada
    raiz = _raiz(registro)
    hace = ""
    for linea in reversed(lineas):
        hace = descripcion_de(linea, raiz) or ""
        if hace:
            break
    if len(_CACHE) > 64:
        _CACHE.clear()
    _CACHE[ruta] = (huella, hace)
    return hace


def evaluar(registro, ahora=None, movimiento=None):
    """Cómo va el agente de este registro, o None si no está trabajando ni se cerró sin avisar
    (en espera, detenido, terminado: ahí no hay señal de vida que enseñar).

    Devuelve `{nivel, animar, retomar, lleva, silencio, titulo, hace, detalle}`; los textos van
    en llano. `retomar` es True solo si el proceso murió: la ficha ofrece «Retomar».
    `movimiento` fuerza la hora del último movimiento (las pruebas)."""
    e = lanzados.estado(registro)
    if not e or e.get("estado") not in (lanzados.TRABAJANDO, lanzados.MURIO):
        return None
    ahora = float(ahora if ahora is not None else time.time())
    inicio = float(registro.get("ts") or ahora)
    lleva = max(0.0, ahora - inicio)
    ultimo = movimiento if movimiento is not None else ultimo_movimiento(registro)
    silencio = max(0.0, ahora - (ultimo if ultimo is not None else inicio))
    marca = f"Lleva {duracion(lleva)} · último movimiento hace {duracion(silencio)}"
    base = {"lleva": lleva, "silencio": silencio, "detalle": marca}
    if e["estado"] == lanzados.MURIO:
        return {**base, "nivel": MURIO, "animar": False, "retomar": True, "hace": "",
                "titulo": "Se cerró sin entregar"}
    cual = nivel(silencio)
    return {**base, "nivel": cual, "animar": True, "retomar": False, "hace": que_hace(registro),
            "titulo": "Pensando…" if cual == PENSANDO else "Trabajando"}
