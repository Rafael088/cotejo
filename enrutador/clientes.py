"""Los clientes de IA que saben ejecutar un modelo, y cómo se les habla desde la línea de comandos.

El catálogo guarda de cada modelo **qué cliente lo ejecuta** (`claude`, `opencode`, `codex`…),
pero hasta aquí nadie usaba ese dato: los motores lanzaban `claude` siempre, así que despachar
una tarea asignada a `#agente/kimi-k2.7-code` acababa en `claude --model kimi-k2.7-code`, que no
existe. Este módulo es la tabla que faltaba: con qué se le pide una tarea a cada cliente sin
interfaz (lo que usa el motor `headless`) y con qué se le abre en una terminal con una primera
instrucción (lo que usa `maestro`).

Aquí no se lanza nada —eso sigue siendo solo de `motores/`—; solo se arman listas de argumentos.

Dos formas de nombrar el modelo, igual que en `niveles.Nivel`: Claude Code entiende el alias
(`opus`), que sobrevive a que salga un modelo nuevo; el resto quiere el id que entiende su
proveedor (`opencode-go/kimi-k2.7-code`).
"""

import json
import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Cliente:
    nombre: str
    ejecutable: str
    # Sin interfaz: <ejecutable> <sin_interfaz> <modelo> <extra> <prompt_sin_interfaz> <prompt>
    sin_interfaz: tuple
    bandera_modelo: str
    prompt_sin_interfaz: tuple = ()
    # En una terminal, con una primera instrucción y la sesión abierta para seguir hablando.
    prompt_interactivo: tuple = ()
    usa_alias: bool = False
    titulo: str = ""   # cómo se llama en el board
    # Con argumentos extra, un `--` antes del prompt sin interfaz. En Claude Code
    # `--allowedTools <tools...>` se come todo lo que venga detrás hasta la siguiente bandera:
    # `claude -p --allowedTools Bash(cotejo:*) "<prompt>"` tomaba el prompt por otra
    # herramienta y salía con «Input must be provided» sin hacer nada (cotejo-p0fybl).
    fin_de_opciones: bool = False

    def modelo_de(self, modelo, modelo_id):
        """El nombre del modelo tal como lo entiende este cliente. La entrada de fábrica que se
        llama como el cliente (`codex`, `opencode`) y no trae id es «el que tenga por defecto»:
        "" y se lanza sin `-m` (`niveles.DE_FABRICA`)."""
        if not modelo_id and modelo != self.nombre and not self.usa_alias:
            from .niveles import DE_FABRICA
            if any(n.modelo == modelo and n.cliente == self.nombre and not n.modelo_id
                   for n in DE_FABRICA):
                return ""
        if modelo == self.nombre and not modelo_id:
            return ""
        if self.usa_alias:
            # Un alias de Claude (`opus`) si lo es; si es un modelo de Claude registrado a
            # mano, su id.
            from .niveles import POR_MODELO
            return modelo if modelo in POR_MODELO else (modelo_id or modelo)
        return modelo_id or modelo

    def argv_sin_interfaz(self, modelo, prompt, comando=None, extra=()):
        # Sin modelo, el que el cliente tenga por defecto (lo usa el inicio, que no es una
        # tarea con `#agente/<modelo>`): una bandera con el valor vacío no la entiende ninguno.
        con_modelo = [self.bandera_modelo, modelo] if modelo else []
        fin = ["--"] if extra and self.fin_de_opciones else []
        return (list(comando or [self.ejecutable]) + list(self.sin_interfaz) +
                con_modelo + list(extra) +
                list(self.prompt_sin_interfaz) + fin + [prompt])

    def argv_interactivo(self, prompt, modelo="", comando=None, extra=()):
        con_modelo = [self.bandera_modelo, modelo] if modelo else []
        return (list(comando or [self.ejecutable]) + con_modelo + list(extra) +
                list(self.prompt_interactivo) + [prompt])

    def permisos(self, carpetas, interactivo=False, entorno=None):
        """Lo que este cliente necesita para escribir en `carpetas` —y solo ahí— cuando corre
        solo (v1.3.0, cotejo-p0fybl): `(argumentos, variables de entorno)`.

        Lo usa el inicio, cuyo agente corre `cotejo init` y compañía: escriben en la carpeta
        del proyecto (y en su `.git`), en la config de Cotejo y en su carpeta de estado. Cada
        cliente lo pide a su manera, con lo que trae la versión instalada:

        - **Codex** (`codex exec`) corre en un sandbox de solo lectura y `init` fallaba con
          `Errno 30`: `--sandbox workspace-write` deja escribir en el directorio de trabajo y
          `--add-dir` en cada carpeta, nada más (su `workspace-write` protege el `.git` de las
          carpetas que añade; por eso el `.git` del proyecto va aparte, para el commit
          inicial). `--skip-git-repo-check` porque un proyecto nuevo aún no es un repo, y
          `exec` se niega a correr fuera de uno; la sesión interactiva no tiene esa bandera.
        - **OpenCode** no tiene sandbox, pero sin nadie que conteste rechaza todo lo que toque
          fuera del proyecto (`external_directory`): se le da ese permiso solo para estas
          carpetas, por `OPENCODE_CONFIG_CONTENT`, que se funde con la config de la persona sin
          tocar sus archivos (y con lo que ya trajera esa variable).
        - **Gemini CLI** sin interfaz no corre en una carpeta que no sea de confianza, y un
          proyecto nuevo nunca lo es: `GEMINI_CLI_TRUST_WORKSPACE`, solo para esta sesión. Su
          shell no está encerrado; el permiso de correr `cotejo` va aparte, como el de Claude
          (`preparar.argumentos_extra`).
        - **Antigravity CLI** (`agy`, cotejo-r4yg0n): `--add-dir` por carpeta, que la suma al
          espacio de trabajo, donde leer y escribir archivos está permitido sin preguntar
          (https://antigravity.google/docs/cli/reference y …/docs/cli/headless). Sus comandos
          de shell sí preguntan, y sin interfaz se niegan solos: el permiso va aparte
          (`preparar.argumentos_extra`, `terminal_libre`).
        - **Claude Code** no necesita nada: su Bash no está encerrado y `cotejo` ya tiene
          permiso (`--allowedTools Bash(cotejo:*)`).
        """
        carpetas = [str(c) for c in dict.fromkeys(str(c) for c in carpetas if c)]
        if self.nombre == "codex":
            argv = ["--sandbox", "workspace-write"]
            if not interactivo:
                argv.append("--skip-git-repo-check")
            for carpeta in carpetas:
                argv += ["--add-dir", carpeta]
            return argv, {}
        if self.nombre == "opencode":
            entorno = os.environ if entorno is None else entorno
            return [], {"OPENCODE_CONFIG_CONTENT": _opencode_con_permiso(
                carpetas, entorno.get("OPENCODE_CONFIG_CONTENT"))}
        if self.nombre == "gemini":
            return [], {"GEMINI_CLI_TRUST_WORKSPACE": "true"}
        if self.nombre == "antigravity":
            return [a for carpeta in carpetas for a in ("--add-dir", carpeta)], {}
        return [], {}

    def terminal_libre(self, carpetas, ramas=None, politica_gemini=None, entorno=None,
                       sandbox=None):
        """Los permisos del agente que lanza el board (v1.3.0, cotejo-7yfw1e, dec-kiik):
        `(argumentos, variables de entorno)`.

        Terminal libre dentro del worktree de su tarea —puede correr las pruebas y los builds
        sin que nadie configure nada— y una lista corta de prohibidos de fábrica
        (`prohibidos`): subir privilegios (sudo/su), `git push --force`, empujar a `main` o a la
        rama por defecto (`ramas`) y borrar fuera del worktree. Cada cliente con lo suyo:

        - **Claude Code**: `acceptEdits`, `--allowedTools Bash` (todo el Bash) y
          `--disallowedTools` con los prohibidos, que ganan a cualquier permiso. Con `sandbox`
          (la clave `sandbox` que arma `sandbox.del_lanzamiento`, cotejo-amui0f), además su
          Bash corre encerrado: escribe solo en esas carpetas y sale a la red solo a sus
          remotos, así que borrar fuera del worktree falla también por `python3 -c`, `find
          -delete` o `cd /x && rm y`, que los patrones no ven.
        - **Codex**: su sandbox `workspace-write` (`permisos`): solo escribe en las carpetas de
          la tarea, no tiene red (no puede empujar nada) y no puede subir privilegios.
        - **OpenCode**: `permission.bash` con todo en `allow` y los prohibidos en `deny` al
          final (en OpenCode gana la última regla que casa), encima de lo que da `permisos`.
        - **Gemini CLI**: `auto_edit` y una política (`--policy`, `politica_gemini`, el archivo
          que escribe `guardas.preparar` con `politica_gemini_toml`) que deja todo el shell y
          niega los prohibidos.
        - **Antigravity CLI**: `--dangerously-skip-permissions`, la única forma documentada de
          aprobar sus comandos en una sola invocación (sin ella, sin interfaz, todo comando se
          niega solo). Sus reglas `deny` solo se leen de `~/.gemini/antigravity-cli/settings.json`,
          la config de la persona, que Cotejo no toca: los prohibidos de este quedan en las
          guardas del PATH. Su sandbox (`--sandbox`) no va por defecto: en Linux esconde lo que
          no monta, y el lanzador de `cotejo` vive fuera del worktree; quien lo quiera lo pone en
          `lanzar.argumentos_extra.antigravity`.

        Debajo de todos, el PATH del agente lleva las guardas de `guardas.py` (un `git`
        que no deja empujar a la fuerza ni a esas ramas, y un `sudo`/`su` que se niega).
        """
        ramas = ramas_protegidas(ramas)
        argv, env = self.permisos(carpetas, entorno=entorno)
        if self.nombre == "claude":
            from . import sandbox as caja
            return (["--permission-mode", "acceptEdits", "--allowedTools", "Bash",
                     *(caja.argumentos_claude(sandbox) if sandbox else []),
                     "--disallowedTools", *[f"Bash({p})" for p in prohibidos(ramas)]], env)
        if self.nombre == "opencode":
            return argv, {"OPENCODE_CONFIG_CONTENT": _opencode_con_prohibidos(
                env["OPENCODE_CONFIG_CONTENT"], prohibidos(ramas))}
        if self.nombre == "gemini":
            return (["--approval-mode", "auto_edit"] +
                    (["--policy", str(politica_gemini)] if politica_gemini else []), env)
        if self.nombre == "antigravity":
            return argv + ["--dangerously-skip-permissions"], env
        return argv, env

    @property
    def instalado(self):
        return shutil.which(self.ejecutable) is not None


def _opencode_con_permiso(carpetas, previo=None):
    """La config de OpenCode (JSON) con `permission.external_directory` en `allow` para cada
    carpeta y lo de dentro (`<carpeta>/*`, la forma en que OpenCode lo pide), encima de lo que
    ya trajera `OPENCODE_CONFIG_CONTENT`. Si lo de antes no se entiende, se descarta: un JSON
    roto ahí tampoco lo leería OpenCode."""
    try:
        datos = json.loads(previo) if previo else {}
    except ValueError:
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    permiso = datos.get("permission")
    if not isinstance(permiso, dict):
        # Un permiso de un solo valor («allow», «ask») vale para todo: queda como regla general.
        permiso = {"*": permiso} if isinstance(permiso, str) else {}
    externo = permiso.get("external_directory")
    externo = ({"*": externo} if isinstance(externo, str) else
               dict(externo) if isinstance(externo, dict) else {})
    for carpeta in carpetas:
        externo[carpeta] = "allow"
        externo[carpeta.rstrip("/") + "/*"] = "allow"
    datos["permission"] = {**permiso, "external_directory": externo}
    return json.dumps(datos, ensure_ascii=False)


# --- los prohibidos de fábrica del agente que lanza el board (dec-kiik) -------------------------

# Siempre protegida, aunque el repo diga que su rama por defecto es otra.
RAMA_PRINCIPAL = "main"
# Subir privilegios: sudo y su, y sus primos (doas; pkexec abriría una ventana pidiendo la
# contraseña en el escritorio de la persona).
ESCALAR = ("sudo", "su", "doas", "pkexec")
# Lo que borra: con ruta absoluta, desde la casa o subiendo con `..` se sale del worktree; con
# ruta relativa sin `..`, se queda dentro.
BORRAR = ("rm", "rmdir", "unlink", "shred")


def ramas_protegidas(ramas=None):
    """`main` y las que se digan (la rama por defecto del repo), sin repetir ni vacías."""
    if isinstance(ramas, str):
        ramas = [ramas]
    return list(dict.fromkeys([RAMA_PRINCIPAL] + [r.strip() for r in (ramas or ()) if r and r.strip()]))


def prohibidos(ramas=None):
    """Los prohibidos de fábrica como patrones de comando, donde `*` es cualquier cosa (también
    nada): la misma lista para Claude (`Bash(<patrón>)`), OpenCode (`permission.bash`) y Gemini
    (`commandRegex`, con `_regex_gemini`).

    Son patrones sobre el texto del comando, así que paran lo que se escribe de la forma normal
    (`sudo …`, `git push --force …`, `git push origin main`, `rm -rf /…`, `rm ../…`); lo que se
    salga de eso lo para el `git` de `guardas.py`, que lee los argumentos de verdad, o el
    sandbox del cliente (Codex, y Claude con `sandbox.py`). Borrar dentro del worktree con ruta
    relativa sigue libre."""
    lista = []
    for orden in ESCALAR:
        lista += [orden, f"{orden} *"]
    lista += ["git push *--force*", "git push -f*", "git push * -f*", "git push *+*",
              "git push *--mirror*", "git push *--all*"]
    for rama in ramas_protegidas(ramas):
        lista += [f"git push * {rama}", f"git push * {rama} *", f"git push *:{rama}",
                  f"git push *:{rama} *", f"git push *:refs/heads/{rama}*"]
    for orden in BORRAR:
        lista += [f"{orden} /*", f"{orden} * /*", f"{orden} ~*", f"{orden} * ~*",
                  f"{orden} *..*", f"{orden} *$HOME*", f"{orden} *${{HOME}}*"]
    return list(dict.fromkeys(lista))


def _opencode_con_prohibidos(previo, patrones):
    """La config de OpenCode con `permission.bash`: `*` en `allow` primero, las reglas de bash
    que ya trajera la persona después (si negó algo, sigue negado) y los prohibidos en `deny` al
    final, porque en OpenCode gana la última regla que casa."""
    datos = json.loads(previo)
    permiso = datos.setdefault("permission", {})
    anterior = permiso.get("bash")
    anterior = ({} if not isinstance(anterior, dict) else
                {k: v for k, v in anterior.items() if k != "*"})
    bash = {"*": "allow", **anterior}
    for patron in patrones:
        bash.pop(patron, None)
        bash[patron] = "deny"
    permiso["bash"] = bash
    permiso.setdefault("edit", "allow")
    return json.dumps(datos, ensure_ascii=False)


def _regex_gemini(patron):
    """Un patrón de `prohibidos` como `commandRegex` de Gemini, que se prueba contra el JSON
    de los argumentos justo después de `"command":"`: `*` no cruza la comilla que cierra el
    comando, y el final se ancla en ella. Solo se escapan los metacaracteres: Gemini es
    JavaScript, y ahí `\\ ` (un espacio escapado, lo que pondría `re.escape`) no es válido con
    la bandera `u`."""
    return "".join('[^"]*' if c == "*" else "\\" + c if c in METACARACTERES else c
                   for c in patron) + '"'


METACARACTERES = set(".^$+?()[]{}|\\/")


AVISO = ("Es uno de los prohibidos de fábrica del agente que lanza CotejoBoard: no subir "
         "privilegios, no git push --force, no empujar a main ni a la rama por defecto, no borrar "
         "fuera del worktree. Hazlo de otra forma o bloquea la tarea con el motivo.")


def politica_gemini_toml(ramas=None):
    """La política de Gemini CLI para el agente del board: todo el shell permitido (también con
    redirecciones) y los prohibidos negados con más prioridad."""
    def cadena(texto):
        return json.dumps(texto, ensure_ascii=False)   # una cadena TOML básica vale como JSON
    reglas = ['[[rule]]', 'toolName = "run_shell_command"', 'decision = "allow"',
              'priority = 100', 'allowRedirection = true', '']
    for patron in prohibidos(ramas):
        reglas += ['[[rule]]', 'toolName = "run_shell_command"',
                   f'commandRegex = {cadena(_regex_gemini(patron))}', 'decision = "deny"',
                   'priority = 900', f'denyMessage = {cadena(AVISO)}', '']
    return "# Lo escribe Cotejo antes de lanzar un agente desde el board.\n" + "\n".join(reglas)


CLIENTES = {
    "claude": Cliente("claude", "claude", ("-p",), "--model", usa_alias=True,
                      titulo="Claude Code", fin_de_opciones=True),
    "opencode": Cliente("opencode", "opencode", ("run",), "-m",
                        prompt_interactivo=("--prompt",), titulo="OpenCode"),
    "codex": Cliente("codex", "codex", ("exec",), "-m", titulo="Codex"),
    "gemini": Cliente("gemini", "gemini", (), "-m", prompt_sin_interfaz=("-p",),
                      prompt_interactivo=("-i",), titulo="Gemini CLI"),
    # Antigravity CLI (cotejo-r4yg0n): lo que Google da desde el 18-jun-2026 al plan gratuito,
    # Pro y Ultra en vez de Gemini CLI. Sus banderas, de https://antigravity.google/docs/cli/
    # reference y …/headless: `-p` corre un prompt sin interfaz, `-i` uno inicial y sigue la
    # sesión, `--model <slug>` (los que lista `agy models`). `--print-timeout 0` espera hasta
    # que termine el turno: la guía de headless dice que por defecto corta a los cinco minutos,
    # y el tope ya lo pone Cotejo (`timeout_seg`).
    "antigravity": Cliente("antigravity", "agy", ("--print-timeout", "0"), "--model",
                           prompt_sin_interfaz=("-p",), prompt_interactivo=("-i",),
                           titulo="Antigravity CLI"),
}


class ClienteDesconocido(Exception):
    pass


def de(nombre):
    """El cliente con ese nombre. Levanta con los que sí hay, para que el error diga qué hacer."""
    cliente = CLIENTES.get((nombre or "claude").strip().lower())
    if cliente is None:
        raise ClienteDesconocido(
            f"No sé cómo lanzar el cliente «{nombre}». Los que sé: "
            f"{', '.join(sorted(CLIENTES))}.")
    return cliente


def instalados():
    """Los nombres de los clientes que esta máquina tiene en el PATH, en el orden de la tabla."""
    return [nombre for nombre, cliente in CLIENTES.items() if cliente.instalado]


def esta_instalado(nombre):
    """¿Está en el PATH el cliente con ese nombre? Un cliente registrado a mano que esta tabla
    no conoce se busca por su nombre, que es lo único que de él se sabe."""
    cliente = CLIENTES.get((nombre or "").strip().lower())
    return cliente.instalado if cliente else shutil.which(nombre or "") is not None


# Lo que dicen el board y `cotejo maestro` cuando no hay ningún agente de terminal: una sola
# fuente para que digan lo mismo. No se inventa un comando de instalación: cada agente se
# instala como dice su propia documentación.
SIN_AGENTE = "El maestro necesita un agente de terminal y no encontré ninguno"
SIN_AGENTE_SALIDA = ("Instala uno (Claude Code, Codex, Antigravity CLI, Gemini CLI u opencode) "
                     "y vuelve a probar; "
                     "mientras tanto puedes trabajar las tareas desde cualquier agente con MCP")
SIN_AGENTE_TEXTO = f"{SIN_AGENTE}. {SIN_AGENTE_SALIDA}."


def aviso_sin_agentes():
    """El aviso de que esta máquina no tiene ningún agente de terminal, o "" si hay alguno.

    Es un aviso y no un error: Cotejo funciona sin maestro, y la decisión del enrutador no
    depende de la máquina (`despachable` no cambia). Solo dice que despachar no llegaría a nada.
    """
    if instalados():
        return ""
    return (f"No encontré ningún agente de terminal ({', '.join(CLIENTES)}) en el PATH: "
            f"puedes ver, decidir y entregar tareas, pero despachar o abrir el maestro "
            f"necesita instalar uno.")
