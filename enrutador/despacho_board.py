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
   (`encargo.armar`), el mismo `cotejo` que el board en el PATH (`mismo_cotejo.py`) y
   **terminal libre en su worktree con los prohibidos de fábrica** (cotejo-7yfw1e, dec-kiik):
   puede correr pruebas y builds sin que nadie configure nada, y no puede subir privilegios,
   empujar a la fuerza, empujar a `main` o a la rama por defecto ni borrar fuera del worktree
   (`clientes.Cliente.terminal_libre`, y debajo las guardas del PATH de `guardas.py`). Si algo
   falla después de tomarla, se suelta con el motivo.

Toda decisión deja línea en la bitácora de despachos, también las negativas, con
`motor: "board"`: `revisar` las cuenta como las de `despachar`.

**Pausar y retomar** (cotejo-z7ma7r): devolver a mano una tarea de Haciendo a Pendiente la
pausa (`pausar`): su agente se para, y el worktree, la rama y el modelo asignado se quedan.
Volver a pasarla a Haciendo vuelve por `lanzar`, que reutiliza el worktree (`worktrees.crear`,
`reutilizado`) y lanza un agente **nuevo** con el encargo de siempre más la nota de retomar
(`tareas/retomar.py`): sin agentes viejos vivos ni resúmenes con IA. El registro guarda
`reanudacion` (qué vez, de quién, cuántos commits y cambios) y el detalle lo enseña.

**El fin y el rechazo** (cotejo-o253bs). Cuando el agente termina, su proceso se cierra solo y
`vigilar` le hace el fin (`fin`, una vez por lanzamiento): si entregó, la tarea ya está en Para
comprobar y su registro y su log se quedan; si terminó o murió **sin entregar**, vuelve a
Pendiente con su modelo y el motivo en llano —«el agente terminó sin entregar», con lo último
que dijo— y queda `detenido` con el worktree para retomarla. Los que se cerraron con el board
cerrado los recoge `recoger` al refrescar. Nada de eso relanza: lanzar es siempre de una
persona. Devolver de Para comprobar a Haciendo con motivo (`rechazar`) lanza uno nuevo en el
mismo worktree con el encargo, la nota de retomar y lo que pidieron cambiar.
"""

import socket
import subprocess
import threading
import time
from pathlib import Path

from tareas import bitacora as bitacora_cotejo, lanzados, retomar, worktrees
from tareas.cli import ErrorCLI
from . import (armado, bitacora, capacidad, clientes, config as cfg, cotejo as f, decision,
               despacho, encargo as enc, guardas, motor, niveles, procesos, reglas)
from .motores import fondo

MOTOR = "board"
# Los mismos escalones en que `despachar` se fía para gastar sin preguntar.
LO_DIJO_UNA_PERSONA = ("override", "asignacion")

NOTA = ("Te lanzó CotejoBoard sin nadie delante: nadie va a contestarte preguntas mientras "
        "trabajas. Si algo te impide seguir, no lo dejes a medias: bloquéala con el motivo. "
        + armado.NOTA_TERMINAL)
NOTA_SANDBOX = armado.NOTA_SANDBOX


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


def decidir(tarea, config, cliente=""):
    """La decisión del enrutador para esta tarea (sin override: lo que hay en la nota); la
    propuesta, con el agente del proyecto (`cliente`)."""
    humano, nivel = reglas.cargar(config.get("reglas_extra"), config.get("reglas_apagadas"))
    return decision.de_tarea(tarea, reglas_humano=humano, reglas_nivel=nivel,
                             niveles_extra=niveles.personalizados(config.get("modelos")),
                             alias_persona=config.get("alias_persona"), cliente=cliente)


def hueco(config):
    """Lo que dice `capacidad` ahora: `capacidad.calcular` sobre la máquina medida."""
    foto = capacidad.leer((c.ejecutable for c in clientes.CLIENTES.values()),
                          lanzados.pids_propios())
    return capacidad.calcular(foto, config.get("capacidad") or {})


def motivo_sin_hueco(calculo):
    """Por qué no cabe y qué hacer, para quien no programa."""
    limita = calculo.get("limita")
    por = {"memoria": "a la máquina le falta memoria libre para otro agente",
           "cpu": "el procesador ya va muy cargado",
           "maximo": (f"ya corren los {calculo.get('limites', {}).get('maximo')} agentes que "
                      f"permite tu configuración")}.get(limita, "la máquina no da para otro")
    return (f"No se lanzó: {por}. La tarea sigue en Pendiente, en espera. Cierra algo que no "
            f"uses (un navegador, otra sesión) o espera a que termine otro agente, y vuelve a "
            f"pasarla a Haciendo. Si quieres arriesgarte, pulsa «Lanzar de todos modos» en su "
            f"ficha: se lanza igual, bajo tu responsabilidad.")


def _cliente_de(elegida):
    try:
        return clientes.de(elegida.nivel.cliente)
    except clientes.ClienteDesconocido as error:
        raise NoSePuede(str(error)) from error


def comando(config, cliente, elegida, prompt, carpetas, ramas=None, politica_gemini=None,
            sandbox=None):
    """`armado.comando` con el modelo de la decisión del enrutador."""
    return armado.comando(config, cliente, elegida.nivel.modelo, elegida.nivel.modelo_id, prompt,
                          carpetas, ramas, politica_gemini, sandbox,
                          elegida.nivel.argumentos)


ramas_protegidas = armado.ramas_protegidas
carpetas_de_escritura = armado.carpetas_de_escritura


def sandbox_de(config, cliente, cotejo, tarea, trabajo, worktree=None, directorio=None):
    """`armado.sandbox_de` para la tarea (un dict con su `id`)."""
    return armado.sandbox_de(config, cliente, cotejo, tarea["id"], trabajo, worktree, directorio)


# --- lanzar -------------------------------------------------------------------------------------

def lanzar(tarea_id, al_terminar=None, config=None, forzar=False):
    """Lanza la tarea con su modelo asignado y devuelve su estado (`lanzados.estado`).

    Con `forzar` (el botón «Lanzar de todos modos») se salta la capacidad, solo esta vez y
    bajo responsabilidad de quien lo pide: lo demás (modelo asignado, carpeta, worktree) se
    comprueba igual.

    Levanta `EsDeUnaPersona`, `FaltaModelo`, `SinHueco` o `NoSePuede` sin haber tomado nada.
    `al_terminar(estado)` se llama desde otro hilo cuando el agente vuelve.
    """
    return _lanzar(tarea_id, al_terminar, config, rechazada=False, forzar=forzar)


def _lanzar(tarea_id, al_terminar, config, rechazada, rechazo_dado=None, forzar=False):
    """`lanzar`, y con `rechazada` el relanzamiento de `rechazar`: la tarea ya está en
    Haciendo a nombre de su modelo (se la devolvieron desde Para comprobar), así que no se
    toma otra vez, y el agente nuevo recibe además lo que le pidieron cambiar. `rechazo_dado` es
    ese rechazo cuando no hay registro de un lanzamiento anterior (la entregó otro camino, por
    ejemplo `despachar`) y por tanto no hay dónde leerlo."""
    config = config if config is not None else cfg.cargar()
    cotejo = f.Cotejo()
    try:
        tarea = cotejo.tarea(tarea_id)
    except ErrorCLI as error:
        raise NoSePuede(str(error)) from error
    # Lo que quedó del lanzamiento anterior, si lo hubo: de ahí sale la nota de retomar
    # (`tareas/retomar.py`), y se lee antes de que el nuevo lo pise.
    anterior = lanzados.leer(tarea["id"])
    try:
        elegida = decidir(tarea, config, cotejo.agente_del_proyecto(tarea.get("proyecto"),
                                                                    config))
    except ValueError as error:
        raise NoSePuede(str(error)) from error

    if not elegida.despachable:
        _rechazar(tarea, elegida, "veto", EsDeUnaPersona(
            f"Es una tarea para una persona ({elegida.razon}): no lancé ningún agente."))
    if elegida.por not in LO_DIJO_UNA_PERSONA:
        _rechazar(tarea, elegida, "falta_modelo", FaltaModelo(
            f"Nadie le ha asignado modelo. La propuesta es {elegida.nivel.modelo} "
            f"({elegida.razon}).", elegida.nivel.modelo, elegida.razon))
    esperado = "en-curso" if rechazada else "pendiente"
    if tarea.get("estado") != esperado:
        _rechazar(tarea, elegida, "no_pendiente", NoSePuede(
            f"La tarea no está {'en Haciendo' if rechazada else 'pendiente'}, está en "
            f"«{tarea.get('estado')}»."))

    calculo = None if forzar else hueco(config)
    if calculo and calculo.get("caben") == 0:
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

    # Lo que pidieron cambiar, si se la devolvieron desde Para comprobar y aún no volvió a
    # entregar (`retomar.rechazo_vigente`): va entero en la nota, así que el encargo no repite
    # el motivo ni la evidencia de la bitácora.
    rechazo = (retomar.rechazo_vigente(anterior, bitacora_cotejo.ultima_entrega(tarea["id"]))
               or rechazo_dado)

    def armar(tarea_ahora, worktree, nota=NOTA):
        trabajo = Path(worktree["ruta"]) if worktree else directorio
        if rechazo:
            tarea_ahora = {k: v for k, v in tarea_ahora.items()
                           if k not in ("motivo", "evidencia")}
        return motor.Encargo(
            prompt=enc.armar(tarea_ahora, elegida, directorio, nota, worktree),
            modelo=elegida.nivel.modelo, modelo_id=elegida.nivel.modelo_id,
            directorio=trabajo, tarea_id=tarea_ahora.get("id", ""), proyecto=proyecto,
            cliente=elegida.nivel.cliente, argumentos=elegida.nivel.argumentos)

    headless = motor.abrir("headless", config)
    for rechazo, problema in despacho.antes_de_tomar(headless, armar(tarea, plan_wt), plan_wt):
        _rechazar(tarea, elegida, rechazo, NoSePuede(problema))

    # Nunca dos agentes en la misma tarea: si el anterior sigue vivo (la tarea volvió a
    # Pendiente por otro camino), se para antes de lanzar el nuevo. No se resume ni se reusa.
    if anterior and anterior.get("fase") == lanzados.LANZADO:
        detener(tarea["id"], "se lanzó otro agente para retomarla")
        anterior = lanzados.leer(tarea["id"])

    # Tomarla: desde aquí, cualquier fallo la suelta antes de decir que no. Una rechazada ya
    # está en Haciendo a su nombre: lo que tenía en Pendiente es lo del lanzamiento anterior.
    id_antes, asignada = tarea["id"], tarea.get("agente", "")
    if rechazada:
        asignada = (anterior or {}).get("asignada") or asignada
    else:
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
    trabajo = Path(worktree["ruta"]) if worktree else directorio
    encerrado = sandbox_de(config, cliente, cotejo, tarea, trabajo, worktree, directorio)
    encargo = armar(tarea, worktree, NOTA + (" " + armado.nota_sandbox() if encerrado["activo"] else ""))
    trabajo = Path(encargo.directorio)
    prompt, reanudacion = encargo.prompt, None
    if retomar.es_retomable(anterior):
        # Pausada y vuelta a Haciendo: un agente nuevo con el encargo de siempre y, pegada al
        # final, la nota de retomar armada sola (commits, cambios sin commitear y lo último
        # que dijo el anterior). Se arma antes de lanzar: después, el log ya es del nuevo.
        previo = {**anterior, "id": tarea["id"],
                  "worktree": ({k: worktree.get(k) for k in ("ruta", "rama", "repo")}
                               if worktree else anterior.get("worktree"))}
        datos_nota = retomar.datos(previo)
        prompt = encargo.prompt + "\n\n" + retomar.armar(
            datos_nota, motivo=retomar.POR_RECHAZO if rechazada else retomar.motivo_de(anterior))
        if rechazo:
            prompt += "\n\n" + retomar.armar_rechazo(rechazo)
        reanudacion = {"vez": int(anterior.get("lanzamientos") or 1) + 1,
                       "anterior": anterior.get("modelo"),
                       "anterior_ts": anterior.get("ts"),
                       "commits": (len(datos_nota["commits"])
                                   if datos_nota["commits"] is not None else None),
                       "sin_commitear": (len(datos_nota["sin_commitear"])
                                         if datos_nota["sin_commitear"] is not None else None),
                       "rechazo": (rechazo or {}).get("motivo"),
                       "nota": prompt[len(encargo.prompt) + 2:]}
    elif rechazo:
        # Devuelta desde Para comprobar sin que el board la hubiera lanzado: no hay agente
        # anterior del que retomar, pero sí lo que pidieron cambiar y su entrega.
        prompt = encargo.prompt + "\n\n" + retomar.armar_rechazo(rechazo)
        reanudacion = {"vez": 2, "anterior": asignada or None, "commits": None,
                       "sin_commitear": None, "rechazo": rechazo.get("motivo"),
                       "nota": prompt[len(encargo.prompt) + 2:]}
    ramas = ramas_protegidas(directorio, worktree)
    argv = comando(config, cliente, elegida, prompt,
                   carpetas_de_escritura(trabajo, worktree), ramas, guardas.politica_gemini(),
                   sandbox=encerrado["ajustes"])
    log = lanzados.ruta_log(tarea["id"])
    registro = {"id": tarea["id"], "proyecto": proyecto, "texto": tarea.get("texto", ""),
                "cliente": cliente.nombre, "modelo": elegida.nivel.modelo,
                "modelo_id": elegida.nivel.modelo_id, "asignada": asignada,
                "directorio": str(directorio), "trabajo": str(trabajo),
                "worktree": ({k: worktree.get(k) for k in ("ruta", "rama", "repo")}
                             if worktree else None),
                "comando": argv, "prompt": prompt, "encargo": encargo.prompt,
                "log": str(log), "log_desde": _tamano(log),
                # La base de la rama se guarda la primera vez y se arrastra: es desde donde
                # cuenta los commits la nota de retomar.
                "base": ((anterior or {}).get("base")
                         or (worktree or {}).get("desde") or None),
                "reanudacion": reanudacion, "rechazo": rechazo,
                # Si su Bash va encerrado y, si no, por qué (cotejo-amui0f). El token no se
                # guarda: va solo en el entorno del agente.
                "sandbox": {"activo": encerrado["activo"], "motivo": encerrado["motivo"],
                            "avisos": encerrado["avisos"]},
                "lanzamientos": int((anterior or {}).get("lanzamientos") or 0) + 1}
    try:
        # El lanzador de `cotejo` primero y las guardas detrás, antes que lo del sistema.
        entorno = armado.entorno(cliente, carpetas_de_escritura(trabajo, worktree), ramas,
                                 encerrado)
        ajustes = (config.get("motores") or {}).get("headless") or {}
        proceso = fondo.lanzar(argv, trabajo, str(log), ajustes, entorno,
                               etiqueta="tarea-" + worktrees.seguro(tarea["id"]))
    except OSError as error:
        soltar(f"No pude lanzar «{argv[0]}»: {error}.", "motor")
    lanzados.anotar_lanzado(registro, proceso.pid, argv[0])
    if id_antes != tarea["id"]:
        lanzados.borrar(id_antes)   # tomarla le dio su id definitivo: el «en espera» era del otro
    _anotar(tarea, elegida, tomada=True, fase="lanzado", comando=argv, pid=proceso.pid,
            programa=argv[0], host=socket.gethostname(), sandbox=encerrado["activo"],
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


# Los pids que espera un hilo de este proceso: `recoger` no se los adelanta.
_VIGILADOS = set()


def vigilar(proceso, tarea, elegida, timeout, al_terminar=None):
    """Espera al proceso en un hilo, anota cómo volvió (registro y bitácora de despachos), le
    hace el fin (`fin`: entregó, o vuelve a Pendiente) y llama `al_terminar(estado)`. Devuelve
    el hilo."""
    _VIGILADOS.add(proceso.pid)

    def esperar():
        try:
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
            _anotar(tarea, elegida, tomada=True, fase="terminado", ok=codigo == 0,
                    codigo=codigo, pid=proceso.pid)
            if registro and registro.get("fase") == lanzados.TERMINADO:
                registro = fin(tarea["id"], proceso.pid) or registro
        finally:
            _VIGILADOS.discard(proceso.pid)
        if al_terminar and registro:
            al_terminar(lanzados.estado(registro))

    hilo = threading.Thread(target=esperar, name=f"lanzar-{tarea['id']}", daemon=True)
    hilo.start()
    return hilo


# --- el fin (cotejo-o253bs) ---------------------------------------------------------------------

SIN_ENTREGAR = "el agente terminó sin entregar"


def motivo_sin_entregar(registro):
    """Por qué volvió a Pendiente, para quien no programa, con lo último que dijo."""
    codigo = registro.get("codigo")
    por = (" (su proceso se cerró sin que nadie lo viera terminar)" if registro.get("murio")
           else " (se le acabó el tiempo)" if codigo == 124
           else f" (salió con un error, código {codigo})" if codigo not in (0, None) else "")
    texto = "El agente terminó sin entregar" + por + "."
    ultimas = retomar.ultimas_lineas(registro, 3)
    if ultimas:
        texto += " Lo último que dijo: " + " / ".join(f"«{l}»" for l in ultimas) + "."
    return texto + (" Su worktree se queda: pásala a Haciendo y otro agente la retoma donde "
                    "quedó.")


def fin(tarea_id, pid):
    """Lo que pasa cuando el agente de `pid` termina, una sola vez por lanzamiento
    (`lanzados.reclamar_fin`). Si entregó, la tarea ya está en Para comprobar y el registro y
    su log se quedan (son sus mensajes). Si sigue en Haciendo a su nombre, terminó **sin
    entregar**: vuelve a Pendiente con su modelo y el motivo en llano (`cotejo.soltar`), y queda
    `detenido` con el worktree, para retomarla. Si la bloqueó o la movió alguien, no se toca.
    Nunca lanza nada. Devuelve el registro, o None si otro ya le hizo el fin."""
    if not lanzados.reclamar_fin(tarea_id, pid):
        return None
    ahora = int(time.time())
    registro = lanzados.leer(tarea_id) or {}
    como = lanzados.FIN_OTRO
    # Devuelta desde Para comprobar mientras volvía: eso lo lleva `rechazar`, no el fin.
    rechazada = (registro.get("rechazo") or {}).get("de_pid") == pid
    if registro.get("fase") == lanzados.TERMINADO and not rechazada:
        cotejo = f.Cotejo()
        try:
            tarea = cotejo.tarea(tarea_id)
        except ErrorCLI:
            tarea = {}
        if tarea.get("estado") == "por-validar":
            como = lanzados.FIN_ENTREGO
        elif tarea.get("estado") == "en-curso" and tarea.get("agente") == registro.get("modelo"):
            motivo = motivo_sin_entregar(registro)
            try:
                soltada = cotejo.soltar(tarea_id, motivo, agente=registro.get("modelo"),
                                        asignada=registro.get("asignada")
                                        or registro.get("modelo") or "")
            except ErrorCLI:
                soltada = False
            if soltada:
                return lanzados.cambiar_fase(
                    tarea_id, lanzados.DETENIDO, motivo=SIN_ENTREGAR, detenido_ts=ahora,
                    fin={"como": lanzados.FIN_SIN_ENTREGAR, "ts": ahora, "motivo": motivo})
    return lanzados.actualizar(tarea_id, fin={"como": como, "ts": ahora})


def recoger():
    """Los fines que nadie hizo: agentes que se cerraron con el board cerrado (`murio`) o que
    volvieron sin que llegara su fin. Los que espera un hilo de este proceso no se tocan.
    Lo llama el board al refrescar; nunca lanza nada. Devuelve los ids que recogió."""
    recogidos = []
    for tarea_id, registro in lanzados.todos().items():
        pid = registro.get("pid")
        if not pid or pid in _VIGILADOS or registro.get("fin"):
            continue
        if registro.get("fase") == lanzados.LANZADO:
            if not procesos.anotado_muerto(registro):
                continue
            registro = lanzados.anotar_terminado(tarea_id, None, pid=pid, murio=True)
        if (registro or {}).get("fase") == lanzados.TERMINADO and fin(tarea_id, pid):
            recogidos.append(tarea_id)
    return recogidos


# --- el rechazo (cotejo-o253bs) -----------------------------------------------------------------

RECHAZO = "lo devolvieron desde Para comprobar para lanzar otro"


def rechazar(tarea_id, motivo, mover, al_terminar=None, config=None):
    """Para comprobar → Haciendo con motivo, de una tarea asignada a un agente: un agente
    **nuevo** en el mismo worktree con el encargo, la nota de retomar y «Lo que te pidieron
    cambiar» (el motivo y la entrega anterior, `retomar.armar_rechazo`).

    El orden importa: se para el agente anterior si sigue vivo y se guarda el rechazo en el
    registro **antes** de que `mover()` (lo que escribe el board: la línea y el «rechazar» de
    la bitácora) la pase a Haciendo; así su fin no la toma por una que terminó sin entregar.
    Si después no se puede lanzar (sin hueco, sin cliente…), vuelve a Pendiente con su modelo y
    el rechazo guardado, y levanta el `NoSePuede`: al pasarla otra vez a Haciendo, el agente
    nuevo lo recibe. Si la lanzó otro camino (`despachar`, un agente a mano) y está asignada a
    un agente, también se lanza: en la carpeta del proyecto o en su worktree si lo tiene, con
    «Lo que te pidieron cambiar» pero sin nota de retomar (no hay registro del anterior).
    Devuelve el estado, o None si es de una persona o no tiene agente (y `mover` no se
    llamó: se mueve como siempre)."""
    anterior = lanzados.leer(tarea_id)
    propia = retomar.es_retomable(anterior)
    if not propia:
        # No la lanzó el board (la entregó `despachar`, o un agente a mano): si está asignada
        # a un agente, devolverla también lanza el suyo; si es de una persona, se mueve como
        # siempre (cotejo-2sxw7p).
        modelo = _agente_asignado(tarea_id, config)
        if not modelo:
            return None
        anterior = None
    else:
        modelo = anterior.get("modelo")
    if not (motivo or "").strip():
        raise NoSePuede("Para devolverla hace falta un motivo.")
    dado = {**retomar.rechazo(motivo, bitacora_cotejo.ultima_entrega(tarea_id)),
            "de_pid": (anterior or {}).get("pid")}
    if propia:
        if anterior.get("fase") == lanzados.LANZADO:
            detener(tarea_id, RECHAZO)
        lanzados.actualizar(tarea_id, rechazo=dado)
    if not mover():
        raise NoSePuede("No pude pasarla a Haciendo: cambió mientras tanto.")
    try:
        return _lanzar(tarea_id, al_terminar, config, rechazada=True, rechazo_dado=dado)
    except NoSePuede as error:
        asignada = (anterior or {}).get("asignada") or modelo or ""
        try:
            f.Cotejo().soltar(tarea_id, f"No se pudo lanzar otro agente: {error} Lo que pediste "
                              f"cambiar queda guardado para el siguiente.", agente=modelo,
                              asignada=asignada)
        except ErrorCLI:
            pass
        # Sin lanzamiento anterior el registro puede ser solo el de «en espera»: el rechazo se
        # guarda ahí para que el siguiente agente lo reciba.
        lanzados.actualizar(tarea_id, rechazo=dado)
        registro = lanzados.leer(tarea_id) or {}
        if registro and registro.get("fase") not in (lanzados.EN_ESPERA, lanzados.DETENIDO):
            lanzados.cambiar_fase(tarea_id, lanzados.DETENIDO, motivo=RECHAZO,
                                  detenido_ts=int(time.time()))
        dicho = (f"{error} La devolví a Pendiente con lo que pediste cambiar: pásala a "
                 f"Haciendo cuando se pueda.")
        raise (SinHueco(dicho) if isinstance(error, SinHueco) else NoSePuede(dicho)) from error


def _agente_asignado(tarea_id, config=None):
    """El modelo al que está asignada la tarea, o "" si no tiene o es de una persona."""
    config = config if config is not None else cfg.cargar()
    try:
        agente = (f.Cotejo().tarea(tarea_id).get("agente") or "").strip()
    except ErrorCLI:
        return ""
    alias = tuple(config.get("alias_persona") or ("persona",))
    return "" if not agente or agente in alias else agente


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


PAUSA = "lo devolvieron a Pendiente desde el board"


def pausar(tarea_id, motivo=PAUSA):
    """Pausar desde el board (cotejo-z7ma7r): para su agente, si sigue vivo, y lo anota
    `detenido` con el motivo. El worktree, la rama y el modelo asignado se quedan, para que
    volver a pasarla a Haciendo lance uno nuevo que retome (`lanzar`, con la nota de
    `tareas/retomar.py`). Devuelve el estado, o None si el board nunca la lanzó."""
    registro = lanzados.leer(tarea_id)
    if registro is None:
        return None
    if registro.get("fase") == lanzados.LANZADO:
        return detener(tarea_id, motivo)
    if registro.get("fase") == lanzados.TERMINADO:
        # Terminó sin entregar y se devuelve a mano: también queda pausada para retomarla.
        registro = lanzados.cambiar_fase(tarea_id, lanzados.DETENIDO, motivo=motivo,
                                         detenido_ts=int(time.time()))
    return lanzados.estado(registro)


__all__ = ["NoSePuede", "pausar", "fin", "recoger", "rechazar", "motivo_sin_entregar", "EsDeUnaPersona", "FaltaModelo", "SinHueco", "lanzar", "estado",
           "detener", "vigilar", "decidir", "hueco", "comando", "carpetas_de_escritura",
           "ramas_protegidas"]
