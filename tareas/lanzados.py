"""Las tareas que CotejoBoard lanzó a un agente (v1.3.0, cotejo-7xsjb8): el registro y lo que
se lee de él, sin lanzar nada.

Pasar a mano una tarea de Pendiente a Haciendo la despacha en segundo plano
(`enrutador/despacho_board.py`, que es quien lanza). Aquí está la otra mitad, la que no lanza
nada y que piden el board y quien venga detrás (pausar y retomar, el fin y el rechazo): un
registro por tarea en `<estado>/lanzados/<id>.json` con lo que hace falta para seguirla,
pararla o retomarla —`pid`, `programa`, `host`, `log`, `cliente`, `modelo`, `worktree`,
`directorio`, `comando`, `prompt`— y la lectura en vivo de su salida para el detalle de la
tarea. Sin GTK y sin importar el enrutador al cargarse, como `preparacion.py`, del que copia la
forma: anotado con pid en cuanto existe, la otra mitad cuando vuelve, y «¿murió sin volver?»
con `enrutador.procesos.anotado_muerto`, la función de `revisar`.

Las fases que se guardan y el `estado` que se lee de ellas:

- `lanzado` → `trabajando` mientras el proceso vive; `murio` si ya no está y nadie lo vio volver.
- `terminado` → `terminado`, con su `codigo`.
- `en-espera` → `en-espera`: se pidió lanzarla y no había hueco (`cotejo capacidad` dijo 0).
  La tarea sigue en Pendiente y nada la lanza sola: se vuelve a arrastrar cuando haya hueco.
  El board lo enseña con un chip «En espera» en la carta y el motivo en su ficha.
- `detenido` → `detenido`: alguien lo paró (`despacho_board.detener`); la tarea y su worktree
  no se tocan. Devolverla a Pendiente desde el board la deja así (`despacho_board.pausar`), y
  volver a lanzarla es una reanudación: `reanudacion` dice qué vez es, de quién retoma y
  cuántos commits y cambios encontró (la nota entera, de `retomar.py`, va en `prompt`).

Cuando el agente vuelve se le hace el fin una sola vez (`reclamar_fin`, clave `fin` con su
`como`: `entrego`, `sin-entregar` u `otro`, cotejo-o253bs). El que terminó sin entregar queda
`detenido` con el motivo, como uno pausado; `murio` marca al que se cerró sin que nadie lo viera
y `rechazo` guarda lo que se pidió cambiar al devolverlo desde Para comprobar.

**La salida del agente en vivo.** El agente escribe a su `.log` (el de Claude va en
`stream-json`, una línea por evento); `Seguimiento` lee solo lo nuevo en cada `nuevas()` y
`legible` lo pasa a texto: lo que dice el agente, qué herramienta usa y cómo terminó. Lo que no
es JSON (Codex, OpenCode, Gemini) va tal cual.
"""

import json
import os
import socket
import threading
import time

from . import rutas, worktrees

ESQUEMA = 1

LANZADO, TERMINADO, EN_ESPERA, DETENIDO = "lanzado", "terminado", "en-espera", "detenido"
TRABAJANDO, MURIO = "trabajando", "murio"
# Cómo acabó un lanzamiento (`fin.como`, cotejo-o253bs): entregó, terminó sin entregar (y se
# devolvió a Pendiente), o la tarea ya estaba en otra parte (la bloqueó o la movió alguien).
FIN_ENTREGO, FIN_SIN_ENTREGAR, FIN_OTRO = "entrego", "sin-entregar", "otro"

# Cuánto de un log largo se enseña al abrir el detalle: lo de antes está en el archivo.
RECORTE_INICIAL = 16 * 1024
LINEA_MAX = 2000

_CANDADO = threading.RLock()


def carpeta():
    """`<estado>/lanzados`. Se calcula en cada llamada: sigue a `COTEJO_ESTADO`."""
    return rutas.estado() / "lanzados"


def _ruta(tarea_id):
    return carpeta() / f"{worktrees.seguro(tarea_id)}.json"


def ruta_log(tarea_id):
    return carpeta() / f"{worktrees.seguro(tarea_id)}.log"


def guardar(registro):
    """Reemplazo atómico: quien lo lee (el board, la barra) nunca lo ve a medias."""
    ruta = _ruta(registro["id"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(json.dumps({"esquema": ESQUEMA, **registro}, ensure_ascii=False),
                        encoding="utf-8")
    os.replace(temporal, ruta)
    return registro


def leer(tarea_id):
    try:
        datos = json.loads(_ruta(tarea_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def borrar(tarea_id):
    """Quita el registro (no el log). Para cuando la tarea cambió de id al tomarla."""
    with _CANDADO:
        try:
            _ruta(tarea_id).unlink()
        except OSError:
            pass


def todos():
    """{id: registro} de todas las tareas lanzadas. Uno roto se salta."""
    if not carpeta().is_dir():
        return {}
    salida = {}
    for archivo in carpeta().glob("*.json"):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict) and datos.get("id"):
            salida[datos["id"]] = datos
    return salida


def poner_en_espera(tarea, modelo, motivo):
    """Se pidió lanzarla y no cabe: queda anotada en espera, con el motivo en llano."""
    with _CANDADO:
        # Si ya se lanzó antes (una tarea pausada que vuelve a moverse sin hueco), lo de aquel
        # lanzamiento se queda: es lo que necesita la nota de retomar (`retomar.py`).
        previo = leer(tarea["id"]) or {}
        if previo.get("fase") == DETENIDO and previo.get("motivo"):
            previo["motivo_antes"] = previo["motivo"]
        previo.update({"id": tarea["id"], "proyecto": tarea.get("proyecto", ""),
                       "modelo": modelo, "fase": EN_ESPERA, "motivo": motivo,
                       "ts": int(time.time())})
        return guardar(previo)


def quitar_de_espera(tarea_id):
    """Se arrepintió: borra el registro de espera sin lanzar nada. True si estaba en espera.

    Si antes hubo un lanzamiento (una pausada que se movió sin hueco), el registro vuelve a lo
    que era (detenido, con su motivo de entonces) para que retomar siga funcionando; si no, se
    borra entero (el log se queda). Nunca toca la tarea ni su modelo en la fuente.
    """
    with _CANDADO:
        registro = leer(tarea_id)
        if not registro or registro.get("fase") != EN_ESPERA:
            return False
        if registro.get("pid") and registro.get("log"):
            registro["fase"] = DETENIDO
            registro["motivo"] = registro.pop("motivo_antes", "") or ""
            guardar(registro)
        else:
            borrar(tarea_id)
        return True


def anotar_lanzado(registro, pid, programa):
    """Lo que se anota en cuanto el proceso existe, como `al_lanzar` en `despachar`."""
    with _CANDADO:
        registro.update(fase=LANZADO, pid=pid, programa=programa, host=socket.gethostname(),
                        ts=int(time.time()))
        for clave in ("codigo", "terminado_ts", "motivo", "detenido_ts", "motivo_antes",
                      "fin", "murio"):
            registro.pop(clave, None)
        return guardar(registro)


def anotar_terminado(tarea_id, codigo, pid=None, murio=False):
    """El proceso volvió. Si ya no está `lanzado` (lo pararon) o es de otro lanzamiento (`pid`
    ya es otro), no se pisa y se devuelve como está. `murio`: nadie lo vio volver (el board
    estaba cerrado) y no hay código (`codigo` None)."""
    with _CANDADO:
        registro = leer(tarea_id)
        if registro is None or registro.get("fase") != LANZADO:
            return registro
        if pid is not None and registro.get("pid") != pid:
            return registro
        registro.update(fase=TERMINADO, codigo=None if codigo is None else int(codigo),
                        terminado_ts=int(time.time()))
        if murio:
            registro["murio"] = True
        return guardar(registro)


def reclamar_fin(tarea_id, pid):
    """True solo la primera vez para el lanzamiento de `pid`: quien lo gana hace el fin
    (`despacho_board.fin`). Así el hilo que lo esperaba y la recogida de los muertos nunca
    lo hacen dos veces."""
    with _CANDADO:
        registro = leer(tarea_id)
        if not registro or registro.get("pid") != pid or registro.get("fin"):
            return False
        registro["fin"] = {"como": "", "ts": int(time.time())}
        guardar(registro)
        return True


def actualizar(tarea_id, **campos):
    """Cambia campos sin tocar la fase. None si no hay registro."""
    with _CANDADO:
        registro = leer(tarea_id)
        if registro is None:
            return None
        registro.update(campos)
        return guardar(registro)


def cambiar_fase(tarea_id, fase, **extra):
    with _CANDADO:
        registro = leer(tarea_id)
        if registro is None:
            raise KeyError(tarea_id)
        registro.update(fase=fase, **extra)
        return guardar(registro)


def _muerto(registro):
    from enrutador import procesos  # aquí y no arriba: `tareas` no importa el enrutador al cargar
    return procesos.anotado_muerto(registro)


def estado(registro):
    """Cómo va, para el board y para quien siga. No escribe nada."""
    if registro is None:
        return None
    fase = registro.get("fase")
    salida = {k: registro.get(k) for k in ("id", "proyecto", "cliente", "modelo", "pid", "log",
                                          "worktree", "directorio", "ts", "codigo",
                                          "terminado_ts", "reanudacion", "fin", "rechazo",
                                          "murio")}
    salida["por_que"] = ""
    if fase == EN_ESPERA:
        cual = EN_ESPERA
        salida["por_que"] = registro.get("motivo") or "No había hueco para otro agente."
    elif fase == LANZADO:
        cual = MURIO if _muerto(registro) else TRABAJANDO
        if cual == MURIO:
            salida["por_que"] = "El proceso del agente ya no existe y nadie lo vio terminar."
    elif fase == TERMINADO:
        cual = TERMINADO
    elif fase == DETENIDO:
        cual = DETENIDO
        salida["por_que"] = registro.get("motivo") or ""
    else:
        cual = fase or ""
    salida["estado"] = cual
    return salida


def pids_propios():
    """Los pids de los agentes que el board lanzó y siguen en `lanzado`: los únicos que
    `cotejo capacidad` cuenta como agentes en curso (las sesiones de la persona, no)."""
    return {r["pid"] for r in todos().values()
            if r.get("fase") == LANZADO and isinstance(r.get("pid"), int)}


def en_espera():
    """{id: motivo} de las que esperan hueco: lo que el board pinta en Pendiente."""
    return {i: r.get("motivo") or "" for i, r in todos().items() if r.get("fase") == EN_ESPERA}


def termino_sin_entregar(registro):
    """¿El agente terminó o murió sin entregar y volvió a Pendiente (`fin.como`)?

    Es lo que distingue su ficha de una pausada a mano: una «pausada» la paró una persona, esta
    se cerró sola. `registro` es lo que devuelve `leer(id)`."""
    return bool(registro) and (registro.get("fin") or {}).get("como") == FIN_SIN_ENTREGAR


# --- la salida en vivo --------------------------------------------------------------------------

def _resumen_entrada(entrada):
    """Lo que dice una llamada a una herramienta, en una línea: el comando, el archivo…"""
    if not isinstance(entrada, dict):
        return ""
    for clave in ("command", "file_path", "path", "pattern", "description", "url", "prompt"):
        if entrada.get(clave):
            return " ".join(str(entrada[clave]).split())[:200]
    return ""


def legible(linea):
    """Una línea del log como texto para una persona, o None si no dice nada que enseñar.

    Las de `claude -p --output-format stream-json` son JSON: de ellas se enseña lo que escribe
    el agente, cada herramienta que usa (`→ Bash: pytest`) y cómo terminó. Lo que no es JSON va
    tal cual, recortado.
    """
    texto = linea.strip()
    if not texto:
        return None
    if not texto.startswith("{"):
        return texto[:LINEA_MAX]
    try:
        datos = json.loads(texto)
    except ValueError:
        return texto[:LINEA_MAX]
    if not isinstance(datos, dict):
        return texto[:LINEA_MAX]
    tipo = datos.get("type")
    if tipo == "assistant":
        partes = []
        for parte in (datos.get("message") or {}).get("content") or ():
            if not isinstance(parte, dict):
                continue
            if parte.get("type") == "text" and str(parte.get("text", "")).strip():
                partes.append(str(parte["text"]).strip()[:LINEA_MAX])
            elif parte.get("type") == "tool_use":
                dice = _resumen_entrada(parte.get("input"))
                partes.append(f"→ {parte.get('name', '?')}" + (f": {dice}" if dice else ""))
        return "\n".join(partes) or None
    if tipo == "result":
        final = " ".join(str(datos.get("result") or "").split())[:400]
        cabeza = "— Terminó con un error" if datos.get("is_error") else "— Terminó"
        return cabeza + (f": {final}" if final else "")
    if tipo == "system" and datos.get("subtype") == "init":
        return "— Empezó" + (f" con {datos['model']}" if datos.get("model") else "")
    return None


class Seguimiento:
    """Lee la salida de un agente lanzado de a poco: cada `nuevas()` trae solo lo que llegó.

    Empieza donde empezó este lanzamiento (`log_desde`), o en los últimos `RECORTE_INICIAL`
    bytes si ya escribió mucho. Una línea a medio escribir se guarda para la vuelta siguiente.
    Si el registro cambia de lanzamiento (otro `ts`), vuelve a empezar.
    """

    def __init__(self, tarea_id):
        self.id = tarea_id
        self.ts = None
        self.desde = 0
        self.resto = b""

    def _empezar(self, registro):
        self.ts = registro.get("ts")
        self.resto = b""
        inicio = int(registro.get("log_desde") or 0)
        try:
            tamano = os.path.getsize(registro.get("log") or "")
        except OSError:
            tamano = 0
        self.desde = max(inicio, tamano - RECORTE_INICIAL)

    def nuevas(self, registro=None):
        """Las líneas legibles que llegaron desde la última vez."""
        registro = registro if registro is not None else leer(self.id)
        if not registro or not registro.get("log"):
            return []
        if registro.get("ts") != self.ts:
            self._empezar(registro)
        try:
            with open(registro["log"], "rb") as archivo:
                archivo.seek(self.desde)
                crudo = archivo.read()
        except OSError:
            return []
        self.desde += len(crudo)
        crudo = self.resto + crudo
        lineas = crudo.split(b"\n")
        self.resto = lineas.pop()
        return [t for t in (legible(l.decode(errors="replace")) for l in lineas) if t]


def situacion(e, ahora=None):
    """La frase de arriba del detalle: qué está pasando con el agente, en llano."""
    if not e:
        return ""
    ahora = int(ahora if ahora is not None else time.time())
    quien = e.get("modelo") or "el agente"
    cual = e.get("estado")
    if cual == TRABAJANDO:
        minutos = max(0, ahora - int(e.get("ts") or ahora)) // 60
        haciendo = "retomándola" if e.get("reanudacion") else "trabajando en ella"
        return f"{quien} está {haciendo}" + (f" desde hace {minutos} min" if minutos else "")
    como = (e.get("fin") or {}).get("como")
    if como == FIN_ENTREGO:
        return f"{quien} terminó y entregó: está en Para comprobar"
    if como == FIN_SIN_ENTREGAR:
        return (f"{quien} terminó sin entregar: la tarea volvió a Pendiente y su worktree "
                f"se queda para retomarla")
    if cual == TERMINADO:
        if e.get("codigo") is None:
            return f"{quien} se cerró sin que nadie lo viera terminar"
        return (f"{quien} terminó" if e.get("codigo") == 0
                else f"{quien} terminó con un error (código {e.get('codigo')})")
    if cual == MURIO:
        return f"{quien} ya no está trabajando: {e['por_que']}"
    if cual == DETENIDO:
        return f"Se detuvo a {quien}" + (f": {e['por_que']}" if e.get("por_que") else "")
    if cual == EN_ESPERA:
        return f"En espera: {e['por_que']}"
    return ""
