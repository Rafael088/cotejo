"""`cotejo mcp`: los mismos verbos que la CLI, por el Model Context Protocol y sobre stdio.

La CLI sigue siendo el contrato y esto es otra puerta al mismo sitio. Por eso el catálogo de
tools **no se escribe a mano**: sale de `cli.analizador()` —con los verbos del enrutador, de la
instalación y de los temas que se cuelgan de él—, y cada llamada se traduce a los argumentos de
la terminal y corre por `cli.main`. Un verbo o una bandera nuevos aparecen aquí solos; uno que no
exista en la CLI no puede aparecer, y eso incluye los que faltan a propósito: no hay tool para
finalizar una tarea ni para aceptar una decisión, igual que no hay verbo
(`test_no_hay_ningun_verbo_para_finalizar_una_tarea` mira las dos cosas). Pedirlas contesta lo
mismo que la CLI: que eso es de la persona, en el board.

Por defecto sirve solo el **núcleo** (`--perfil nucleo`): los verbos que el analizador marca con
`cli.nucleo()`, que es lo que un agente usa casi siempre y lo que se paga en cada sesión antes de
la primera llamada. `--perfil completo` sirve todos. Aquí no se elige ninguno: solo se filtra.

Sin dependencias, como el resto del núcleo: JSON-RPC 2.0 a mano, un mensaje por línea, que es
el transporte stdio de MCP. Solo `initialize`, `ping`, `tools/list` y `tools/call`; lo demás se
contesta con «método no encontrado».

La salida estándar es el canal del protocolo y nada más puede escribir en ella. Al arrancar, el
servidor se queda con un duplicado de los descriptores 0 y 1 y apunta los originales a /dev/null
y a stderr: así ni un `print` perdido ni un proceso hijo (las pruebas de `entregar`, un motor de
`despachar`) pueden colar bytes en mitad de un mensaje ni comerse los que llegan.
"""

import argparse
import contextlib
import io
import json
import os
import re
import sys
import traceback

from . import __version__

# Las versiones del protocolo que este servidor habla, la más nueva primero. Si el cliente pide
# una que está aquí, se le contesta con esa; si no, con la primera, y decide él si sigue.
VERSIONES = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

# El verbo que arranca este servidor no es una tool: sería un servidor dentro de otro.
NO_SON_TOOLS = {"mcp"}

# Qué verbos sirve. `nucleo` (el de por defecto) solo los marcados con `cli.nucleo()` en el
# analizador; `completo`, todos. El catálogo viaja en cada sesión antes de la primera llamada,
# y el núcleo es lo que un agente usa casi siempre; para lo demás está el completo.
NUCLEO, COMPLETO = "nucleo", "completo"
PERFILES = (NUCLEO, COMPLETO)

INSTRUCCIONES = (
    "Cotejo: las tareas de los proyectos y sus estados. Las mismas tools que los verbos de la "
    "CLI `cotejo`, con los mismos argumentos, y la misma respuesta en JSON. Enterarse con "
    "`tareas`; trabajar con `tomar`, `entregar` (con evidencia) o `bloquear` (con motivo). "
    "El conocimiento del repo (`.cotejo/`): `contexto`, `buscar`, `leer`; escribirlo con "
    "`anotar_*` y `bitacora`. Ese es el núcleo; `cotejo mcp --perfil completo` sirve "
    "además el resto de verbos (`proponer_decision`, `editar`, `resolver`, `protocolo`…). "
    "No hay tool para dar una tarea por hecha ni para aceptar una decisión, a propósito: eso lo "
    "hace una persona en CotejoBoard. `protocolo` (completo) devuelve el trato entero.")

# Códigos de JSON-RPC 2.0.
PARSEO, PETICION_INVALIDA, NO_EXISTE, PARAMETROS, INTERNO = -32700, -32600, -32601, -32602, -32603


# --- el catálogo, sacado de argparse --------------------------------------------


def _subcomandos(analizador):
    for accion in analizador._actions:
        if isinstance(accion, argparse._SubParsersAction):
            return accion
    return None


def _ayudas(subparsers):
    """La ayuda de cada subcomando, que argparse guarda en el padre y no en el hijo."""
    return {a.dest: a.help or "" for a in subparsers._choices_actions}


# Recortes solo de la composición MCP: la ayuda de la terminal (`--help`) no se toca. El agente
# paga cada carácter en cada sesión, así que lo que ya dice el nombre de la tool o del argumento
# no se repite (el «Equivale a `cotejo …`», el verbo delante de cada acción) y las ayudas que son
# la misma frase en siete verbos se dicen una vez y corta.
_AYUDA_REPO = re.compile(r"^El repo [^.]*\. Por defecto, su raíz git desde aquí$")
_AYUDA_RECORTES = (
    (_AYUDA_REPO, "Por defecto, aquí"),
)


def _ayuda_breve(texto):
    for patron, corta in _AYUDA_RECORTES:
        if patron.match(texto):
            return corta
    return texto


def _unir(verbo, accion):
    """La descripción de una tool de un verbo con acciones. La del verbo da el contexto
    (`fuentes info`: «Activarla» solo no dice qué), salvo que la de la acción ya lo diga: en
    `anotar` ambas empiezan por «Una entrada» y repetirlo cuatro veces es puro peso."""
    if not verbo or not accion or accion.split()[:2] == verbo.split()[:2]:
        return accion or verbo
    return f"{verbo}. {accion}"


def _esquema(accion):
    """El JSON Schema de un argumento de argparse."""
    if accion.nargs == 0:  # store_true y compañía
        esquema = {"type": "boolean"}
    else:
        tipo = {int: "integer", float: "number"}.get(accion.type, "string")
        uno = {"type": tipo}
        if accion.choices is not None:
            uno["enum"] = list(accion.choices)
        varios = accion.nargs in ("*", "+") or isinstance(accion, argparse._AppendAction)
        esquema = {"type": "array", "items": uno} if varios else uno
    if accion.help:
        esquema["description"] = _ayuda_breve(accion.help)
    if accion.default not in (None, False, argparse.SUPPRESS, "") and accion.nargs != 0:
        esquema["default"] = accion.default
    return esquema


def _argumentos(analizador):
    """Los argumentos que un tool acepta, en orden: (accion, es_posicional)."""
    for accion in analizador._actions:
        if isinstance(accion, (argparse._HelpAction, argparse._VersionAction,
                               argparse._SubParsersAction)):
            continue
        yield accion, not accion.option_strings


def _requerido(accion, posicional):
    if posicional:
        return accion.nargs not in ("?", "*")
    return accion.required


def catalogo(analizador=None, perfil=COMPLETO):
    """{nombre de la tool: (ruta de verbos, subanalizador, descripción)}.

    Un verbo con acciones (`fuentes info`, `temas usar`) da una tool por acción, `fuentes_info`,
    y el verbo a secas también es una tool si se puede llamar sin acción (`fuentes`). Con el
    perfil `nucleo`, solo los verbos que el analizador marca con `cli.nucleo()`, con todas sus
    acciones: aquí no se elige ninguno, solo se filtra.
    """
    if perfil not in PERFILES:
        raise ValueError(f"perfil desconocido: {perfil}")
    from . import cli
    analizador = analizador or cli.analizador()
    tools = {}
    raiz = _subcomandos(analizador)
    ayudas = _ayudas(raiz)
    for verbo, sub in raiz.choices.items():
        if verbo in NO_SON_TOOLS or (perfil == NUCLEO and not getattr(sub, "nucleo", False)):
            continue
        acciones = _subcomandos(sub)
        if acciones is None or not acciones.required:
            tools[verbo] = ((verbo,), sub, ayudas.get(verbo, ""))
        if acciones is not None:
            ayudas_accion = _ayudas(acciones)
            for accion, subsub in acciones.choices.items():
                descripcion = _unir(ayudas.get(verbo, ""), ayudas_accion.get(accion, ""))
                tools[f"{verbo}_{accion}"] = ((verbo, accion), subsub, descripcion)
    return tools


def tools(analizador=None, perfil=COMPLETO):
    """La respuesta de `tools/list`."""
    lista = []
    for nombre, (ruta, sub, descripcion) in catalogo(analizador, perfil).items():
        propiedades, requeridos = {}, []
        for accion, posicional in _argumentos(sub):
            propiedades[accion.dest] = _esquema(accion)
            if _requerido(accion, posicional):
                requeridos.append(accion.dest)
        esquema = {"type": "object", "properties": propiedades}
        if requeridos:
            esquema["required"] = requeridos
        lista.append({
            "name": nombre,
            "description": descripcion,
            "inputSchema": esquema,
        })
    return lista


class ArgumentosMalos(ValueError):
    pass


def argv(nombre, argumentos, analizador=None, perfil=COMPLETO):
    """Los argumentos de la terminal que equivalen a llamar a la tool `nombre` con `argumentos`.

    Las opciones van como `--bandera=valor`, para que un valor que empieza por guion no se lea
    como otra bandera, y las posicionales detrás de `--` por lo mismo.
    """
    entrada = catalogo(analizador, perfil).get(nombre)
    if entrada is None:
        raise KeyError(nombre)
    ruta, sub, _ = entrada
    argumentos = dict(argumentos or {})
    opciones, posicionales = [], []
    for accion, posicional in _argumentos(sub):
        if accion.dest not in argumentos:
            continue
        valor = argumentos.pop(accion.dest)
        if valor is None:
            continue
        if accion.nargs == 0:
            if not isinstance(valor, bool):
                raise ArgumentosMalos(f"«{accion.dest}» es true o false")
            if valor:
                opciones.append(accion.option_strings[-1])
            continue
        valores = valor if isinstance(valor, list) else [valor]
        if any(isinstance(v, (dict, list)) for v in valores):
            raise ArgumentosMalos(f"«{accion.dest}» no admite objetos ni listas anidadas")
        valores = [str(v).lower() if isinstance(v, bool) else str(v) for v in valores]
        if posicional:
            posicionales.extend(valores)
        else:
            bandera = accion.option_strings[-1]
            opciones.extend(f"{bandera}={v}" for v in valores)
    if argumentos:
        raise ArgumentosMalos(
            f"«{nombre}» no tiene {', '.join(sorted(argumentos))}; "
            "`tools/list` dice qué acepta cada una")
    return [*ruta, *opciones, *(["--", *posicionales] if posicionales else [])]


# --- llamar a una tool ----------------------------------------------------------


def llamar(nombre, argumentos, perfil=COMPLETO):
    """Corre la tool como si fuera el verbo en la terminal. Devuelve el resultado de MCP."""
    from . import cli
    try:
        linea = argv(nombre, argumentos, perfil=perfil)
    except ArgumentosMalos as error:
        return _resultado(str(error), error=True)
    salida, errores = io.StringIO(), io.StringIO()
    codigo = 0
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
        try:
            codigo = cli.main(linea)
        except SystemExit as fin:  # argparse, al no entender los argumentos
            codigo = fin.code if isinstance(fin.code, int) else 2
        except Exception:  # un fallo de un verbo no tumba el servidor
            traceback.print_exc()
            codigo = 1
    texto = salida.getvalue().strip()
    ruido = errores.getvalue().strip()
    if not texto:
        texto = ruido or f"`cotejo {' '.join(linea)}` no devolvió nada (código {codigo})."
    resultado = _resultado(texto, error=bool(codigo))
    try:
        datos = json.loads(texto)
    except ValueError:
        datos = None
    if isinstance(datos, dict):
        resultado["structuredContent"] = datos
    if codigo and ruido and ruido not in texto:
        resultado["content"].append({"type": "text", "text": ruido})
    return resultado


def _resultado(texto, error=False):
    return {"content": [{"type": "text", "text": texto}], "isError": error}


# --- JSON-RPC ------------------------------------------------------------------


def _error(id_, codigo, mensaje):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": mensaje}}


def atender(mensaje, perfil=COMPLETO):
    """Un mensaje de JSON-RPC → su respuesta, o None si era una notificación."""
    if not isinstance(mensaje, dict) or mensaje.get("jsonrpc") != "2.0" \
            or not isinstance(mensaje.get("method"), str):
        if isinstance(mensaje, dict) and "method" not in mensaje and (
                "result" in mensaje or "error" in mensaje):
            return None  # la respuesta a algo que preguntamos nosotros: no preguntamos nada
        return _error(mensaje.get("id") if isinstance(mensaje, dict) else None,
                      PETICION_INVALIDA, "No es una petición JSON-RPC 2.0")
    metodo, params = mensaje["method"], mensaje.get("params") or {}
    if "id" not in mensaje:
        return None  # notificación (notifications/initialized, cancelled…): no se contesta
    id_ = mensaje["id"]
    if not isinstance(params, dict):
        return _error(id_, PARAMETROS, "params tiene que ser un objeto")

    if metodo == "initialize":
        pedida = params.get("protocolVersion")
        resultado = {
            "protocolVersion": pedida if pedida in VERSIONES else VERSIONES[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "cotejo", "title": "Cotejo", "version": __version__},
            "instructions": INSTRUCCIONES,
        }
    elif metodo == "ping":
        resultado = {}
    elif metodo == "tools/list":
        resultado = {"tools": tools(perfil=perfil)}
    elif metodo == "tools/call":
        nombre, argumentos = params.get("name"), params.get("arguments") or {}
        if not isinstance(argumentos, dict):
            return _error(id_, PARAMETROS, "arguments tiene que ser un objeto")
        if nombre not in catalogo(perfil=perfil):
            # Pedir aceptar una decisión o finalizar una tarea no es un error del cliente sino
            # algo que no es del agente: se contesta igual que la CLI, diciendo de quién es.
            from . import cli
            pedido = cli.de_la_persona(re.split(r"[_\W]+", str(nombre)))
            if pedido is None:
                fuera = perfil == NUCLEO and nombre in catalogo()
                return _error(id_, PARAMETROS, f"No hay ninguna tool «{nombre}»" + (
                    " en el perfil núcleo; está con `cotejo mcp --perfil completo`"
                    if fuera else ""))
            datos = {"esquema": cli.ESQUEMA, "error": pedido.mensaje, "salida": pedido.salida,
                     "reintentable": pedido.reintentable}
            resultado = _resultado(json.dumps(datos, ensure_ascii=False), error=True)
            resultado["structuredContent"] = datos
            return {"jsonrpc": "2.0", "id": id_, "result": resultado}
        resultado = llamar(nombre, argumentos, perfil)
    else:
        return _error(id_, NO_EXISTE, f"Método no soportado: {metodo}")
    return {"jsonrpc": "2.0", "id": id_, "result": resultado}


def servir(entrada, salida, perfil=NUCLEO):
    """Lee mensajes de `entrada` (bytes, uno por línea) y escribe las respuestas en `salida`."""
    for linea in entrada:
        if not linea.strip():
            continue
        try:
            mensaje = json.loads(linea)
        except ValueError:
            respuesta = _error(None, PARSEO, "No es JSON")
        else:
            try:
                if isinstance(mensaje, list):  # lotes: los quitó 2025-06-18, pero cuestan poco
                    respuesta = [r for r in (atender(m, perfil) for m in mensaje)
                                 if r is not None] or None
                else:
                    respuesta = atender(mensaje, perfil)
            except Exception as error:  # noqa: BLE001 — el servidor no se cae por un mensaje
                traceback.print_exc(file=sys.stderr)
                respuesta = _error(mensaje.get("id") if isinstance(mensaje, dict) else None,
                                   INTERNO, f"Error interno: {error}")
        if respuesta is not None:
            salida.write(json.dumps(respuesta, ensure_ascii=False).encode("utf-8") + b"\n")
            salida.flush()
    return 0


def cmd_mcp(args):
    # El protocolo se queda con copias de 0 y 1; los originales pasan a /dev/null y a stderr,
    # que es lo que heredan los procesos hijos y donde acaba cualquier escritura perdida.
    entrada = os.fdopen(os.dup(0), "rb", buffering=0)
    salida = os.fdopen(os.dup(1), "wb")
    sys.stdout.flush()
    nulo = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nulo, 0)
    os.close(nulo)
    os.dup2(2, 1)
    try:
        return servir(iter(entrada.readline, b""), salida, args.perfil)
    except KeyboardInterrupt:
        return 0


def anadir(sub):
    mcp = sub.add_parser(
        "mcp", help="Servidor MCP por stdio: los mismos verbos, como tools, para cualquier cliente")
    mcp.add_argument("--perfil", choices=PERFILES, default=NUCLEO,
                     help="Qué verbos sirve: «nucleo» (por defecto) los de cada día, "
                          "«completo» todos los de la CLI")
    mcp.set_defaults(funcion=cmd_mcp)
