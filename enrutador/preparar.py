"""Preparar un proyecto nuevo en segundo plano (v1.3.0): la puerta que usa la pantalla
Preparando de CotejoBoard.

Con las respuestas de la entrevista, `lanzar` arma el prompt de inicio (`tareas/inicio.py`) y
lanza **el cliente que eligió la persona** sin interfaz (`claude -p`, `codex exec`,
`opencode run`, `gemini -p`), con la misma tabla y la misma config que el motor `headless`
(`clientes.py`, `motores.headless`). Es la única excepción a «nada en segundo plano» (la
decisión del inicio en la app): solo para preparar un proyecto y con el progreso a la vista.

Cómo se sigue, reutilizando lo de los despachos:

- **Anotado con pid en cuanto existe** (`tareas/preparacion.py`), con el argv del cliente y no
  el de systemd-run; «murió sin volver» se decide con `procesos.anotado_muerto`, la función de
  `revisar`.
- **Un hilo espera a que vuelva** (`vigilar`) y anota el código. Vive en el proceso que lo lanzó,
  que en el board es el de fondo (`--fondo`) y sigue con la ventana cerrada. Si ese proceso
  también muere, el estado se deduce del pid y de lo que haya en la carpeta.
- **Aviso por la barra** al lanzar y al terminar: se reescribe `estado.json`, que ahora lleva
  `preparaciones` y que el widget `cotejo.barra` vigila.
- **Colgado o fallido → reintentar o abrir en terminal.** `reintentar` para el proceso viejo y
  lanza otra vez el mismo comando; `abrir_en_terminal` lo para y abre el mismo prompt en una
  sesión que se ve, como el maestro (`motores/terminal.py`, `maestro.terminal` de la config).

**El entorno (`inicio.ENTORNO`, `COTEJO_FUENTE=repo`).** `init` registra la carpeta en la fuente
repo sin activarla, pero `crear` y `asignar` escriben en la fuente activa: con Obsidian activo,
el agente no encontraría el proyecto que acaba de crear. El agente corre con la fuente repo
fijada por entorno, así que esos verbos dan con él y la config de la persona no cambia.
"""

import shutil
import subprocess
import threading
from pathlib import Path

from tareas import inicio, preparacion
from . import clientes, config as cfg, procesos
from .motores import fondo, terminal


class NoSePuede(Exception):
    """Lo que impide lanzar, en llano, para enseñarlo tal cual en la pantalla."""


def _cliente(nombre):
    if not nombre:
        instalados = clientes.instalados()
        if not instalados:
            raise NoSePuede(clientes.aviso_sin_agentes())
        nombre = instalados[0]
    try:
        return clientes.de(nombre)
    except clientes.ClienteDesconocido as error:
        raise NoSePuede(str(error)) from error


def _propios(config, cliente):
    """`motores.headless` (Claude) o `motores.headless.clientes.<cliente>`, como el motor."""
    headless = (config.get("motores") or {}).get("headless") or {}
    return headless if cliente.nombre == "claude" else (
        (headless.get("clientes") or {}).get(cliente.nombre) or {})


def comando(config, cliente, modelo, prompt):
    """El argv sin interfaz, como lo arma el motor `headless` para ese cliente, más los
    `preparar.argumentos_extra.<cliente>` (el permiso de usar `cotejo`, en Claude)."""
    propios = _propios(config, cliente)
    extra = (list(propios.get("argumentos_extra") or ()) +
             list(((config.get("preparar") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ()))
    return cliente.argv_sin_interfaz(cliente.modelo_de(modelo, ""), prompt,
                                     comando=propios.get("comando"), extra=extra)


def _donde(carpeta):
    """Dónde arranca el agente: la carpeta si ya existe; si no, la primera de arriba que sí
    (`init` la crea)."""
    ruta = Path(carpeta)
    while not ruta.is_dir() and ruta.parent != ruta:
        ruta = ruta.parent
    return ruta


def avisar_a_la_barra(_estado=None):
    """Reescribe `estado.json`: el widget de la barra lo vigila y enseña `preparaciones`."""
    from tareas import estado
    try:
        estado.escribir(estado.calcular())
    except Exception:  # noqa: BLE001 - un aviso que falla no puede tumbar la preparación
        pass


def lanzar(respuestas, cliente=None, modelo=None, al_terminar=None, config=None):
    """Lanza la preparación y devuelve su estado (`preparacion.estado`). `al_terminar(estado)`
    se llama desde otro hilo cuando el agente vuelve; sin él, solo se avisa a la barra."""
    config = config if config is not None else cfg.cargar()
    try:
        r = inicio.validar(respuestas)
    except ValueError as error:
        raise NoSePuede(str(error)) from error
    elegido = _cliente(cliente)
    if modelo is None:
        modelo = ((config.get("maestro") or {}).get("modelos") or {}).get(elegido.nombre, "")
    prompt = inicio.armar(r)
    argv = comando(config, elegido, modelo, prompt)
    if shutil.which(argv[0]) is None:
        raise NoSePuede(f"No encontré «{argv[0]}» en esta máquina, y es el cliente que elegiste "
                        f"({elegido.titulo or elegido.nombre}). Instálalo o elige otro.")
    proyecto = inicio.nombre_del_proyecto(r.carpeta)
    ident = preparacion.nuevo_id(proyecto)
    registro = {"id": ident, "proyecto": proyecto, "carpeta": r.carpeta,
                "cliente": elegido.nombre, "modelo": modelo, "prompt": prompt,
                "comando": argv, "entorno": dict(inicio.ENTORNO), "intentos": 0,
                "log": str(preparacion.CARPETA / f"{ident}.log")}
    return _arrancar(registro, config, al_terminar)


def _arrancar(registro, config, al_terminar):
    ajustes = (config.get("motores") or {}).get("headless") or {}
    registro["intentos"] = int(registro.get("intentos") or 0) + 1
    try:
        proceso = fondo.lanzar(registro["comando"], _donde(registro["carpeta"]),
                               registro["log"], ajustes, registro.get("entorno"),
                               etiqueta="inicio-" + registro["id"])
    except OSError as error:
        raise NoSePuede(f"No pude lanzar «{registro['comando'][0]}»: {error}") from error
    preparacion.anotar_lanzado(registro, proceso.pid, registro["comando"][0])
    vigilar(proceso, registro["id"], ajustes.get("timeout_seg", 1800), al_terminar)
    avisar_a_la_barra()
    return preparacion.estado(registro)


def vigilar(proceso, ident, timeout, al_terminar=None):
    """Espera al proceso en un hilo y anota cómo volvió. Devuelve el hilo."""
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
        registro = preparacion.anotar_terminado(ident, codigo, pid=proceso.pid)
        avisar_a_la_barra()
        if al_terminar and registro:
            al_terminar(preparacion.estado(registro))

    hilo = threading.Thread(target=esperar, name=f"preparar-{ident}", daemon=True)
    hilo.start()
    return hilo


def _leer(ident):
    registro = preparacion.leer(ident)
    if registro is None:
        raise NoSePuede(f"No hay ninguna preparación «{ident}».")
    return registro


def _parar(registro):
    if registro.get("fase") == "lanzado":
        procesos.terminar(registro.get("pid"), registro.get("programa", ""))


def reintentar(ident, al_terminar=None, config=None):
    """Para el proceso si sigue vivo y lanza otra vez el mismo comando, con el mismo id."""
    registro = _leer(ident)
    _parar(registro)
    return _arrancar(registro, config if config is not None else cfg.cargar(), al_terminar)


def abrir_en_terminal(ident, config=None, simular=False):
    """El mismo prompt en una terminal que se ve, con el mismo cliente, modelo y entorno.

    Para el proceso de fondo antes de abrir: dos agentes preparando la misma carpeta se
    pisarían. Devuelve `{"comando", "directorio", "abierto"}`; `simular` no para ni abre nada.
    """
    config = config if config is not None else cfg.cargar()
    registro = _leer(ident)
    elegido = _cliente(registro.get("cliente"))
    argv = (list((config.get("maestro") or {}).get("terminal") or ()) +
            elegido.argv_interactivo(registro["prompt"],
                                     elegido.modelo_de(registro.get("modelo") or "", ""),
                                     comando=_propios(config, elegido).get("comando")))
    directorio = _donde(registro["carpeta"])
    salida = {"id": ident, "comando": argv, "directorio": str(directorio), "abierto": False}
    if simular:
        return salida
    _parar(registro)
    try:
        terminal.abrir(argv, directorio, registro.get("entorno"))
    except terminal.SinTerminal as error:
        raise NoSePuede(str(error)) from error
    preparacion.cambiar_fase(ident, preparacion.EN_TERMINAL)
    avisar_a_la_barra()
    return dict(salida, abierto=True)


def descartar(ident):
    """La persona ya lo vio: deja de salir en la barra y en la pantalla."""
    preparacion.marcar_visto(ident)
    avisar_a_la_barra()


def estados():
    """Todas las preparaciones con su estado, de la más nueva a la más vieja."""
    return preparacion.listar()


def estado(ident):
    return preparacion.estado(_leer(ident))


__all__ = ["NoSePuede", "lanzar", "reintentar", "abrir_en_terminal", "descartar", "estados",
           "estado", "comando", "vigilar"]
