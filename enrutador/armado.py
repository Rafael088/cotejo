"""El armado del agente sin interfaz que lanza Cotejo: terminal libre con los prohibidos de
fábrica y, en Claude, su Bash en el sandbox (v1.3.0, cotejo-7yfw1e, cotejo-amui0f, cotejo-6a7np9).

Es lo que comparten el board (`despacho_board.py`) y `despachar --motor headless`
(`motores/claude_cli.py`): los mismos permisos para los cuatro clientes, armados por las mismas
funciones, sin una copia en cada sitio. Aquí no hay política nueva: solo se juntan
`clientes.Cliente.terminal_libre`, las guardas del PATH (`guardas.py`), el lanzador de `cotejo`
(`mismo_cotejo.py`) y el sandbox de Claude (`sandbox.py`).

El «preparar» del inicio de un proyecto (`preparar.py`) NO pasa por aquí: sigue con el permiso
de usar `cotejo` y nada más.
"""

from pathlib import Path

from tareas import worktrees
from . import clientes, guardas, mismo_cotejo, preparar, sandbox as caja

NOTA_TERMINAL = ("Tienes terminal libre en tu carpeta de trabajo: corre las pruebas y los "
                 "builds que haga falta. Están prohibidos y se rechazan solos: sudo/su, git "
                 "push --force, empujar a main o a la rama por defecto y borrar fuera de tu "
                 "carpeta (borra con rutas relativas, sin «..»).")
# Se añade a la nota cuando el Bash del agente va dentro del sandbox de Claude (cotejo-amui0f).
NOTA_SANDBOX = ("Tu terminal corre dentro de un sandbox: solo puedes escribir en tu carpeta de "
                "trabajo, el .git del repo y las carpetas de Cotejo, y la red solo llega a los "
                "remotos del repo. Si algo falla con «sistema de ficheros de solo lectura» o "
                "una conexión denegada, es a propósito: no intentes rodearlo; si te impide "
                "terminar, bloquea la tarea con el motivo.")


def ramas_protegidas(directorio, worktree=None):
    """`main` y la rama por defecto del repo de la tarea (la de su `origin`)."""
    repo = (worktree or {}).get("repo") or worktrees.raiz_repo(directorio)
    return clientes.ramas_protegidas(worktrees.rama_por_defecto(repo) if repo else None)


def carpetas_de_escritura(trabajo, worktree=None):
    """Las de preparar para la carpeta de trabajo (ella, la config de Cotejo y la de estado)
    más el `.git` del repo si trabaja en un worktree: ahí van sus commits."""
    lista = preparar.carpetas_de_escritura(trabajo)
    if worktree:
        git = Path(worktree["repo"]) / ".git"
        if git.is_dir():
            lista.append(str(git))
    return list(dict.fromkeys(lista))


def sandbox_de(config, cliente, cotejo, tarea_id, trabajo, worktree=None, directorio=None):
    """El sandbox del agente de esta tarea (cotejo-amui0f): `{"activo", "motivo", "ajustes",
    "entorno", "avisos"}`. Solo Claude Code lo lleva (Codex trae el suyo; OpenCode y Gemini no
    tienen); sin él disponible en la máquina, o con `lanzar.sandbox: false`, va apagado con el
    motivo y el agente trabaja con los prohibidos de siempre (`sandbox.py`)."""
    apagado = {"activo": False, "motivo": "", "ajustes": None, "entorno": {}, "avisos": []}
    if cliente.nombre != "claude":
        return {**apagado, "motivo": f"{cliente.titulo or cliente.nombre} no usa el de Claude"}
    ajustes = (config.get("lanzar") or {}).get("sandbox")
    if ajustes is False:
        return {**apagado, "motivo": "apagado en la config (lanzar.sandbox)"}
    hay, motivo = caja.disponible()
    if not hay:
        return {**apagado, "motivo": motivo}
    repo = (worktree or {}).get("repo") or (worktrees.raiz_repo(directorio) if directorio
                                            else None)
    hecho = caja.del_lanzamiento(
        carpetas_de_escritura(trabajo, worktree), repo=repo,
        propio=(worktree or {}).get("ruta"), carpeta_tarea=cotejo.carpeta_de_la_tarea(tarea_id),
        ajustes=ajustes)
    return {"activo": True, "motivo": "", **hecho}


def comando(config, cliente, modelo, modelo_id, prompt, carpetas, ramas=None,
            politica_gemini=None, sandbox=None):
    """El argv sin interfaz: el del motor `headless` para ese cliente, más
    `lanzar.argumentos_extra.<cliente>` y la terminal libre en `carpetas` con los prohibidos
    de fábrica para `ramas` (`clientes.Cliente.terminal_libre`), con el sandbox de Claude si
    viene (`sandbox`, los ajustes de `sandbox_de`). Los permisos no viven en la config: así una
    config propia no se los lleva por delante."""
    propios = preparar._propios(config, cliente)
    extra = (list(propios.get("argumentos_extra") or ()) +
             list(((config.get("lanzar") or {}).get("argumentos_extra") or {})
                  .get(cliente.nombre) or ()) +
             cliente.terminal_libre(carpetas, ramas, politica_gemini, sandbox=sandbox)[0])
    return cliente.argv_sin_interfaz(
        cliente.modelo_de(modelo, modelo_id), prompt,
        comando=propios.get("comando"), extra=extra)


def entorno(cliente, carpetas, ramas, encerrado):
    """El entorno del agente: las variables de su terminal libre y las del sandbox, con las
    guardas primeras en el PATH (las escribe) y el lanzador de `cotejo` delante."""
    con_guardas = guardas.entorno(
        {**cliente.terminal_libre(carpetas, ramas)[1], **encerrado["entorno"]}, ramas)
    return mismo_cotejo.entorno(con_guardas, base=con_guardas)


def nota(encerrado):
    """Lo que se le dice al agente de su terminal, y de su sandbox si lo lleva."""
    return NOTA_TERMINAL + (" " + NOTA_SANDBOX if encerrado["activo"] else "")
