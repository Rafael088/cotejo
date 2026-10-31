"""Hablar con el maestro de un proyecto: la parte de `verbos.hablar_maestro` que no necesita
`verbos` (que está congelado en su tope de líneas, `test_tamano_de_modulos`).

`armar` reúne lo de un turno —el proyecto, sus pendientes asignadas, la carpeta del código, la
instrucción con la conversación y el comando del cliente— sin lanzar nada; `hablar` lo lanza por
`conversacion.empezar`. Lo usan igual la CLI (`cotejo maestro`, que espera la respuesta) y
CotejoBoard (que la sigue en vivo). Nunca se abre una terminal (cotejo-9ybn1a).
"""

import shutil
from pathlib import Path

from tareas import ramas_pendientes
from tareas.cli import ESQUEMA, ErrorCLI
from . import clientes, config as cfg, conversacion, decision, maestro

# Mismo valor que `verbos.LO_DIJO_UNA_PERSONA`: una persona lo dijo (override o asignación).
LO_DIJO_UNA_PERSONA = ("override", "asignacion")


def asignadas(config, humano, nivel, propios, pendientes):
    """Las pendientes que una persona asignó a un modelo que se puede despachar: lo único que
    el maestro puede proponer repartir."""
    filas = []
    for tarea in pendientes:
        elegida = decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                                    niveles_extra=propios,
                                    alias_persona=config.get("alias_persona"))
        if elegida.por in LO_DIJO_UNA_PERSONA and elegida.despachable:
            filas.append({"id": tarea.get("id"), "texto": tarea.get("texto"),
                          "modelo": elegida.nivel.modelo, "cliente": elegida.nivel.cliente})
    return filas


def carpeta_de_tareas(cotejo, directorio, pendientes):
    """Dónde escribe `cotejo crear` para este proyecto: el `.cotejo/` de su repo o la carpeta
    de su nota (la de cualquiera de sus tareas). None si no se sabe (una fuente externa)."""
    if directorio and (Path(directorio) / ".cotejo").is_dir():
        return Path(directorio) / ".cotejo"
    for tarea in pendientes:
        carpeta = cotejo.carpeta_de_la_tarea(tarea.get("id"))
        if carpeta:
            return carpeta
    return None


def _cliente(cliente):
    if cliente:
        try:
            return clientes.de(cliente)
        except clientes.ClienteDesconocido as error:
            raise ErrorCLI(str(error), "Mira cuáles hay con `cotejo maestro --clientes`.") \
                from error
    # Sin cliente pedido, el primero que haya en la máquina. Si no hay ninguno no se inventa
    # uno (ni `claude`): sin agente no hay maestro, ni siquiera para simularlo.
    if not clientes.instalados():
        raise ErrorCLI(clientes.SIN_AGENTE, clientes.SIN_AGENTE_SALIDA)
    return clientes.de(clientes.instalados()[0])


def _nombre(cotejo, proyecto):
    try:
        return maestro.resolver_proyecto(proyecto, cotejo.proyectos())
    except maestro.SinProyecto as error:
        raise ErrorCLI(str(error), "Mira los proyectos con `cotejo estado`.") from error


def armar(config, cotejo, humano, nivel, propios, proyecto, cliente, modelo, pedido):
    """Todo lo de un turno, sin lanzar nada."""
    elegido = _cliente(cliente)
    nombre = _nombre(cotejo, proyecto)
    if modelo is None:
        modelo = ((config.get("maestro") or {}).get("modelos") or {}).get(elegido.nombre, "")
    pendientes = [t for t in cotejo.tareas(nombre, "pendiente") if t.get("proyecto") == nombre]
    filas = asignadas(config, humano, nivel, propios, pendientes)
    directorio = cfg.directorio_de(config, nombre) or cotejo.carpeta_de(nombre)
    directorio = str(directorio) if directorio else None
    todas = list(pendientes)
    for estado in ("en-curso", "por-validar", "hecha"):
        todas.extend(t for t in cotejo.tareas(nombre, estado) if t.get("proyecto") == nombre)
    ramas = ramas_pendientes.detectar(directorio, todas)
    escritura = conversacion.carpetas_de_escritura(
        carpeta_de_tareas(cotejo, directorio, pendientes))
    pedido = " ".join((pedido or "").split())
    prompt = maestro.instruccion(nombre, filas, directorio, pedido,
                                 conversacion.leer(nombre)["turnos"], ramas)
    try:
        argv, env, trabajo = conversacion.comando(config, elegido, modelo, prompt, directorio,
                                                  escritura)
    except conversacion.NoSePuede as error:
        raise ErrorCLI(str(error), "Elige otro agente para el maestro.") from error
    return {"esquema": ESQUEMA, "proyecto": nombre, "cliente": elegido.nombre,
            "titulo": elegido.titulo or elegido.nombre, "modelo": modelo,
            "directorio": directorio, "asignadas": filas, "ramas_pendientes": ramas,
            "pedido": pedido, "prompt": prompt,
            "argv": argv, "env": env, "trabajo": str(trabajo) if trabajo else None,
            "escritura": escritura}


def hablar(preparado, proyecto, pedido, cliente=None, modelo=None, simular=False,
           al_terminar=None, esperar=False, olvidar=False):
    """Un turno de la conversación. Con `simular`, solo lo que se lanzaría. Con `esperar` (la
    CLI), espera la respuesta y la devuelve en `respuesta`; sin él (el board), vuelve al
    lanzarlo y `al_terminar(turno)` llega desde otro hilo."""
    config = preparado[0]
    if olvidar and not simular:
        conversacion.olvidar(_nombre(preparado[1], proyecto))
    hecho = armar(*preparado, proyecto, cliente, modelo, pedido)
    salida = {k: hecho[k] for k in ("esquema", "proyecto", "cliente", "titulo", "modelo",
                                    "directorio", "asignadas", "ramas_pendientes", "pedido")}
    salida["comando"] = hecho["argv"]
    if simular:
        return dict(salida, prompt=hecho["prompt"], escritura=hecho["escritura"],
                    lanzado=False)
    if shutil.which(hecho["argv"][0]) is None:
        raise ErrorCLI(f"«{hecho['cliente']}» no está instalado en esta máquina",
                       f"Los que sí: {', '.join(clientes.instalados()) or 'ninguno'}.")
    headless = (config.get("motores") or {}).get("headless") or {}
    try:
        hilo = conversacion.empezar(
            hecho["proyecto"], hecho["pedido"], hecho, al_terminar, ajustes=headless,
            timeout=(config.get("maestro") or {}).get("timeout_seg") or conversacion.TIMEOUT_SEG)
    except conversacion.NoSePuede as error:
        raise ErrorCLI(str(error), "Mira la conversación en el board.") from error
    salida["lanzado"] = True
    if esperar:
        hilo.join()
        turno = conversacion.leer(hecho["proyecto"])["turnos"][-1]
        salida.update(respuesta=turno.get("texto", ""), ok=bool(turno.get("ok")),
                      repartir=turno.get("repartir") or [])
    return salida
