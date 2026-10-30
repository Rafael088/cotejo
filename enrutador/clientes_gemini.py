"""Lo de Gemini CLI en `enrutador/clientes.py`: sus ajustes del proyecto y de la persona.

Aquí vive lo que Cotejo lee, filtra y le pasa a Gemini CLI antes de lanzarlo —los servidores
MCP, las políticas, los hooks y comandos que correrían solos—, sin lanzar nada. `clientes.py`
lo reexporta para quien lo usa; la política TOML sigue allí, porque se arma con `prohibidos`.
"""

import json
import os
import re
import sys


def _sin_comentarios_jsonc(texto):
    """JSONC a JSON: sin comentarios `//` y `/* */` (fuera de las cadenas) ni comas sueltas
    antes de `}` o `]`."""
    salida, i, n, cadena = [], 0, len(texto), False
    while i < n:
        c = texto[i]
        if cadena:
            salida.append(c)
            if c == "\\" and i + 1 < n:
                salida.append(texto[i + 1])
                i += 1
            elif c == '"':
                cadena = False
        elif c == '"':
            cadena = True
            salida.append(c)
        elif texto.startswith("//", i):
            fin = texto.find("\n", i)
            i = n if fin < 0 else fin
            continue
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
            continue
        else:
            salida.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(salida))

# Gemini CLI lee la config del proyecto de `<donde arranca>/.gemini/settings.json` en cuanto el
# espacio de trabajo es de confianza, y sin interfaz se niega a correr en uno que no lo sea
# (https://geminicli.com/docs/cli/trusted-folders/): Cotejo le da la confianza
# (`GEMINI_CLI_TRUST_WORKSPACE`) y con ella venían los servidores MCP del proyecto, sus hooks
# y sus comandos. Probado con Gemini CLI 0.61 (`pruebas/test_config_gemini_opencode.py`).
AJUSTES_GEMINI_DEL_PROYECTO = os.path.join(".gemini", "settings.json")
# El servidor que arma `mcp.serverCommand` se llama así.
SERVIDOR_DE_COMANDO_GEMINI = "mcp"
# Lo que `--allowed-mcp-server-names` deja cuando la persona no tiene ninguno: con la lista
# vacía Gemini no filtraría nada.
NINGUN_SERVIDOR_GEMINI = "cotejo-ninguno"


def _gemini_ajustes(ruta):
    """Los ajustes de Gemini de ese archivo (JSON con comentarios), `{}` si no existe o no
    es un objeto. Levanta `ValueError` si no se entiende."""
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(str(error))
    datos = json.loads(_sin_comentarios_jsonc(texto))
    return datos if isinstance(datos, dict) else {}


def _gemini_servidores(ajustes):
    """Los nombres de los servidores MCP que definen unos ajustes de Gemini."""
    servidores = ajustes.get("mcpServers")
    nombres = list(servidores) if isinstance(servidores, dict) else []
    mcp = ajustes.get("mcp")
    if isinstance(mcp, dict) and mcp.get("serverCommand"):
        nombres.append(SERVIDOR_DE_COMANDO_GEMINI)
    return nombres


def _gemini_lo_que_corre(ajustes):
    """Lo que estos ajustes del proyecto le hacen correr a Gemini solo y ninguna bandera apaga,
    en llano, para decirlo antes de lanzar. Lista vacía si no hay nada.

    Son los hooks (`hooks.<evento>`, que se suman a los de la persona y corren sin preguntar),
    los comandos de herramientas propias (`tools.discoveryCommand`, que corre al arrancar, y
    `tools.callCommand`) y las políticas que el proyecto se cargaría (`policyPaths`,
    `adminPolicyPaths`: las de administrador pesarían más que los prohibidos)."""
    motivos = []
    hooks = ajustes.get("hooks")
    if isinstance(hooks, dict) and any(isinstance(v, list) and v for v in hooks.values()):
        motivos.append("hooks (órdenes que Gemini corre solo, sin preguntar)")
    herramientas = ajustes.get("tools")
    if isinstance(herramientas, dict):
        if herramientas.get("discoveryCommand"):
            motivos.append("tools.discoveryCommand (un comando que corre al arrancar)")
        if herramientas.get("callCommand"):
            motivos.append("tools.callCommand (un comando que corre al usar una herramienta)")
    politicas = [clave for clave in ("policyPaths", "adminPolicyPaths") if ajustes.get(clave)]
    if politicas:
        motivos.append(" y ".join(politicas) + " (políticas que se cargan por encima de los "
                        "permisos de Cotejo)")
    return motivos


def _gemini_corre_codigo(ajustes):
    """¿Traen estos ajustes del proyecto algo que Gemini corre solo y que ninguna bandera
    apaga? Ver `_gemini_lo_que_corre`."""
    return bool(_gemini_lo_que_corre(ajustes))


def aviso_de_gemini(trabajo):
    """Por qué Gemini no va a arrancar en esa carpeta, en llano y con el archivo, o "".

    Desde cotejo-lbwsq4, si el `.gemini/settings.json` del worktree trae hooks, comandos de
    herramientas propias o políticas (o no se entiende), el worktree va sin confianza
    (`GEMINI_CLI_TRUST_WORKSPACE=false`) y Gemini, sin interfaz, se niega a arrancar con
    `FatalUntrustedWorkspaceError` —solo en su log, y en inglés—. Se dice **antes** de lanzar,
    con el archivo y qué quitar, para no gastar un lanzamiento condenado. Sin ese archivo (o
    sin nada de eso), "".
    """
    if not trabajo:
        return ""
    ruta = os.path.join(str(trabajo), AJUSTES_GEMINI_DEL_PROYECTO)
    try:
        ajustes = _gemini_ajustes(ruta)
    except ValueError:
        return (f"Gemini no va a arrancar: «{ruta}» no se entiende (JSON roto) y, sin leerlo, "
                f"el worktree va sin confianza; sin interfaz se niega a correr (su log dice "
                f"«FatalUntrustedWorkspaceError»). Arréglalo o bórralo, o elige otro modelo, y "
                f"vuelve a lanzarla.")
    motivos = _gemini_lo_que_corre(ajustes)
    if not motivos:
        return ""
    return (f"Gemini no va a arrancar: «{ruta}» trae {'; '.join(motivos)}, y con eso el worktree "
            f"va sin confianza; sin interfaz se niega a correr (su log dice "
            f"«FatalUntrustedWorkspaceError»). Quita eso de ese archivo (o bórralo), o elige "
            f"otro modelo, y vuelve a lanzarla; sus servidores MCP no hacen falta quitarlos.")


def _gemini_ajustes_de_la_persona(entorno):
    """Las rutas de los ajustes de Gemini de la persona que Cotejo lee: los del sistema por
    defecto, los suyos y los del sistema (`GEMINI_CLI_HOME` y las dos variables de sus rutas,
    que son las que usa Gemini). Las que no existen o no se entienden, fuera."""
    casa = entorno.get("GEMINI_CLI_HOME") or os.path.expanduser("~")
    sistema = entorno.get("GEMINI_CLI_SYSTEM_SETTINGS_PATH") or {
        "darwin": "/Library/Application Support/GeminiCli/settings.json",
        "win32": "C:\\ProgramData\\gemini-cli\\settings.json"}.get(
            sys.platform, "/etc/gemini-cli/settings.json")
    defectos = (entorno.get("GEMINI_CLI_SYSTEM_DEFAULTS_PATH") or
                os.path.join(os.path.dirname(sistema), "system-defaults.json"))
    for ruta in (defectos, os.path.join(casa, ".gemini", "settings.json"), sistema):
        try:
            yield _gemini_ajustes(ruta)
        except ValueError:
            continue


def _gemini_politicas_de_la_persona(entorno=None):
    """Las rutas de políticas que Gemini CLI cargaría si Cotejo no le pasara `--policy`: los
    `policyPaths` de los ajustes de la persona (los del sistema por defecto, los suyos y los
    del sistema, en ese orden, como los lee Gemini) y, si no pone ninguno, su carpeta
    `~/.gemini/policies`, que es la de la tier User (https://geminicli.com/docs/reference/policy-engine/, «Policy
    locations» y «`policyPaths`»). Hacen falta porque `--policy` las sustituye, no las suma."""
    entorno = os.environ if entorno is None else entorno
    rutas = []
    for ajustes in _gemini_ajustes_de_la_persona(entorno):
        propias = ajustes.get("policyPaths")
        if isinstance(propias, list):
            rutas += [str(p) for p in propias if isinstance(p, str) and p]
    if rutas:
        return list(dict.fromkeys(rutas))
    casa = entorno.get("GEMINI_CLI_HOME") or os.path.expanduser("~")
    return [os.path.join(casa, ".gemini", "policies")]


def _gemini_policy_argv(politica, entorno=None):
    """Los `--policy` de Gemini CLI: primero las políticas de la persona y detrás la de Cotejo,
    que nunca la sustituye. Sin política de Cotejo no se pasa ninguna bandera: Gemini lee las
    suyas como siempre. La bandera admite varias, una por ruta."""
    if not politica:
        return []
    rutas = [*_gemini_politicas_de_la_persona(entorno), str(politica)]
    return [bandera for ruta in rutas for bandera in ("--policy", ruta)]


def _gemini_de_la_persona(entorno):
    """`(servidores, permitidos, excluidos)` de la config de Gemini de la persona: los nombres
    de sus servidores MCP (sus ajustes, los del sistema y los de sus extensiones) y sus listas
    `mcp.allowed` (`None` si no tiene) y `mcp.excluded`. Solo se leen nombres. Un archivo que no
    se entiende no suma nada: con él roto, Gemini tampoco arrancaría."""
    casa = entorno.get("GEMINI_CLI_HOME") or os.path.expanduser("~")
    servidores, permitidos, excluidos = [], None, set()
    for ajustes in _gemini_ajustes_de_la_persona(entorno):
        servidores += _gemini_servidores(ajustes)
        mcp = ajustes.get("mcp") if isinstance(ajustes.get("mcp"), dict) else {}
        if isinstance(mcp.get("allowed"), list) and mcp["allowed"]:
            permitidos = (permitidos or set()) | {str(n) for n in mcp["allowed"]}
        if isinstance(mcp.get("excluded"), list):
            excluidos |= {str(n) for n in mcp["excluded"]}
    extensiones = os.path.join(casa, ".gemini", "extensions")
    for nombre in sorted(os.listdir(extensiones)) if os.path.isdir(extensiones) else []:
        try:
            ajustes = _gemini_ajustes(os.path.join(extensiones, nombre, "gemini-extension.json"))
        except ValueError:
            continue
        servidores += _gemini_servidores(ajustes)
    return list(dict.fromkeys(servidores)), permitidos, excluidos


def _gemini_sin_lo_del_proyecto(trabajo, argv, env, entorno=None):
    """`(argumentos, variables)` de Gemini CLI sin lo que el `.gemini/settings.json` del
    worktree le haría arrancar.

    - **Servidores MCP del proyecto**: `--allowed-mcp-server-names` con los de la persona
      (https://geminicli.com/docs/reference/configuration/, «A comma-separated list of MCP
      server names to allow for the session»), sin los que el proyecto define —uno que
      redefine con el nombre de uno suyo ya no sería el suyo—, y respetando su `mcp.allowed` y
      su `mcp.excluded` (la bandera reemplaza a los dos). Sin ninguno suyo, un nombre que no
      existe: la lista vacía no filtraría nada.
    - **Hooks y comandos** (`_gemini_corre_codigo`) o unos ajustes que no se entienden: no hay
      bandera ni variable que los apague sin llevarse los de la persona (los ajustes de
      sistema, que pesarían más, tienen que ser de root). El worktree va sin confianza
      (`GEMINI_CLI_TRUST_WORKSPACE=false`): Gemini no lee nada del proyecto y, sin interfaz,
      se niega a arrancar con `FatalUntrustedWorkspaceError`. Mejor una tarea que no arranca,
      con el motivo en su log, que un programa del repo corriendo sin que nadie lo pida.

    Sin `.gemini/settings.json` en el worktree, nada cambia. Se lee al lanzar (Gemini tampoco
    relee sus servidores a media sesión)."""
    if not trabajo:
        return argv, env
    try:
        proyecto = _gemini_ajustes(os.path.join(trabajo, AJUSTES_GEMINI_DEL_PROYECTO))
    except ValueError:
        proyecto = None
    if proyecto is None or _gemini_corre_codigo(proyecto):
        return argv, {**env, "GEMINI_CLI_TRUST_WORKSPACE": "false"}
    suyos = set(_gemini_servidores(proyecto))
    if not suyos:
        return argv, env
    servidores, permitidos, excluidos = _gemini_de_la_persona(
        os.environ if entorno is None else entorno)
    lista = [n for n in servidores if n not in suyos and n not in excluidos and "," not in n
             and (permitidos is None or n in permitidos)]
    ninguno = NINGUN_SERVIDOR_GEMINI
    while ninguno in suyos:
        ninguno += "-"
    return argv + ["--allowed-mcp-server-names", ",".join(lista) or ninguno], env
