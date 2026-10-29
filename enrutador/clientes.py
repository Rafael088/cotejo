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
import re
import shutil
import sys
from dataclasses import dataclass

from . import gemini_env


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
                       sandbox=None, vedados=()):
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
          -delete` o `cd /x && rm y`, que los patrones no ven. Sus herramientas de editar no
          pasan por ese sandbox: `vedados` (rutas absolutas, o relativas a donde arranca) va
          en `--disallowedTools` como `Edit(...)`, que vale para todas (cotejo-dgb7l2). Y
          `--setting-sources user` (`SOLO_AJUSTES_DE_LA_PERSONA`, cotejo-0hgn6x): los
          `.claude/settings*.json` del worktree no se cargan, ni al arrancar ni a media sesión,
          los escriba quien los escriba (otro agente que tuvo la tarea antes, o este con el
          sandbox apagado). Vedar la carpeta no basta: `denyWrite` no para un archivo que no
          existe, y Codex u OpenCode en el mismo worktree no pasan por el sandbox de Claude.
          Lo que se pierde son las skills de `.claude/skills` del repo (sin ajustes del
          proyecto, Claude no las lee); el `CLAUDE.md` y las skills de la persona siguen. La
          misma bandera deja fuera el `.mcp.json` del worktree (cotejo-j42qfc): sin interfaz,
          Claude arranca sus servidores sin preguntar, y correrían fuera del sandbox; con ella
          no arrancan ni aunque la persona tenga `enableAllProjectMcpServers`, y los suyos (los
          de `~/.claude.json`, los conectores de claude.ai y los de sus plugins) siguen.
        - **Codex**: su sandbox `workspace-write` (`permisos`): solo escribe en las carpetas de
          la tarea, no tiene red (no puede empujar nada) y no puede subir privilegios. Con
          `sandbox` (lo que arma `sandbox.del_lanzamiento`, como para Claude), en vez de
          `--sandbox` va un perfil de permisos propio (`_codex_perfil`, cotejo-srkywv) con las
          mismas carpetas: así puede commitear en su worktree y escribir la carpeta de la tarea,
          y sacar capturas con Firefox. Y el
          worktree va como proyecto sin confianza (`_codex_sin_confianza`, cotejo-j42qfc): un
          worktree hereda la confianza de su repo, y con ella Codex carga el
          `.codex/config.toml` que haya dentro, que puede arrancar servidores MCP fuera de su
          sandbox (o cambiarlo). Sin confianza, se salta esa capa del proyecto (config, hooks y
          reglas); la config de la persona y el `AGENTS.md` siguen.
        - **OpenCode**: `permission.bash` con todo en `allow` y los prohibidos en `deny` al
          final (en OpenCode gana la última regla que casa), encima de lo que da `permisos`. Y
          los servidores MCP que defina el proyecto (`opencode.json[c]` del worktree o de su
          `.opencode/`) apagados con `enabled: false` en esa misma config, que pesa más que la
          del proyecto (`_opencode_sin_mcp_del_proyecto`, cotejo-j42qfc); si el proyecto trae
          plugins o herramientas en JavaScript, sin su config entera
          (`_opencode_sin_plugins_del_proyecto`, cotejo-lbwsq4).
        - **Gemini CLI**: `auto_edit` y una política (`--policy`, `politica_gemini`, el archivo
          que escribe `guardas.preparar` con `politica_gemini_toml`) que deja todo el shell y
          niega los prohibidos. Y lo que el `.gemini/settings.json` del worktree le haría
          arrancar, fuera (`_gemini_sin_lo_del_proyecto`, cotejo-lbwsq4): sus servidores MCP,
          por `--allowed-mcp-server-names` con los de la persona; y si trae hooks o comandos que
          corren solos, el worktree va sin confianza y Gemini no arranca. Con la confianza
          Gemini también carga el `.env` (o `.gemini/.env`) del worktree o de una carpeta de
          arriba: las variables que corren código (`BASH_ENV`, `NODE_OPTIONS`, `LD_*`,
          `GIT_*`…, `gemini_env.VEDADAS`) que traiga van definidas vacías antes, y como Gemini
          solo añade las que no existen, no las pone (`gemini_env.sin_env_del_proyecto`,
          cotejo-4gvdy5); las demás siguen llegando. Codex (solo `~/.codex/.env`, sin
          `CODEX_*`) y OpenCode (compilado con `autoloadDotenv: false`) no cargan el del
          proyecto.
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
                     *SOLO_AJUSTES_DE_LA_PERSONA,
                     *(caja.argumentos_claude(sandbox) if sandbox else []),
                     "--disallowedTools", *[f"Bash({p})" for p in prohibidos(ramas)],
                     *[f"Edit({_ruta_de_permiso(v)})" for v in vedados]], env)
        trabajo = next((str(c) for c in carpetas if c), None)
        if self.nombre == "codex":
            if sandbox:
                return (["--skip-git-repo-check", *_codex_perfil(sandbox, trabajo),
                         *_codex_sin_confianza(trabajo)], env)
            return argv + _codex_sin_confianza(trabajo), env
        if self.nombre == "opencode":
            return argv, _opencode_sin_plugins_del_proyecto(
                trabajo, _opencode_sin_mcp_del_proyecto(trabajo, {
                    "OPENCODE_CONFIG_CONTENT": _opencode_con_prohibidos(
                        env["OPENCODE_CONFIG_CONTENT"], prohibidos(ramas))}))
        if self.nombre == "gemini":
            argv, env = _gemini_sin_lo_del_proyecto(
                trabajo, ["--approval-mode", "auto_edit"] +
                (["--policy", str(politica_gemini)] if politica_gemini else []), env, entorno)
            return argv, gemini_env.sin_env_del_proyecto(trabajo, env, entorno)
        if self.nombre == "antigravity":
            return argv + ["--dangerously-skip-permissions"], env
        return argv, env

    @property
    def instalado(self):
        return shutil.which(self.ejecutable) is not None


def _ruta_de_permiso(ruta):
    """Una ruta como la pide una regla de permisos de Claude Code: absoluta con `//` delante
    (una sola barra sería relativa a la config), relativa tal cual."""
    ruta = str(ruta).replace(os.sep, "/")
    return "/" + ruta if os.path.isabs(str(ruta)) else ruta


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
# Claude Code sin los ajustes del proyecto (cotejo-0hgn6x): ni `.claude/settings.json` ni
# `.claude/settings.local.json` del worktree, solo los de la persona (`~/.claude`) y lo que pasa
# Cotejo por `--settings`. Un hook dejado ahí correría fuera del sandbox, y un `allowWrite` o un
# `env` lo cambiarían; el `CLAUDE.md` del repo y las skills de la persona siguen cargando.
# Tampoco carga el `.mcp.json` del worktree (cotejo-j42qfc, probado con Claude 2.1.304 y en
# https://code.claude.com/docs/en/mcp: «Exclude project settings entirely with
# --setting-sources»), y los servidores MCP de la persona siguen. `--strict-mcp-config` también
# lo cerraría, pero solo deja los de `--mcp-config`: se llevaría los conectores de claude.ai y
# los de sus plugins, y pasarle los suyos sería copiar sus secretos a un archivo.
SOLO_AJUSTES_DE_LA_PERSONA = ("--setting-sources", "user")


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


# --- los servidores MCP del proyecto, fuera del agente del board (cotejo-j42qfc) ----------------

def _codex_sin_confianza(trabajo):
    """`-c projects={"<trabajo>"={trust_level="untrusted"}}`: Codex trata el worktree como un
    proyecto sin confianza en esta sesión, sin tocar su `~/.codex/config.toml`. Un worktree
    hereda la confianza del repo (`codex mcp list` dentro de uno lo muestra), y un proyecto de
    confianza carga su `.codex/config.toml`: ahí un `[mcp_servers.x]` arranca un programa fuera
    del sandbox de Codex. Sin confianza, Codex se salta las capas `.codex/` del proyecto
    (https://developers.openai.com/codex/config-advanced); la config de la persona, con sus
    servidores, sigue. La forma de tabla entera es la que funciona: con la clave en puntos
    (`projects."<ruta>".trust_level`) Codex 0.154 seguía cargando la capa del proyecto."""
    if not trabajo:
        return []
    ruta = json.dumps(os.path.abspath(trabajo), ensure_ascii=False)   # cadena TOML básica
    return ["-c", f'projects={{{ruta}={{trust_level="untrusted"}}}}']


# --- el perfil de permisos de Codex para el agente del board (cotejo-srkywv) ---------------------

# Con `--sandbox workspace-write` Codex no podía entregar ni commitear: el `.git` de cada carpeta
# que escribe —y, si es un puntero `gitdir:` como el de un worktree, la carpeta a la que apunta—
# queda de solo lectura sin forma de abrirlo (`git commit` fallaba con `index.lock`), y sin red su
# seccomp niega hasta los sockets locales, así que Firefox no arranca ni se abre un puerto. Los
# perfiles de permisos (https://developers.openai.com/codex/permissions, beta) sí lo permiten:
# reglas `write`/`read` por ruta, donde gana la más concreta y una regla explícita reabre esas
# rutas protegidas. Probado con Codex 0.154 en un worktree real.
PERFIL_CODEX = "cotejo-tarea"
# La red del perfil: solo lo local, por el proxy de Codex (`network_proxy`, experimental), que
# aplica la lista de dominios. Con la red encendida y sin proxy saldría a todo internet.
LOCALES_CODEX = ("localhost", "127.0.0.1")


def _gitdir_de(trabajo):
    """La carpeta a la que apunta el `.git` de un worktree (`gitdir: …`), o None."""
    if not trabajo:
        return None
    puntero = os.path.join(str(trabajo), ".git")
    try:
        with open(puntero, encoding="utf-8") as archivo:
            linea = archivo.readline().strip()
    except OSError:   # no existe, o es una carpeta (un repo normal)
        return None
    if not linea.startswith("gitdir:"):
        return None
    return os.path.abspath(os.path.join(str(trabajo), linea[len("gitdir:"):].strip()))


def _codex_perfil(caja, trabajo):
    """Los argumentos que lanzan Codex con el perfil `PERFIL_CODEX` en vez de `--sandbox`.

    `caja` es lo que arma `sandbox.del_lanzamiento` (las mismas carpetas que el sandbox de
    Claude): cada `allowWrite` va con `write` —el worktree, el `.git` del repo, la carpeta del
    archivo de la tarea, la de estado de Cotejo— más la carpeta propia del worktree dentro del
    `.git`, y cada `denyWrite` con `read`, que gana por ser más concreta o por venir después: los
    `hooks` y la `config` del `.git`, los demás worktrees y los archivos de la config de Cotejo.
    Hereda de `:workspace` (la carpeta donde arranca, y el resto se lee), pero niega `:slash_tmp`
    —el `/tmp` de la persona, donde no debe escribir ni dejar un `.git`— y la red queda solo para
    lo local, por el proxy de Codex. Todo por `-c`: el `~/.codex/config.toml` no se toca."""
    caja = ((caja or {}).get("sandbox") or {}).get("filesystem") or {}
    # `:slash_tmp` es el `/tmp` de la persona, y heredarlo de `:workspace` es lo que dejaba
    # `/tmp/.git` cuando Codex escribía ahí (cotejo-wwrzyf). El temporal del agente va a la
    # carpeta de estado (`armado.entorno` pone su TMPDIR), así que no se pierde nada.
    reglas = {":slash_tmp": "deny"}
    for ruta in caja.get("allowWrite") or ():
        reglas[os.path.abspath(str(ruta))] = "write"
    propio = _gitdir_de(trabajo)
    if propio:
        reglas[propio] = "write"
    for ruta in caja.get("denyWrite") or ():
        reglas[os.path.abspath(str(ruta))] = "read"

    def cadena(texto):   # cadena TOML básica
        return json.dumps(texto, ensure_ascii=False)

    def tabla(datos):
        return "{" + ",".join(f"{cadena(k)}={cadena(v)}" for k, v in datos.items()) + "}"

    perfil = ("{extends=\":workspace\",filesystem=" + tabla(reglas) +
              ",network={enabled=true,domains=" + tabla({d: "allow" for d in LOCALES_CODEX}) +
              "}}")
    return ["--enable", "network_proxy", "-c", f'default_permissions="{PERFIL_CODEX}"',
            "-c", f"permissions.{PERFIL_CODEX}={perfil}"]


# Donde OpenCode lee la config de un proyecto, desde la carpeta donde arranca
# (https://opencode.ai/docs/config/): el `opencode.json[c]` y el de `.opencode/`.
CONFIG_OPENCODE_DEL_PROYECTO = ("opencode.json", "opencode.jsonc", ".opencode/opencode.json",
                                ".opencode/opencode.jsonc")


def _opencode_sin_mcp_del_proyecto(trabajo, entorno):
    """El entorno de OpenCode con los servidores MCP del proyecto apagados: cada nombre que
    defina un `opencode.json[c]` del worktree (`mcp.<nombre>`) va con `enabled: false` en
    `OPENCODE_CONFIG_CONTENT`, que OpenCode funde por encima de la del proyecto. Los de la
    persona siguen, salvo uno que el proyecto redefina con el mismo nombre: ese ya no sería el
    suyo, y se apaga también. Se lee al lanzar, así que lo que se escriba a media sesión cuenta
    en el siguiente lanzamiento (OpenCode tampoco relee la config a media sesión).

    Si hay una config del proyecto que no se entiende, va `OPENCODE_DISABLE_PROJECT_CONFIG`:
    OpenCode no lee ninguna del proyecto (ni su `AGENTS.md`), mejor que dejar pasar lo que no
    se pudo mirar."""
    if not trabajo:
        return entorno
    nombres = []
    for relativa in CONFIG_OPENCODE_DEL_PROYECTO:
        archivo = os.path.join(trabajo, relativa)
        if not os.path.isfile(archivo):
            continue
        try:
            with open(archivo, encoding="utf-8") as f:
                datos = json.loads(_sin_comentarios_jsonc(f.read()))
            mcp = datos.get("mcp") if isinstance(datos, dict) else None
            nombres += list(mcp) if isinstance(mcp, dict) else []
        except (OSError, ValueError, UnicodeDecodeError):
            return {**entorno, "OPENCODE_DISABLE_PROJECT_CONFIG": "1"}
    if not nombres:
        return entorno
    datos = json.loads(entorno["OPENCODE_CONFIG_CONTENT"])
    mcp = datos.get("mcp") if isinstance(datos.get("mcp"), dict) else {}
    for nombre in dict.fromkeys(nombres):
        propio = mcp.get(nombre)
        mcp[nombre] = {**(propio if isinstance(propio, dict) else {}), "enabled": False}
    datos["mcp"] = mcp
    return {**entorno, "OPENCODE_CONFIG_CONTENT": json.dumps(datos, ensure_ascii=False)}


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


# --- los plugins de OpenCode y la config de Gemini CLI del proyecto (cotejo-lbwsq4) -------------

# Donde OpenCode busca código JavaScript/TypeScript del proyecto, que importa él mismo al
# arrancar —fuera de cualquier permiso, como un servidor MCP—: sus plugins
# (https://opencode.ai/docs/plugins/) y sus herramientas propias
# (https://opencode.ai/docs/custom-tools/). Con la carpeta en singular también los carga.
CODIGO_OPENCODE_DEL_PROYECTO = (".opencode/plugin", ".opencode/plugins", ".opencode/tool",
                                ".opencode/tools")


def _opencode_sin_plugins_del_proyecto(trabajo, entorno):
    """El entorno de OpenCode sin la config del proyecto si el worktree trae código que
    OpenCode cargaría solo: un archivo en sus carpetas de plugins o herramientas, o un `plugin`
    en un `opencode.json[c]` del proyecto (que OpenCode instala y carga al arrancar).

    No hay forma de apagar solo esos (`OPENCODE_CONFIG_CONTENT` añade plugins, no los quita):
    `OPENCODE_DISABLE_PROJECT_CONFIG` deja fuera toda la config del proyecto y su `AGENTS.md`
    (https://opencode.ai/docs/cli/, «Disable project configuration and project instruction
    files»), y los plugins de la persona —su carpeta y los de su `opencode.json`— siguen. Sin
    código del proyecto, nada cambia."""
    if not trabajo:
        return entorno
    codigo = any(os.path.isdir(os.path.join(trabajo, carpeta)) and
                 any(archivos for _, _, archivos in os.walk(os.path.join(trabajo, carpeta)))
                 for carpeta in CODIGO_OPENCODE_DEL_PROYECTO)
    for relativa in CONFIG_OPENCODE_DEL_PROYECTO:
        archivo = os.path.join(trabajo, relativa)
        if codigo or not os.path.isfile(archivo):
            continue
        try:
            with open(archivo, encoding="utf-8") as f:
                datos = json.loads(_sin_comentarios_jsonc(f.read()))
            codigo = bool(isinstance(datos, dict) and datos.get("plugin"))
        except (OSError, ValueError, UnicodeDecodeError):
            codigo = True
    return {**entorno, "OPENCODE_DISABLE_PROJECT_CONFIG": "1"} if codigo else entorno


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


def _gemini_corre_codigo(ajustes):
    """¿Traen estos ajustes del proyecto algo que Gemini corre solo y que ninguna bandera
    apaga? Los hooks (`hooks.<evento>`, que se suman a los de la persona y corren sin
    preguntar), los comandos de herramientas propias (`tools.discoveryCommand`, que corre al
    arrancar, y `tools.callCommand`) y las políticas que el proyecto se cargaría
    (`policyPaths`, `adminPolicyPaths`: las de administrador pesarían más que los prohibidos)."""
    hooks = ajustes.get("hooks")
    if isinstance(hooks, dict) and any(isinstance(v, list) and v for v in hooks.values()):
        return True
    herramientas = ajustes.get("tools")
    if isinstance(herramientas, dict) and (herramientas.get("discoveryCommand") or
                                           herramientas.get("callCommand")):
        return True
    return bool(ajustes.get("policyPaths") or ajustes.get("adminPolicyPaths"))


def _gemini_de_la_persona(entorno):
    """`(servidores, permitidos, excluidos)` de la config de Gemini de la persona: los nombres
    de sus servidores MCP (sus ajustes, los del sistema y los de sus extensiones) y sus listas
    `mcp.allowed` (`None` si no tiene) y `mcp.excluded`. Solo se leen nombres. Un archivo que no
    se entiende no suma nada: con él roto, Gemini tampoco arrancaría."""
    casa = entorno.get("GEMINI_CLI_HOME") or os.path.expanduser("~")
    sistema = entorno.get("GEMINI_CLI_SYSTEM_SETTINGS_PATH") or {
        "darwin": "/Library/Application Support/GeminiCli/settings.json",
        "win32": "C:\\ProgramData\\gemini-cli\\settings.json"}.get(
            sys.platform, "/etc/gemini-cli/settings.json")
    defectos = (entorno.get("GEMINI_CLI_SYSTEM_DEFAULTS_PATH") or
                os.path.join(os.path.dirname(sistema), "system-defaults.json"))
    servidores, permitidos, excluidos = [], None, set()
    for ruta in (defectos, os.path.join(casa, ".gemini", "settings.json"), sistema):
        try:
            ajustes = _gemini_ajustes(ruta)
        except ValueError:
            continue
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
