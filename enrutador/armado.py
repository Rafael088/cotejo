"""El armado del agente sin interfaz que lanza Cotejo: terminal libre con los prohibidos de
fábrica y, en Claude, su Bash en el sandbox (v1.3.0, cotejo-7yfw1e, cotejo-amui0f, cotejo-6a7np9).

Es lo que comparten el board (`despacho_board.py`) y `despachar --motor headless`
(`motores/claude_cli.py`): los mismos permisos para los cuatro clientes, armados por las mismas
funciones, sin una copia en cada sitio. Aquí no hay política nueva: solo se juntan
`clientes.Cliente.terminal_libre`, las guardas del PATH (`guardas.py`), el lanzador de `cotejo`
(`mismo_cotejo.py`) y el sandbox de Claude (`sandbox.py`).

El «preparar» del inicio de un proyecto (`preparar.py`) NO pasa por aquí: sigue con el permiso
de usar `cotejo` y nada más.

**La config de Cotejo queda fuera de su alcance** (cotejo-dgb7l2): ahí viven `lanzar.sandbox` y
`lanzar.argumentos_extra`, y el agente que la escribiera se los quitaría a los lanzamientos
siguientes. Ningún verbo que use durante una tarea la escribe (eso es de `init`, en preparar),
así que su carpeta no está entre las suyas (`carpetas_de_escritura`, para los cuatro clientes);
el sandbox de Claude veda además los archivos (`vedados`) aunque una carpeta que sí le toca los
contenga, y sus herramientas de editar también; y su entorno lleva `COTEJO_CONFIG_VEDADA`, con
la que el propio `cotejo` se niega a escribirla (`configuracion.sin_vedar`).
"""

import os
from pathlib import Path

from tareas import configuracion, rutas, worktrees
from . import clientes, guardas, mismo_cotejo, navegador, preparar, sandbox as caja

NOTA_TERMINAL = ("Tienes terminal libre en tu carpeta de trabajo: corre las pruebas y los "
                 "builds que haga falta. Están prohibidos y se rechazan solos: sudo/su, git "
                 "push --force, empujar a main o a la rama por defecto y borrar fuera de tu "
                 "carpeta (borra con rutas relativas, sin «..»).")
# Cómo ve el agente una página que hizo, dentro del sandbox (cotejo-xrmr3h, `navegador.py`).
NOTA_NAVEGADOR = ("Para ver una página (y sacarle captura) usa Firefox sin interfaz: "
                  f"`{navegador.COMO_CAPTURAR}`; en el repo de Cotejo, también "
                  "`python3 -m enrutador.navegador <archivo|url> captura.png`. Chromium no "
                  "arranca en el sandbox. Si sirves la página con un servidor local, arráncalo "
                  "en el mismo comando que el navegador: cada comando va en su sandbox.")
# Se añade a la nota cuando el Bash del agente va dentro del sandbox de Claude (cotejo-amui0f).
SANDBOX_BASE = ("Tu terminal corre dentro de un sandbox: solo puedes escribir en tu carpeta de "
                "trabajo, el .git del repo y la carpeta de estado de Cotejo (su config no), y la red solo llega a los "
                "remotos del repo. Si algo falla con «sistema de ficheros de solo lectura» o "
                "una conexión denegada, es a propósito: no intentes rodearlo; si te impide "
                "terminar, bloquea la tarea con el motivo. ")
NOTA_SANDBOX = SANDBOX_BASE + NOTA_NAVEGADOR
NOTA_SANDBOX_ANTIGRAVITY = (
    "Antigravity corre entero dentro de la jaula de Cotejo: solo puedes escribir en tu carpeta "
    "de trabajo, el .git del repo, la carpeta de la tarea y el estado de Cotejo (su config no); "
    "el resto se lee. La red sigue disponible para el CLI. No intentes rodear la jaula; si te "
    "impide terminar, bloquea la tarea con el motivo.")
# Codex con su perfil de permisos (cotejo-srkywv, `clientes._codex_perfil`): escribe donde Claude
# y commitea, pero no tiene más red que la local, y esa pasa por el proxy de Codex.
SANDBOX_CODEX = ("Tu terminal corre dentro del sandbox de Codex: solo puedes escribir en tu "
                 "carpeta de trabajo, el .git del repo (haz ahí tus commits; sus hooks y su "
                 "config no), la carpeta del archivo de la tarea y la de estado de Cotejo (su "
                 "config no). No hay red fuera de esta máquina: no puedes empujar la rama ni "
                 "instalar nada (déjala commiteada; la empuja quien revisa). Si algo falla con "
                 "«sistema de ficheros de solo lectura» o una conexión denegada, es a propósito: "
                 "no intentes rodearlo; si te impide terminar, bloquea la tarea con el motivo. ")
NOTA_SANDBOX_CODEX = (SANDBOX_CODEX + NOTA_NAVEGADOR + " Para probar tu servidor con curl, "
                      "sáltate el proxy: `curl --noproxy '*' http://127.0.0.1:<puerto>`.")
# Sin Firefox no se da un comando que va a fallar (cotejo-0e17vu): se dice y se pide avisar.
SIN_NAVEGADOR = ("En esta máquina no hay un navegador sin interfaz para ver tu trabajo: no "
                 "podrás sacarle capturas. Dilo en la entrega y propón a la persona instalar "
                 "Firefox.")
NOTA_SIN_NAVEGADOR = SANDBOX_BASE + SIN_NAVEGADOR


def nota_sandbox(disponible=None):
    """La nota del sandbox que vale ahora: con la línea de captura si hay navegador, y si no,
    la que avisa. `disponible` (para las pruebas) es lo que contesta la detección."""
    hay = navegador.disponible_para_el_agente() if disponible is None else disponible
    return NOTA_SANDBOX if hay else NOTA_SIN_NAVEGADOR


def ramas_protegidas(directorio, worktree=None):
    """`main` y la rama por defecto del repo de la tarea (la de su `origin`)."""
    repo = (worktree or {}).get("repo") or worktrees.raiz_repo(directorio)
    return clientes.ramas_protegidas(worktrees.rama_por_defecto(repo) if repo else None)


def carpetas_de_escritura(trabajo, worktree=None):
    """Las de preparar para la carpeta de trabajo (ella y la de estado de Cotejo, **sin** la de
    su config: cotejo-dgb7l2) más el `.git` del repo si trabaja en un worktree: ahí van sus
    commits. En macOS la de estado cuelga de la de config, y se da solo la de estado."""
    config = os.path.abspath(Path(configuracion.ruta()).expanduser().parent)
    lista = [c for c in preparar.carpetas_de_escritura(trabajo) if c != config]
    if worktree:
        git = Path(worktree["repo"]) / ".git"
        if git.is_dir():
            lista.append(str(git))
    return list(dict.fromkeys(lista))


def vedados():
    """Los archivos que el agente no escribe aunque caigan dentro de lo suyo: los de la config
    de Cotejo. (Un archivo vedado que no existe no lo para el sandbox de Claude; por eso lo
    primero es que su carpeta no sea de las del agente.)"""
    return configuracion.archivos()


def sandbox_de(config, cliente, cotejo, tarea_id, trabajo, worktree=None, directorio=None):
    """El sandbox del agente de esta tarea: el de Claude, la jaula propia de Antigravity o las
    carpetas del perfil de permisos de Codex (`clientes._codex_perfil`, cotejo-srkywv).

    Claude conserva el comportamiento anterior si el suyo falta. Antigravity, en cambio, no se
    lanza sin jaula: `--dangerously-skip-permissions` sin contención dejaría escribir en toda la
    máquina (cotejo-b1iwpj). Aquí se anota el motivo y `comando`/`comprobar` impiden el lanzamiento.
    """
    apagado = {"activo": False, "motivo": "", "ajustes": None, "entorno": {}, "avisos": []}
    ajustes = (config.get("lanzar") or {}).get("sandbox")
    if cliente.nombre == "codex" and os.name != "nt":
        # Codex lleva siempre su sandbox; aquí solo se le dan las carpetas de Claude para su
        # perfil de permisos (cotejo-srkywv). `lanzar.sandbox: false` apaga el de Claude, no
        # el de Codex: sin perfil volvería a no poder commitear. Sin token: no tiene red.
        return {"activo": True, "motivo": "", "cliente": "codex",
                **_del_lanzamiento(cotejo, tarea_id, trabajo, worktree, directorio,
                                   ajustes if isinstance(ajustes, dict) else None, token=None)}
    if cliente.nombre not in ("claude", "antigravity"):
        return {**apagado, "motivo": f"{cliente.titulo or cliente.nombre} no usa el de Claude"}
    if ajustes is False:
        return {**apagado, "motivo": "apagado en la config (lanzar.sandbox)"}
    hay, motivo = caja.disponible() if cliente.nombre == "claude" else caja.disponible_bwrap()
    if not hay:
        return {**apagado, "motivo": motivo}
    hecho = _del_lanzamiento(cotejo, tarea_id, trabajo, worktree, directorio, ajustes)
    return {"activo": True, "motivo": "", "cliente": cliente.nombre, **hecho}


def _del_lanzamiento(cotejo, tarea_id, trabajo, worktree, directorio, ajustes, **mas):
    """`sandbox.del_lanzamiento` con las carpetas de esta tarea."""
    repo = (worktree or {}).get("repo") or (worktrees.raiz_repo(directorio) if directorio
                                            else None)
    return caja.del_lanzamiento(
        carpetas_de_escritura(trabajo, worktree), repo=repo,
        propio=(worktree or {}).get("ruta"), carpeta_tarea=cotejo.carpeta_de_la_tarea(tarea_id),
        ajustes=ajustes, vedadas=vedados(), **mas)


def comando(config, cliente, modelo, modelo_id, prompt, carpetas, ramas=None,
            politica_gemini=None, sandbox=None, argumentos=()):
    """El argv sin interfaz: el del motor `headless` para ese cliente, más
    `lanzar.argumentos_extra.<cliente>` y la terminal libre en `carpetas` con los prohibidos
    de fábrica para `ramas` (`clientes.Cliente.terminal_libre`), con el sandbox de Claude si
    viene (`sandbox`, los ajustes de `sandbox_de`). Los permisos no viven en la config: así una
    config propia no se los lleva por delante."""
    propios = preparar._propios(config, cliente)
    extra = (list(argumentos or ()) + list(propios.get("argumentos_extra") or ()) +
             list(((config.get("lanzar") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ()) +
             cliente.terminal_libre(carpetas, ramas, politica_gemini, sandbox=sandbox,
                                    vedados=vedados())[0])
    argv = cliente.argv_sin_interfaz(
        cliente.modelo_de(modelo, modelo_id), prompt,
        comando=propios.get("comando"), extra=extra)
    if cliente.nombre == "antigravity":
        if not sandbox:
            raise caja.SandboxNoDisponible(
                "Antigravity CLI no se lanzó: la jaula de Cotejo no está disponible. Instala "
                "bubblewrap y comprueba que puede crear espacios de nombres; no se lanzará "
                "sin protección.")
        return caja.envolver_antigravity(argv, sandbox, carpetas[0])
    return argv


def entorno(cliente, carpetas, ramas, encerrado):
    """El entorno del agente: las variables de su terminal libre y las del sandbox, con las
    guardas primeras en el PATH (las escribe), el lanzador de `cotejo` delante y la marca con
    la que `cotejo` no le escribe la config."""
    base = {**cliente.terminal_libre(carpetas, ramas)[1], **encerrado["entorno"],
            configuracion.VEDADA: "1"}
    if cliente.nombre == "codex":
        # Su perfil niega `:slash_tmp` (cotejo-wwrzyf), así que el temporal va a la carpeta de
        # estado, que ya está entre las suyas: builds y Firefox siguen teniendo su TMPDIR.
        temporal = rutas.estado() / "agente" / "tmp"
        try:
            temporal.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        base["TMPDIR"] = str(temporal)
    con_guardas = guardas.entorno(base, ramas)
    return mismo_cotejo.entorno(con_guardas, base=con_guardas)


def nota_jaula(encerrado):
    """La parte del encargo que explica la jaula que de verdad lleva este agente."""
    if encerrado.get("cliente") == "antigravity":
        return NOTA_SANDBOX_ANTIGRAVITY
    if encerrado.get("cliente") == "codex":
        return nota_codex()
    return nota_sandbox()


def nota_codex(disponible=None):
    """La nota de Codex con su perfil: con la línea de captura si hay Firefox (con la red
    local del perfil arranca en su sandbox; Chromium no), y si no, la que avisa."""
    hay = navegador.disponible_para_el_agente() if disponible is None else disponible
    return NOTA_SANDBOX_CODEX if hay else SANDBOX_CODEX + SIN_NAVEGADOR


def nota(encerrado):
    """Lo que se le dice al agente de su terminal, y de su sandbox si lo lleva."""
    return NOTA_TERMINAL + (" " + nota_jaula(encerrado) if encerrado["activo"] else "")
