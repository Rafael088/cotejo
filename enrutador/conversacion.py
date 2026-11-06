"""La conversación con el maestro: cada mensaje de la persona es un turno de un cliente sin
interfaz (v1.3.0, cotejo-9ybn1a) que puede todo menos aprobar (v1.3.1, cotejo-va7lgn).

Lo que se dice el maestro (`maestro.instruccion`) lleva la conversación entera, recortada: no
todos los clientes tienen una forma documentada de retomar su sesión sin interfaz, y así vale
igual para Claude Code, Codex, OpenCode, Gemini CLI y Antigravity CLI. La conversación de cada
proyecto vive en `<estado>/maestro/<proyecto>.json` (fuera del vault, como `board.json`); la
salida de cada turno, al lado (`.out` y `.err`), y de ahí la lee el board mientras contesta.

**Lo que puede hacer el cliente** (`comando`, v1.3.1, cotejo-va7lgn): todo lo que haría la persona
en una terminal —leer y editar el código, correr comandos, crear, asignar, despachar, entregar,
bloquear— menos aprobar. Arranca en la carpeta del código (o en la de las tareas si no se sabe
cuál es). Cada cliente con su forma de no preguntar, porque sin nadie delante lo que pregunta
se niega solo:

- **Claude Code**: `--permission-mode bypassPermissions`, sin los ajustes del proyecto
  (`SOLO_AJUSTES_DE_LA_PERSONA`) y `stream-json` para ver en el board qué hace.
- **Codex**: `--dangerously-bypass-approvals-and-sandbox`, sin confianza en el proyecto (su
  `.codex/` no arranca servidores MCP). Codex escribe el progreso en stderr y solo el mensaje
  final en stdout (https://learn.chatgpt.com/docs/non-interactive-mode): stdout es la respuesta.
- **OpenCode**: `permission` con `edit`, `bash` (`{"*": "allow"}`) y `webfetch` en `allow`
  (https://opencode.ai/docs/permissions/), sin los servidores MCP ni los plugins del proyecto.
- **Gemini CLI**: `--approval-mode yolo`, sin lo que su `.gemini/settings.json` del proyecto le
  haría arrancar.
- **Antigravity CLI**: `--dangerously-skip-permissions`, ya sin la jaula de bubblewrap (no hay
  escritura que limitar), así que también habla en Windows y en un Linux sin bwrap.

Lo único vedado, aprobar, no se le confía al prompt: el candado (`candado.py`) fotografía antes
de cada turno lo que estaba aprobado y, al terminar (también si muere o se para), deshace lo
que el maestro aprobó y lo dice en su respuesta.

Lo lanza `motores/fondo.py` (`lanzar_aparte`), como todo lo que corre sin interfaz: en Windows sin
ninguna consola a la vista (`subproceso`). Para todos, el mismo `cotejo` que el board primero en
el PATH (`mismo_cotejo`); la config ya no va vedada (puede asignar modelos, como la persona). Aquí no hay GTK: la CLI (`cotejo maestro`) y el board lo usan
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
from . import candado, clientes, maestro, mismo_cotejo, procesos
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
                and not procesos.vivo(curso.get("pid"), curso.get("programa", ""),
                                   curso.get("nacio"))):
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
    permiso.update(edit="allow", webfetch="allow", bash={"*": "allow"})
    datos["permission"] = permiso
    return json.dumps(datos, ensure_ascii=False)


def comando(config, cliente, modelo, prompt, directorio, escritura):
    """`(argv, variables, carpeta donde arranca)` de un turno del maestro con `cliente`.

    `directorio` es la carpeta del código (o None); `escritura`, las carpetas donde escribe
    `cotejo` (`carpetas_de_escritura`): la primera es donde arranca si no hay código. Lo que pone
    la persona en `enrutador.maestro.argumentos_extra.<cliente>` solo añade; los permisos de aquí
    van siempre.
    """
    from . import niveles, preparar
    propios = preparar._propios(config, cliente)
    extra = list(propios.get("argumentos_extra") or ())
    extra += list(((config.get("maestro") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ())
    trabajo = directorio or (escritura[0] if escritura else None)
    env = {}
    if cliente.nombre == "claude":
        extra += ["--output-format", "stream-json", "--verbose",
                  *clientes.SOLO_AJUSTES_DE_LA_PERSONA, "--permission-mode", "bypassPermissions"]
    elif cliente.nombre == "codex":
        # `--skip-git-repo-check`: `exec` se niega fuera de un repo, y el proyecto puede no serlo.
        extra += (["--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check"]
                  + clientes._codex_sin_confianza(trabajo))
    elif cliente.nombre == "opencode":
        env = {"OPENCODE_CONFIG_CONTENT": _permisos_opencode(
            os.environ.get("OPENCODE_CONFIG_CONTENT"))}
        env = clientes._opencode_sin_plugins_del_proyecto(
            trabajo, clientes._opencode_sin_mcp_del_proyecto(trabajo, env))
    elif cliente.nombre == "gemini":
        extra, env = clientes._gemini_sin_lo_del_proyecto(
            trabajo, extra + ["--approval-mode", "yolo"], {"GEMINI_CLI_TRUST_WORKSPACE": "true"})
    elif cliente.nombre == "antigravity":
        # Las de `cotejo` (tareas, estado) al espacio de trabajo, con la del código.
        extra += (cliente.permisos([c for c in escritura if c != trabajo])[0]
                  + ["--dangerously-skip-permissions"])
    concreto = niveles.modelo_concreto(modelo, config.get("modelos"))
    if concreto is not None and concreto.cliente == cliente.nombre:
        modelo_cliente = cliente.modelo_de(concreto.modelo, concreto.modelo_id)
        extra += list(concreto.argumentos)
    else:
        modelo_cliente = cliente.modelo_de(modelo or "", "")
    argv = cliente.argv_sin_interfaz(modelo_cliente, prompt,
                                     comando=propios.get("comando"), extra=extra)
    return argv, env, trabajo


def carpetas_de_escritura(carpeta_tareas):
    """Donde escribe `cotejo crear` (la carpeta del archivo de tareas del proyecto) y la de
    estado (bitácora, ahorro, esta conversación): donde arranca el maestro si no hay código."""
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
    """Cierra el turno en curso con `respuesta`, después de que el candado deshaga lo que el
    maestro aprobó en él: lo deshecho va al final de lo que ve la persona."""
    curso = datos.pop("en_curso", None) or {}
    texto, ok = respuesta
    texto = maestro.sin_marca(texto) or texto
    aviso = candado.revisar(curso.get("foto"))
    turno = {"quien": QUIEN_MAESTRO, "texto": "\n\n".join(filter(None, (texto, aviso))),
             "ok": ok, "ts": time.time(), "cliente": curso.get("cliente"),
             "out": curso.get("out"), "err": curso.get("err")}
    if aviso:
        turno["candado"] = aviso
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
        if curso and procesos.vivo(curso.get("pid"), curso.get("programa", ""),
                                   curso.get("nacio")):
            raise NoSePuede("El maestro todavía está contestando lo anterior: espera a que "
                            "termine o páralo.")
        datos.pop("en_curso", None)
        n = len(datos["turnos"])
        base = carpeta() / f"{_nombre(proyecto)}-{n + 1}-{int(time.time())}"
        base.parent.mkdir(parents=True, exist_ok=True)
        # Lo aprobado antes del turno, para deshacer al cerrarlo lo que apruebe el maestro.
        curso = {"cliente": armado["cliente"], "out": str(base) + ".out",
                 "err": str(base) + ".err", "desde": time.time(),
                 "asignadas": armado["asignadas"],
                 "foto": candado.foto(proyecto, armado.get("directorio"))}
        try:
            entorno = mismo_cotejo.entorno(armado["env"])
        except OSError as error:
            raise NoSePuede(f"No pude preparar el Cotejo que usará el maestro: {error}") from error
        try:
            proceso = fondo.lanzar_aparte(armado["argv"], armado.get("trabajo"), curso["out"],
                                          curso["err"], ajustes, entorno,
                                          etiqueta="maestro-" + _nombre(proyecto))
        except OSError as error:
            raise NoSePuede(f"No pude lanzar «{armado['argv'][0]}»: {error}") from error
        curso.update(pid=proceso.pid, programa=os.path.basename(armado["argv"][0]),
                     nacio=procesos.nacimiento(proceso.pid))
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
        procesos.terminar(curso.get("pid"), curso.get("programa", ""), curso.get("nacio"))
        if anotar:
            _cerrar(datos, ("Lo paraste antes de que contestara.", False))
        else:
            datos.pop("en_curso", None)
            _guardar(datos)
            candado.revisar(curso.get("foto"))   # sin conversación, queda en la bitácora
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
