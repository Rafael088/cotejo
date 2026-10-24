"""Lanzar desde el board (v1.3.0, cotejo-7xsjb8): pasar a mano una tarea de Pendiente a
Haciendo la despacha en segundo plano con su modelo asignado.

Es la segunda excepción a «nada en segundo plano», después de preparar un proyecto
(`preparar.py`), y por la misma razón: la persona lo pidió moviendo la carta, y lo que hace el
agente se ve en vivo en el detalle de la tarea. Nada aquí lanza un agente por su cuenta: solo
`lanzar`, que llama el board cuando alguien mueve una carta.

Las reglas son las de `despachar`, en el mismo orden y con las mismas piezas, sin un camino
propio para ninguna:

1. **n0 no se lanza** (`EsDeUnaPersona`): la decisión del enrutador dice que es de una persona.
2. **Sin modelo se pregunta** (`FaltaModelo`, con la propuesta y su porqué): las reglas
   proponen, no autorizan a gastar. El board pregunta y guarda la respuesta con «asignar».
3. **Si no cabe, queda en espera** (`SinHueco`): `capacidad` mide la máquina; con 0 la tarea
   sigue en Pendiente anotada en espera (`tareas/lanzados.py`) con el motivo en llano, y nada
   la lanza sola después: se vuelve a mover cuando haya hueco.
4. Lo que impediría lanzar (el cliente no está, el repo sin commits) se dice **antes** de
   tomarla (`despacho.antes_de_tomar`, con el motor `headless`, que es el que sabe de clientes).
5. Se toma a nombre del modelo (`cotejo.tomar`), se le crea su worktree (`tareas/worktrees.py`)
   y se lanza el cliente sin interfaz (`motores/fondo.py`) con el encargo de siempre
   (`encargo.armar`), el mismo `cotejo` que el board en el PATH (`mismo_cotejo.py`) y permiso
   para escribir solo donde hace falta (`clientes.Cliente.permisos`, como en preparar). Si algo
   falla después de tomarla, se suelta con el motivo.

Toda decisión deja línea en la bitácora de despachos, también las negativas, con
`motor: "board"`: `revisar` las cuenta como las de `despachar`.

Para quien venga detrás (pausar y retomar, el fin y el rechazo) quedan `lanzar`, `estado`,
`detener` y `vigilar`, y el registro por tarea de `tareas/lanzados.py`.
"""

import socket
import subprocess
import threading
import time
from pathlib import Path

from tareas import lanzados, worktrees
from tareas.cli import ErrorCLI
from . import (bitacora, capacidad, clientes, config as cfg, cotejo as f, decision, despacho,
               encargo as enc, mismo_cotejo, motor, niveles, preparar, procesos, reglas)
from .motores import fondo

MOTOR = "board"
# Los mismos escalones en que `despachar` se fía para gastar sin preguntar.
LO_DIJO_UNA_PERSONA = ("override", "asignacion")

NOTA = ("Te lanzó CotejoBoard sin nadie delante: nadie va a contestarte preguntas mientras "
        "trabajas. Si algo te impide seguir, no lo dejes a medias: bloquéala con el motivo.")


class NoSePuede(Exception):
    """Lo que impide lanzar, en llano, para enseñarlo tal cual en el board."""


class EsDeUnaPersona(NoSePuede):
    """La tarea es del nivel humano (n0): no se lanza ningún agente."""


class FaltaModelo(NoSePuede):
    """Nadie le asignó modelo. Trae la propuesta del enrutador y su porqué."""

    def __init__(self, mensaje, propuesta, razon):
        super().__init__(mensaje)
        self.propuesta = propuesta
        self.razon = razon


class SinHueco(NoSePuede):
    """`capacidad` dice que no cabe otro agente: la tarea queda en espera."""


# --- lo que decide ------------------------------------------------------------------------------

def _anotar(tarea, elegida, **extra):
    return bitacora.anotar(
        tarea=tarea.get("id"), texto=tarea.get("texto"), proyecto=tarea.get("proyecto"),
        nivel=elegida.nivel.clave, modelo=elegida.nivel.modelo,
        modelo_id=elegida.nivel.modelo_id, por=elegida.por, regla=elegida.regla, motor=MOTOR,
        **extra)


def _rechazar(tarea, elegida, rechazo, error):
    """Toda negativa deja línea antes de decirse (la regla de `despachar`)."""
    _anotar(tarea, elegida, tomada=False, ok=False, rechazo=rechazo)
    raise error


def decidir(tarea, config):
    """La decisión del enrutador para esta tarea (sin override: lo que hay en la nota)."""
    humano, nivel = reglas.cargar(config.get("reglas_extra"), config.get("reglas_apagadas"))
    return decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                             niveles_extra=niveles.personalizados(config.get("modelos")),
                             alias_persona=config.get("alias_persona"))


def hueco(config):
    """Lo que dice `capacidad` ahora: `capacidad.calcular` sobre la máquina medida."""
    foto = capacidad.leer(c.ejecutable for c in clientes.CLIENTES.values())
    return capacidad.calcular(foto, config.get("capacidad") or {})


def motivo_sin_hueco(calculo):
    """Por qué no cabe, para quien no programa."""
    limita = calculo.get("limita")
    por = {"memoria": "no queda memoria libre para otro agente",
           "cpu": "el procesador ya va muy cargado",
           "maximo": (f"ya corren los {calculo.get('limites', {}).get('maximo')} agentes que "
                      f"permite tu configuración")}.get(limita, "la máquina no da para otro")
    return (f"No hay hueco para otro agente ahora: {por}. La tarea queda en Pendiente, en "
            f"espera; muévela otra vez a Haciendo cuando termine alguno.")


def _cliente_de(elegida):
    try:
        return clientes.de(elegida.nivel.cliente)
    except clientes.ClienteDesconocido as error:
        raise NoSePuede(str(error)) from error


def comando(config, cliente, elegida, prompt, carpetas):
    """El argv sin interfaz: el del motor `headless` para ese cliente, más
    `lanzar.argumentos_extra.<cliente>` y lo que le deja escribir en `carpetas`."""
    propios = preparar._propios(config, cliente)
    extra = (list(propios.get("argumentos_extra") or ()) +
             list(((config.get("lanzar") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ()) +
             cliente.permisos(carpetas)[0])
    return cliente.argv_sin_interfaz(
        cliente.modelo_de(elegida.nivel.modelo, elegida.nivel.modelo_id), prompt,
        comando=propios.get("comando"), extra=extra)


def carpetas_de_escritura(trabajo, worktree=None):
    """Las de preparar para la carpeta de trabajo (ella, la config de Cotejo y la de estado)
    más el `.git` del repo si trabaja en un worktree: ahí van sus commits."""
    lista = preparar.carpetas_de_escritura(trabajo)
    if worktree:
        git = Path(worktree["repo"]) / ".git"
        if git.is_dir():
            lista.append(str(git))
    return list(dict.fromkeys(lista))


# --- lanzar -------------------------------------------------------------------------------------

def lanzar(tarea_id, al_terminar=None, config=None):
    """Lanza la tarea con su modelo asignado y devuelve su estado (`lanzados.estado`).

    Levanta `EsDeUnaPersona`, `FaltaModelo`, `SinHueco` o `NoSePuede` sin haber tomado nada.
    `al_terminar(estado)` se llama desde otro hilo cuando el agente vuelve.
    """
    config = config if config is not None else cfg.cargar()
    cotejo = f.Cotejo()
    try:
        tarea = cotejo.tarea(tarea_id)
    except ErrorCLI as error:
        raise NoSePuede(str(error)) from error
    try:
        elegida = decidir(tarea, config)
    except ValueError as error:
        raise NoSePuede(str(error)) from error

    if not elegida.despachable:
        _rechazar(tarea, elegida, "veto", EsDeUnaPersona(
            f"Es una tarea para una persona ({elegida.razon}): no lancé ningún agente."))
    if elegida.por not in LO_DIJO_UNA_PERSONA:
        _rechazar(tarea, elegida, "falta_modelo", FaltaModelo(
            f"Nadie le ha asignado modelo. La propuesta es {elegida.nivel.modelo} "
            f"({elegida.razon}).", elegida.nivel.modelo, elegida.razon))
    if tarea.get("estado") != "pendiente":
        _rechazar(tarea, elegida, "no_pendiente", NoSePuede(
            f"La tarea no está pendiente, está en «{tarea.get('estado')}»."))

    calculo = hueco(config)
    if calculo.get("caben") == 0:
        motivo = motivo_sin_hueco(calculo)
        lanzados.poner_en_espera(tarea, elegida.nivel.modelo, motivo)
        _rechazar(tarea, elegida, "capacidad", SinHueco(motivo))

    proyecto = tarea.get("proyecto", "")
    directorio = cfg.directorio_de(config, proyecto) or cotejo.carpeta_de(proyecto)
    if not directorio:
        _rechazar(tarea, elegida, "sin_carpeta", NoSePuede(
            f"No sé en qué carpeta vive el proyecto {proyecto}, y el agente necesita una para "
            f"trabajar: ponla en enrutador.proyectos de la config."))
    directorio = Path(directorio)

    ajustes_wt = config.get("worktrees") or {}
    base_wt = worktrees.carpeta_base(ajustes_wt.get("carpeta"))
    vedadas = cotejo.carpetas_propias()
    plan_wt = None
    if ajustes_wt.get("aislar") is not False:
        try:
            plan_wt = worktrees.planear(tarea["id"], directorio, base_wt, vedadas)
        except worktrees.ErrorWorktree as error:
            _rechazar(tarea, elegida, "worktree", NoSePuede(error.mensaje))

    cliente = _cliente_de(elegida)

    def armar(tarea_ahora, worktree):
        trabajo = Path(worktree["ruta"]) if worktree else directorio
        return motor.Encargo(
            prompt=enc.armar(tarea_ahora, elegida, directorio, NOTA, worktree),
            modelo=elegida.nivel.modelo, modelo_id=elegida.nivel.modelo_id,
            directorio=trabajo, tarea_id=tarea_ahora.get("id", ""), proyecto=proyecto,
            cliente=elegida.nivel.cliente)

    headless = motor.abrir("headless", config)
    for rechazo, problema in despacho.antes_de_tomar(headless, armar(tarea, plan_wt), plan_wt):
        _rechazar(tarea, elegida, rechazo, NoSePuede(problema))

    # Tomarla: desde aquí, cualquier fallo la suelta antes de decir que no.
    id_antes, asignada = tarea["id"], tarea.get("agente", "")
    try:
        tarea = cotejo.tomar(tarea["id"], elegida.nivel.modelo)
    except ErrorCLI as error:
        _rechazar(tarea, elegida, "no_pendiente", NoSePuede(str(error)))

    def soltar(motivo, rechazo):
        try:
            cotejo.soltar(tarea["id"], motivo, asignada=asignada)
        except ErrorCLI:
            pass  # la línea cambió mientras tanto: no se pisa, y el error de abajo lo dice
        _rechazar(tarea, elegida, rechazo,
                  NoSePuede(f"{motivo} La tarea vuelve a estar pendiente."))

    worktree = None
    if plan_wt:
        try:
            plan_wt = worktrees.planear(tarea["id"], directorio, base_wt, vedadas)
            worktree = worktrees.crear(tarea["id"], plan_wt)
        except worktrees.ErrorWorktree as error:
            soltar(f"No se pudo crear su worktree: {error.mensaje}", "worktree")
    encargo = armar(tarea, worktree)
    trabajo = Path(encargo.directorio)
    argv = comando(config, cliente, elegida, encargo.prompt,
                   carpetas_de_escritura(trabajo, worktree))
    log = lanzados.ruta_log(tarea["id"])
    registro = {"id": tarea["id"], "proyecto": proyecto, "texto": tarea.get("texto", ""),
                "cliente": cliente.nombre, "modelo": elegida.nivel.modelo,
                "modelo_id": elegida.nivel.modelo_id, "asignada": asignada,
                "directorio": str(directorio), "trabajo": str(trabajo),
                "worktree": ({k: worktree.get(k) for k in ("ruta", "rama", "repo")}
                             if worktree else None),
                "comando": argv, "prompt": encargo.prompt, "log": str(log),
                "log_desde": _tamano(log),
                "lanzamientos": int((lanzados.leer(tarea["id"]) or {}).get("lanzamientos")
                                    or 0) + 1}
    try:
        entorno = mismo_cotejo.entorno(cliente.permisos(
            carpetas_de_escritura(trabajo, worktree))[1])
        ajustes = (config.get("motores") or {}).get("headless") or {}
        proceso = fondo.lanzar(argv, trabajo, str(log), ajustes, entorno,
                               etiqueta="tarea-" + worktrees.seguro(tarea["id"]))
    except OSError as error:
        soltar(f"No pude lanzar «{argv[0]}»: {error}.", "motor")
    lanzados.anotar_lanzado(registro, proceso.pid, argv[0])
    if id_antes != tarea["id"]:
        lanzados.borrar(id_antes)   # tomarla le dio su id definitivo: el «en espera» era del otro
    _anotar(tarea, elegida, tomada=True, fase="lanzado", comando=argv, pid=proceso.pid,
            programa=argv[0], host=socket.gethostname(),
            **({"worktree": registro["worktree"]} if worktree else {}))
    vigilar(proceso, tarea, elegida,
            (config.get("lanzar") or {}).get("timeout_seg") or ajustes.get("timeout_seg", 3600),
            al_terminar)
    return lanzados.estado(lanzados.leer(tarea["id"]))


def _tamano(ruta):
    try:
        return Path(ruta).stat().st_size
    except OSError:
        return 0


def vigilar(proceso, tarea, elegida, timeout, al_terminar=None):
    """Espera al proceso en un hilo, anota cómo volvió (registro y bitácora de despachos) y
    llama `al_terminar(estado)`. Devuelve el hilo."""
    def esperar():
        try:
            codigo = proceso.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            procesos.terminar(proceso.pid)
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()
            codigo = 124
        registro = lanzados.anotar_terminado(tarea["id"], codigo, pid=proceso.pid)
        _anotar(tarea, elegida, tomada=True, fase="terminado", ok=codigo == 0, codigo=codigo,
                pid=proceso.pid)
        if al_terminar and registro:
            al_terminar(lanzados.estado(registro))

    hilo = threading.Thread(target=esperar, name=f"lanzar-{tarea['id']}", daemon=True)
    hilo.start()
    return hilo


# --- seguir y parar -----------------------------------------------------------------------------

def estado(tarea_id):
    """El estado de lo lanzado para esta tarea (`lanzados.estado`), o None si nunca se lanzó."""
    return lanzados.estado(lanzados.leer(tarea_id))


def detener(tarea_id, motivo=""):
    """Para el agente si sigue vivo y lo anota `detenido`. No toca la tarea ni su worktree:
    qué pasa con ellos lo decide quien llama. Devuelve el estado, o None si nunca se lanzó."""
    registro = lanzados.leer(tarea_id)
    if registro is None:
        return None
    if registro.get("fase") == lanzados.LANZADO:
        procesos.terminar(registro.get("pid"), registro.get("programa", ""))
        registro = lanzados.cambiar_fase(tarea_id, lanzados.DETENIDO, motivo=motivo,
                                         detenido_ts=int(time.time()))
    return lanzados.estado(registro)


__all__ = ["NoSePuede", "EsDeUnaPersona", "FaltaModelo", "SinHueco", "lanzar", "estado",
           "detener", "vigilar", "decidir", "hueco", "comando", "carpetas_de_escritura"]
