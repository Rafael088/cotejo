"""La conversación con el maestro: cada mensaje de la persona es un turno de un cliente sin
interfaz que solo puede correr `cotejo` (v1.3.0, cotejo-9ybn1a).

Lo que se dice el maestro (`maestro.instruccion`) lleva la conversación entera, recortada: no
todos los clientes tienen una forma documentada de retomar su sesión sin interfaz, y así vale
igual para Claude Code, Codex, OpenCode, Gemini CLI y Antigravity CLI. La conversación de cada
proyecto vive en `<estado>/maestro/<proyecto>.json` (fuera del vault, como `board.json`); la
salida de cada turno, al lado (`.out` y `.err`), y de ahí la lee el board mientras contesta.

**Lo que puede hacer el cliente** (`comando`): leer, y correr `cotejo`. Nada de editar
archivos. Cada uno con lo suyo y con lo que ya hay para los demás lanzamientos:

- **Claude Code**: `--allowedTools Bash(cotejo:*)` (lo demás que pida permiso, sin nadie
  delante, se niega), `Edit`/`Write`/`NotebookEdit` en `--disallowedTools` y sin los ajustes del
  proyecto (`SOLO_AJUSTES_DE_LA_PERSONA`). `stream-json` para ver en el board qué hace.
- **Codex**: su sandbox `workspace-write` con la carpeta donde se escriben las tareas como
  directorio de trabajo y la de estado (`--add-dir`), sin confianza en el proyecto. Lo demás,
  incluido el código, en solo lectura. Codex escribe el progreso en stderr y solo el mensaje
  final en stdout (https://learn.chatgpt.com/docs/non-interactive-mode): stdout es la respuesta.
- **OpenCode**: `permission.edit: deny`, `permission.bash` todo `deny` salvo `cotejo`
  (https://opencode.ai/docs/permissions/, gana la última regla que casa) y sin los servidores MCP
  ni los plugins del proyecto.
- **Gemini CLI**: `--allowed-tools run_shell_command(cotejo)`, como al preparar, y sin lo que su
  `.gemini/settings.json` del proyecto le haría arrancar.
- **Antigravity CLI**: no tiene cómo permitir un solo comando en la invocación; va con
  `--dangerously-skip-permissions` dentro de la jaula de bubblewrap de Cotejo, que solo deja
  escribir donde se escriben las tareas y en la de estado. Sin bwrap no se lanza.

Lo lanza `motores/fondo.py` (`lanzar_aparte`), como todo lo que corre sin interfaz. Para todos, la config de Cotejo vedada (`COTEJO_CONFIG_VEDADA`) y el mismo `cotejo` que el board
primero en el PATH (`mismo_cotejo`). Aquí no hay GTK: la CLI (`cotejo maestro`) y el board lo usan
igual.
"""

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from tareas import lanzados, rutas
from . import clientes, maestro, mismo_cotejo, procesos, sandbox
from .motores import fondo

TIMEOUT_SEG = 600
QUIEN_PERSONA, QUIEN_MAESTRO = "persona", "maestro"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_hilos = {}   # proyecto → hilo que espera su turno en este proceso


class NoSePuede(Exception):
    """Lo que impide hablar con el maestro, en llano, para enseñarlo tal cual."""


# --- dónde vive cada conversación ---------------------------------------------------------------

def carpeta():
    return Path(rutas.estado()) / "maestro"


def _nombre(proyecto):
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "-", proyecto or "proyecto").strip("-.") or "proyecto"
    return limpio[:80]


def _ruta(proyecto):
    return carpeta() / f"{_nombre(proyecto)}.json"


def _crudo(proyecto):
    try:
        datos = json.loads(_ruta(proyecto).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict) or not isinstance(datos.get("turnos"), list):
        datos = {"turnos": []}
    datos["proyecto"] = proyecto
    return datos


def _guardar(datos):
    ruta = _ruta(datos["proyecto"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporal, ruta)


_cerrojo = threading.Lock()


def leer(proyecto):
    """La conversación de un proyecto: `{"proyecto", "turnos": [...], "en_curso"?}`.

    Un turno que se quedó a medias con su proceso muerto (se apagó la máquina, se cerró el
    proceso del board) se cierra aquí con un aviso, para que no se vea «pensando» para siempre.
    """
    with _cerrojo:
        datos = _crudo(proyecto)
        curso = datos.get("en_curso")
        if (curso and proyecto not in _hilos
                and not procesos.vivo(curso.get("pid"), curso.get("programa", ""))):
            _cerrar(datos, _respuesta_de(curso))
    return datos


def olvidar(proyecto):
    """Empezar de nuevo: borra la conversación (y para el turno que esté en marcha)."""
    parar(proyecto, anotar=False)
    with _cerrojo:
        datos = _crudo(proyecto)
        for turno in datos["turnos"] + [datos.get("en_curso") or {}]:
            for clave in ("out", "err"):
                if turno.get(clave):
                    Path(turno[clave]).unlink(missing_ok=True)
        _ruta(proyecto).unlink(missing_ok=True)


def contestando(proyecto):
    """¿Hay un turno en marcha para este proyecto?"""
    return bool(leer(proyecto).get("en_curso"))


# --- qué puede hacer el cliente ----------------------------------------------------------------

def _permisos_opencode(previo):
    try:
        datos = json.loads(previo) if previo else {}
    except ValueError:
        datos = {}
    datos = datos if isinstance(datos, dict) else {}
    permiso = datos.get("permission")
    permiso = dict(permiso) if isinstance(permiso, dict) else {}
    permiso.update(edit="deny", webfetch="deny",
                   bash={"*": "deny", "cotejo": "allow", "cotejo *": "allow"})
    datos["permission"] = permiso
    return json.dumps(datos, ensure_ascii=False)


def comando(config, cliente, modelo, prompt, directorio, escritura):
    """`(argv, variables, carpeta donde arranca)` de un turno del maestro con `cliente`.

    `directorio` es la carpeta del código (o None); `escritura`, las carpetas donde `cotejo`
    tiene que poder escribir (`carpetas_de_escritura`). Lo que pone la persona en
    `enrutador.maestro.argumentos_extra.<cliente>` solo añade; los permisos de aquí van siempre.
    """
    from . import preparar
    propios = preparar._propios(config, cliente)
    extra = list(propios.get("argumentos_extra") or ())
    extra += list(((config.get("maestro") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ())
    trabajo = directorio or (escritura[0] if escritura else None)
    env = {}
    if cliente.nombre == "claude":
        extra += ["--output-format", "stream-json", "--verbose",
                  *clientes.SOLO_AJUSTES_DE_LA_PERSONA, "--allowedTools", "Bash(cotejo:*)",
                  "--disallowedTools", "Edit", "Write", "NotebookEdit"]
    elif cliente.nombre == "codex":
        # El directorio de trabajo es lo único que `workspace-write` deja escribir además de
        # `--add-dir`: la carpeta de las tareas, no la del código.
        trabajo = escritura[0] if escritura else trabajo
        extra += cliente.permisos(escritura[1:])[0] + clientes._codex_sin_confianza(trabajo)
    elif cliente.nombre == "opencode":
        env = {"OPENCODE_CONFIG_CONTENT": _permisos_opencode(
            os.environ.get("OPENCODE_CONFIG_CONTENT"))}
        env = clientes._opencode_sin_plugins_del_proyecto(
            trabajo, clientes._opencode_sin_mcp_del_proyecto(trabajo, env))
    elif cliente.nombre == "gemini":
        extra, env = clientes._gemini_sin_lo_del_proyecto(
            trabajo, extra + ["--allowed-tools", "run_shell_command(cotejo)"],
            {"GEMINI_CLI_TRUST_WORKSPACE": "true"})
    elif cliente.nombre == "antigravity":
        extra += cliente.permisos(escritura)[0] + ["--dangerously-skip-permissions"]
    argv = cliente.argv_sin_interfaz(cliente.modelo_de(modelo or "", ""), prompt,
                                     comando=propios.get("comando"), extra=extra)
    if cliente.nombre == "antigravity":
        hay, motivo = sandbox.disponible_bwrap()
        if not hay:
            raise NoSePuede(f"Antigravity CLI no habla sin la jaula de Cotejo: {motivo}.")
        from tareas import configuracion
        ajustes = sandbox.del_lanzamiento(escritura, vedadas=configuracion.archivos(),
                                          token=None)["ajustes"]
        argv = sandbox.envolver_antigravity(argv, ajustes, trabajo)
    return argv, env, trabajo


def carpetas_de_escritura(carpeta_tareas):
    """Donde escribe `cotejo crear` (la carpeta del archivo de tareas del proyecto) y la de
    estado (bitácora, ahorro, esta conversación). Ninguna más: ni el código ni la config."""
    lista = [c for c in (carpeta_tareas, rutas.estado()) if c]
    return [os.path.abspath(str(c)) for c in dict.fromkeys(str(c) for c in lista)]


# --- un turno ----------------------------------------------------------------------------------

def _texto(ruta):
    try:
        return Path(ruta).read_text(encoding="utf-8", errors="replace")
    except (OSError, TypeError):
        return ""


def _respuesta_claude(salida):
    """De `stream-json`: el `result` final, o lo que escribió si se cortó antes."""
    final, escrito = None, []
    for linea in salida.splitlines():
        try:
            datos = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(datos, dict):
            continue
        if datos.get("type") == "result":
            final = (str(datos.get("result") or ""), bool(datos.get("is_error")))
        elif datos.get("type") == "assistant":
            for parte in (datos.get("message") or {}).get("content") or ():
                if isinstance(parte, dict) and parte.get("type") == "text":
                    escrito.append(str(parte.get("text") or ""))
    if final is not None:
        return final
    return "\n".join(escrito), True


def _respuesta_de(curso, codigo=None):
    """`(texto, ok)` de un turno a partir de lo que dejó en `.out` y `.err`."""
    salida = _ANSI.sub("", _texto(curso.get("out")))
    if curso.get("cliente") == "claude":
        texto, error = _respuesta_claude(salida)
    else:
        texto, error = salida.strip(), False
    texto = texto.strip()
    ok = bool(texto) and not error and codigo in (0, None)
    if codigo is None and not texto:
        return "El maestro se cortó antes de contestar. Vuelve a escribirle.", False
    if not texto:
        errores = [l for l in _ANSI.sub("", _texto(curso.get("err"))).splitlines() if l.strip()]
        cola = " ".join(errores[-3:])[:400]
        texto = ("El maestro no contestó" + (f" (código {codigo})" if codigo else "") + "."
                 + (f" Dijo: {cola}" if cola else ""))
    return texto, ok


def _cerrar(datos, respuesta, repartir=()):
    curso = datos.pop("en_curso", None) or {}
    texto, ok = respuesta
    turno = {"quien": QUIEN_MAESTRO, "texto": maestro.sin_marca(texto) or texto, "ok": ok,
             "ts": time.time(), "cliente": curso.get("cliente"),
             "out": curso.get("out"), "err": curso.get("err")}
    if repartir:
        turno["repartir"] = list(repartir)
    datos["turnos"].append(turno)
    _guardar(datos)
    return turno


def empezar(proyecto, pedido, armado, al_terminar=None, timeout=TIMEOUT_SEG, ajustes=None):
    """Lanza un turno y devuelve el hilo que lo espera. `armado` es lo que dejó listo
    `apertura.armar` (`argv`, `env`, `trabajo`, `cliente`, `asignadas`). `al_terminar(turno)` se
    llama desde ese hilo con el turno del maestro ya guardado."""
    with _cerrojo:
        datos = _crudo(proyecto)
        curso = datos.get("en_curso")
        if curso and procesos.vivo(curso.get("pid"), curso.get("programa", "")):
            raise NoSePuede("El maestro todavía está contestando lo anterior: espera a que "
                            "termine o páralo.")
        datos.pop("en_curso", None)
        n = len(datos["turnos"])
        base = carpeta() / f"{_nombre(proyecto)}-{n + 1}-{int(time.time())}"
        base.parent.mkdir(parents=True, exist_ok=True)
        curso = {"cliente": armado["cliente"], "out": str(base) + ".out",
                 "err": str(base) + ".err", "desde": time.time(),
                 "asignadas": armado["asignadas"]}
        try:
            entorno = mismo_cotejo.entorno({"COTEJO_CONFIG_VEDADA": "1", **armado["env"]})
        except OSError as error:
            raise NoSePuede(f"No pude preparar el Cotejo que usará el maestro: {error}") from error
        try:
            proceso = fondo.lanzar_aparte(armado["argv"], armado.get("trabajo"), curso["out"],
                                          curso["err"], ajustes, entorno,
                                          etiqueta="maestro-" + _nombre(proyecto))
        except OSError as error:
            raise NoSePuede(f"No pude lanzar «{armado['argv'][0]}»: {error}") from error
        curso.update(pid=proceso.pid, programa=os.path.basename(armado["argv"][0]))
        datos["turnos"].append({"quien": QUIEN_PERSONA, "texto": pedido, "ts": time.time()})
        datos["en_curso"] = curso
        _guardar(datos)

    def esperar():
        try:
            codigo = proceso.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            procesos.terminar(proceso.pid)
            try:
                codigo = proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
                codigo = proceso.wait()
            codigo = 124
        with _cerrojo:
            datos = _crudo(proyecto)
            actual = datos.get("en_curso") or {}
            if actual.get("pid") != proceso.pid:
                turno = None          # lo paró o lo borró la persona: ya está anotado
            else:
                respuesta = _respuesta_de(actual, codigo)
                if codigo == 124:
                    respuesta = ("Tardé demasiado y me paré. Pídemelo por partes.", False)
                turno = _cerrar(datos, respuesta,
                                maestro.pedidas(respuesta[0], actual.get("asignadas") or ()))
            _hilos.pop(proyecto, None)
        if al_terminar and turno is not None:
            al_terminar(turno)

    hilo = threading.Thread(target=esperar, name=f"maestro-{_nombre(proyecto)}", daemon=True)
    _hilos[proyecto] = hilo
    hilo.start()
    return hilo


def parar(proyecto, anotar=True):
    """Para el turno en marcha. Con `anotar`, queda en la conversación que se paró."""
    with _cerrojo:
        datos = _crudo(proyecto)
        curso = datos.get("en_curso")
        if not curso:
            return False
        procesos.terminar(curso.get("pid"), curso.get("programa", ""))
        if anotar:
            _cerrar(datos, ("Lo paraste antes de que contestara.", False))
        else:
            datos.pop("en_curso", None)
            _guardar(datos)
    return True


def en_vivo(proyecto, limite=8):
    """Lo último que va haciendo el maestro en el turno en marcha, en llano (lo de
    `lanzados.legible`: lo que escribe y cada `cotejo` que corre). Vacío si no hay turno."""
    curso = _crudo(proyecto).get("en_curso")
    if not curso:
        return []
    lineas = []
    for linea in _ANSI.sub("", _texto(curso.get("out"))).splitlines():
        dice = lanzados.legible(linea)
        if dice and not dice.startswith("— Terminó"):
            lineas.extend(l for l in dice.splitlines() if l.strip())
    return lineas[-limite:]


def marcar_repartido(proyecto, indice):
    """La persona pulsó «Repartir» en ese turno: el botón no vuelve a salir."""
    with _cerrojo:
        datos = _crudo(proyecto)
        if 0 <= indice < len(datos["turnos"]):
            datos["turnos"][indice]["repartido"] = True
            _guardar(datos)
