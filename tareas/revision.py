"""La vista de revisión (B4, v1.1): lo que el board enseña de una entrega y lo que hace al aprobarla.

Aquí está toda la lógica, sin GTK: qué dice la carta de *Para comprobar* a partir de la
evidencia estructurada (pruebas en verde o en rojo, diff resumido, commits), cómo se parte un
diff unificado en archivos y líneas para pintarlo, cómo se vuelven a correr las pruebas
(`comprobar` de la CLI y el botón del board son la misma función) y qué pasa al aprobar:
**ofrecer** integrar la rama de la tarea, nunca integrarla sin preguntar. El board solo pinta
lo que devuelve esto, y por eso se puede probar entero sin pantalla.

La CLI no gana ningún verbo con esto: finalizar e integrar siguen siendo de una persona, en el
board (`test_no_hay_ningun_verbo_para_finalizar_una_tarea`).

No importa GTK, como el resto del núcleo.
"""

import os
import subprocess
from pathlib import Path

from . import evidencia, worktrees

TIEMPO_GIT = 60

# Cuántas líneas de un archivo se pintan en el board. Un `Gtk.Label` por línea aguanta unos
# cientos; para un diff más grande está «Abrir en herramienta», que es para lo que existe.
LINEAS_MAX = 400


def _git(carpeta, *args, tiempo=TIEMPO_GIT):
    """(código, salida, error) de un git sin shell ni entrada. Código None si no llegó a correr."""
    try:
        hecho = subprocess.run(["git", "-C", str(carpeta), *args], stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=tiempo)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, "", str(error)
    return (hecho.returncode, hecho.stdout.decode("utf-8", "replace").rstrip("\n"),
            hecho.stderr.decode("utf-8", "replace").strip())


# --- qué enseña la carta -------------------------------------------------------------------

def estado_prueba(codigo):
    """«verde» (código 0), «rojo» (otro código) o «sin-terminar» (no llegó a terminar: None)."""
    if codigo is None:
        return "sin-terminar"
    return "verde" if codigo == 0 else "rojo"


def _plural(numero, uno, varios):
    return f"{numero} {uno if numero == 1 else varios}"


def frase_pruebas(entrega):
    """Una frase llana sobre las pruebas que dejó el agente, sin su salida: de aquí a la vista."""
    pruebas = (entrega or {}).get("pruebas") or []
    if not pruebas:
        return "El agente no dejó pruebas que repetir."
    fallaron = sum(1 for p in pruebas if estado_prueba(p.get("codigo")) != "verde")
    if fallaron:
        return f"{fallaron} de {len(pruebas)} pruebas fallaron."
    if len(pruebas) == 1:
        return "La prueba que dejó el agente pasó."
    return f"Las {len(pruebas)} pruebas que dejó el agente pasaron."


def resumen(entrega):
    """Lo que la carta enseña de una entrega, o None si no trae evidencia estructurada.

    Una entrega de antes de B1 (o de una tarea que no es de código y se entregó sin
    `--prueba`) solo tiene el texto libre: esa carta se queda como estaba.
    """
    if not entrega or entrega.get("operacion", "entregar") != "entregar":
        return None
    git = entrega.get("git") or {}
    pruebas = entrega.get("pruebas") or []
    if not git and not pruebas:
        return None
    datos = {"rama": git.get("rama"), "head": git.get("head"), "desde": git.get("desde"),
             "sin_commitear": bool(git.get("sin_commitear"))}

    if pruebas:
        estados = [estado_prueba(p.get("codigo")) for p in pruebas]
        verdes = estados.count("verde")
        estado = "verde" if verdes == len(estados) else "rojo"
        datos["pruebas"] = {"estado": estado, "verdes": verdes, "total": len(estados),
                            "texto": (f"{verdes}/{len(estados)} en verde" if estado == "verde"
                                      else f"{len(estados) - verdes}/{len(estados)} en rojo")}
    else:
        datos["pruebas"] = None

    diff = git.get("diff")
    if diff and diff.get("archivos") is not None:
        mas, menos = diff.get("mas", 0), diff.get("menos", 0)
        total = mas + menos
        archivos = [{"ruta": a["ruta"], "mas": a.get("mas"), "menos": a.get("menos"),
                     "binario": a.get("mas") is None and a.get("menos") is None}
                    for a in diff["archivos"]]
        mayor = max([(a["mas"] or 0) + (a["menos"] or 0) for a in archivos] or [0])
        for archivo in archivos:
            cambio = (archivo["mas"] or 0) + (archivo["menos"] or 0)
            # La barra de cada archivo es proporcional al que más cambió: así el más grande
            # llena su barra y los demás se comparan con él de un vistazo.
            archivo["proporcion"] = cambio / mayor if mayor else 0.0
            archivo["proporcion_mas"] = (archivo["mas"] or 0) / cambio if cambio else 0.0
        datos["diff"] = {"mas": mas, "menos": menos, "archivos": archivos,
                         "proporcion_mas": mas / total if total else 0.0,
                         "texto": f"+{mas} −{menos} · {_plural(len(archivos), 'archivo', 'archivos')}"}
    else:
        datos["diff"] = None

    commits = git.get("commits") or []
    datos["commits"] = [{"hash": c.get("hash", ""), "corto": c.get("hash", "")[:7],
                         "asunto": c.get("asunto", "")} for c in commits]
    datos["commits_texto"] = _plural(len(commits), "commit", "commits") if git else ""
    return datos


def texto_comprobacion(comprobacion):
    """La línea que deja en la carta el botón «Volver a comprobar», o "" si no se pulsó."""
    if not comprobacion:
        return ""
    if comprobacion.get("corriendo"):
        return "Comprobando…"
    if comprobacion.get("sigue_igual") is None:
        return comprobacion.get("salida") or "No hay pruebas que volver a correr"
    pruebas = comprobacion.get("pruebas") or []
    rojas = sum(1 for p in pruebas if estado_prueba(p.get("ahora")) != "verde")
    ahora = "todo en verde" if not rojas else _plural(rojas, "en rojo", "en rojo")
    return ("Sigue igual: " if comprobacion["sigue_igual"] else "Cambió: ") + ahora


# --- volver a comprobar --------------------------------------------------------------------

def recomprobar(entrega, propio=None):
    """Vuelve a correr las pruebas de una entrega: `{sigue_igual, pruebas, salida?}`.

    Es lo que hace `cotejo comprobar` y el botón del board. No toca ni el estado de la tarea ni
    la bitácora. `propio` es la carpeta del worktree de la tarea, si la tiene: se corren ahí,
    que es donde está su rama, aunque se entregara desde otra carpeta.
    """
    if entrega is None:
        return {"pruebas": [], "sigue_igual": None,
                "salida": "Esta tarea nunca se entregó: no hay pruebas que comprobar."}
    anteriores = entrega.get("pruebas") or []
    if not anteriores:
        return {"pruebas": [], "sigue_igual": None,
                "salida": "La entrega no registró ninguna prueba (se entregó sin --prueba)."}
    resultados = []
    for anterior in anteriores:
        carpeta = propio or anterior["carpeta"]
        ahora = evidencia.correr_prueba(anterior["comando"], carpeta)
        resultado = {"comando": anterior["comando"], "carpeta": carpeta,
                     "antes": anterior["codigo"], "ahora": ahora["codigo"],
                     "igual": ahora["codigo"] == anterior["codigo"],
                     "salida": ahora["salida"], "segundos": ahora["segundos"]}
        if "error" in ahora:
            resultado["error"] = ahora["error"]
        if carpeta != anterior["carpeta"]:
            resultado["carpeta_entrega"] = anterior["carpeta"]
        resultados.append(resultado)
    return {"sigue_igual": all(r["igual"] for r in resultados), "pruebas": resultados}


# --- el diff -------------------------------------------------------------------------------

def partir_diff(texto):
    """Un `git diff` unificado, partido por archivo: `[{ruta, lineas: [(tipo, texto)], binario}]`.

    `tipo` es «hunk» (`@@ … @@`), «mas», «menos» o «contexto»; lo que va antes del primer
    hunk de cada archivo (index, ---, +++, modos) no se enseña, porque la ruta ya lo dice.
    """
    archivos = []
    actual = None
    for linea in texto.splitlines():
        if linea.startswith("diff --git "):
            actual = {"ruta": _ruta_de_cabecera(linea), "lineas": [], "binario": False}
            archivos.append(actual)
            continue
        if actual is None:
            continue
        if not actual["lineas"]:
            # Todavía en la cabecera del archivo: hasta el primer hunk.
            if linea.startswith("+++ "):
                destino = linea[4:]
                if destino != "/dev/null":
                    actual["ruta"] = destino[2:] if destino.startswith("b/") else destino
                continue
            if linea.startswith("rename to "):
                actual["ruta"] = linea[len("rename to "):]
                continue
            if linea.startswith("Binary files ") or linea == "GIT binary patch":
                actual["binario"] = True
                continue
            if not linea.startswith("@@"):
                continue
        if linea.startswith("@@"):
            actual["lineas"].append(("hunk", linea))
        elif linea.startswith("+"):
            actual["lineas"].append(("mas", linea[1:]))
        elif linea.startswith("-"):
            actual["lineas"].append(("menos", linea[1:]))
        elif linea.startswith("\\"):
            continue  # «\ No newline at end of file»
        else:
            actual["lineas"].append(("contexto", linea[1:] if linea.startswith(" ") else linea))
    return archivos


def _ruta_de_cabecera(linea):
    """La ruta de `diff --git a/x b/x`. Con espacios en el nombre es ambigua; la afina `+++`."""
    resto = linea[len("diff --git "):]
    mitad = resto.rfind(" b/")
    return resto[mitad + 3:] if mitad >= 0 else resto


def diff(carpeta, desde, hasta):
    """El diff de la entrega, partido por archivo, o None si git no lo puede dar.

    Se pide entre los dos commits que anotó la entrega, no contra la rama de ahora: lo que se
    revisa es lo que se entregó, aunque la rama haya avanzado después.
    """
    if not carpeta or not desde or not hasta:
        return None
    codigo, salida, _ = _git(carpeta, "-c", "core.quotepath=false", "diff", "--no-color",
                             "--no-ext-diff", "-M", desde, hasta)
    if codigo != 0:
        return None
    return partir_diff(salida)


def recortar(lineas, maximo=LINEAS_MAX):
    """(las que se pintan, cuántas quedan fuera)."""
    return lineas[:maximo], max(0, len(lineas) - maximo)


def carpeta_git(tarea_id, entrega):
    """Dónde preguntarle a git por la entrega: su worktree, la carpeta anotada o su repo."""
    propio = worktrees.carpeta_de(tarea_id)
    if propio:
        return propio
    anotada = ((entrega or {}).get("git") or {}).get("repo")
    if anotada and Path(anotada).is_dir():
        return anotada
    registrado = worktrees.de_tarea(tarea_id)
    if registrado and Path(registrado.get("repo", "")).is_dir():
        return registrado["repo"]
    return None


# --- abrir en la herramienta de la persona -------------------------------------------------

def herramienta(carpeta):
    """La herramienta de diff que tiene configurada la persona en git, o None."""
    for clave in ("diff.guitool", "diff.tool", "merge.tool"):
        codigo, salida, _ = _git(carpeta, "config", "--get", clave)
        if codigo == 0 and salida.strip():
            return salida.strip()
    return None


def argv_difftool(carpeta, desde, hasta):
    """El `git difftool` que abre la entrega entera en la herramienta de la persona."""
    return ["git", "-C", str(carpeta), "difftool", "--dir-diff", "--no-prompt", desde, hasta]


def _lanzar(argv):
    """Lanza sin esperar y sin atarlo al board: cerrar la ventana no cierra la herramienta."""
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
                     **({"start_new_session": True} if os.name != "nt" else {}))


def abrir_en_herramienta(carpeta, desde, hasta):
    """Lanza `git difftool` sin esperar. `{abierto: bool, motivo?, herramienta?}`."""
    if not carpeta or not desde or not hasta:
        return {"abierto": False, "motivo": "La entrega no anotó sus commits: no hay diff que abrir"}
    nombre = herramienta(carpeta)
    if nombre is None:
        return {"abierto": False,
                "motivo": "Git no tiene herramienta de diff: git config --global diff.tool meld"}
    try:
        _lanzar(argv_difftool(carpeta, desde, hasta))
    except OSError as error:
        return {"abierto": False, "motivo": f"No pude lanzar git difftool: {error}"}
    return {"abierto": True, "herramienta": nombre}


# --- aprobar: ofrecer integrar -------------------------------------------------------------

def _repo_principal(carpeta):
    """El repo del que cuelga un worktree (o el propio repo), a partir de su `--git-common-dir`."""
    codigo, comun, _ = _git(carpeta, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if codigo != 0 or not comun:
        return None
    comun = Path(comun)
    if comun.name == ".git":
        return comun.parent
    codigo, raiz, _ = _git(carpeta, "rev-parse", "--show-toplevel")
    return Path(raiz) if codigo == 0 and raiz else None


def plan_integracion(tarea_id, entrega):
    """Qué ofrecer al aprobar: `{ofrecer, repo, rama, destino, motivo?, aviso?}`.

    Se calcula **antes** de dar la tarea por buena, porque aprobarla retira su worktree (B3) y
    con él el registro que dice de qué repo es. `ofrecer` es False cuando no hay nada que
    integrar (no es de código, no tiene rama, ya está integrada) o cuando integrar ahora
    pisaría algo (el repo tiene cambios sin commitear o está en mitad de otra cosa); `motivo`
    dice cuál, para avisarlo en vez de callarlo.
    """
    git = (entrega or {}).get("git") or {}
    registrado = worktrees.de_tarea(tarea_id) or {}
    rama = git.get("rama") or registrado.get("rama")
    plan = {"ofrecer": False, "rama": rama}
    if not rama:
        return {**plan, "motivo": "La entrega no está en ninguna rama"}

    repo = None
    if registrado.get("repo") and Path(registrado["repo"]).is_dir():
        repo = Path(registrado["repo"])
    else:
        for carpeta in (registrado.get("ruta"), git.get("repo")):
            if carpeta and Path(carpeta).is_dir():
                repo = _repo_principal(carpeta)
                if repo:
                    break
    if repo is None:
        return {**plan, "motivo": "No encuentro el repo de la tarea"}
    plan["repo"] = str(repo)

    codigo, destino, _ = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    if codigo != 0 or not destino:
        return {**plan, "motivo": f"{repo} no está en ninguna rama: no sé dónde integrarla"}
    plan["destino"] = destino
    if destino == rama:
        return {**plan, "motivo": f"Se trabajó directamente en {rama}: no hay nada que integrar"}
    codigo, punta, _ = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{rama}")
    if codigo != 0:
        return {**plan, "motivo": f"La rama {rama} ya no existe en {repo}"}
    codigo, _, _ = _git(repo, "merge-base", "--is-ancestor", punta, "HEAD")
    if codigo == 0:
        return {**plan, "motivo": f"{rama} ya está integrada en {destino}"}
    codigo, sucio, _ = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if codigo != 0:
        return {**plan, "motivo": f"No pude preguntarle a git por {repo}"}
    if sucio:
        return {**plan, "motivo": f"{repo} tiene cambios sin commitear: intégrala a mano"}
    for marca in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD"):
        codigo, _, _ = _git(repo, "rev-parse", "--verify", "--quiet", marca)
        if codigo == 0:
            return {**plan, "motivo": f"{repo} está en mitad de otra operación de git"}
    plan["ofrecer"] = True
    plan["punta"] = punta
    if git.get("head") and git["head"] != punta:
        plan["aviso"] = f"{rama} avanzó desde la entrega: se integraría también lo que vino después"
    return plan


def integrar(plan):
    """Integra la rama del plan en su destino con un merge (`--no-ff`). `{integrada, ...}`.

    Solo se llama cuando la persona dijo que sí. Si hay conflicto, el merge se aborta y el repo
    queda como estaba: integrar a medias es peor que no integrar. La rama no se borra nunca.
    """
    if not plan or not plan.get("ofrecer"):
        return {"integrada": False, "motivo": (plan or {}).get("motivo", "No hay nada que integrar")}
    repo, rama, destino = plan["repo"], plan["rama"], plan["destino"]
    # Lo que se vio al aprobar tiene que seguir siendo verdad al confirmar: el diálogo pudo
    # quedarse abierto un rato.
    codigo, actual, _ = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    if codigo != 0 or actual != destino:
        return {"integrada": False, "motivo": f"{repo} ya no está en {destino}; no integré nada"}
    codigo, sucio, _ = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if codigo != 0 or sucio:
        return {"integrada": False, "motivo": f"{repo} tiene cambios sin commitear; no integré nada"}
    codigo, _, error = _git(repo, "merge", "--no-ff", "--no-edit", rama, tiempo=300)
    if codigo != 0:
        _git(repo, "merge", "--abort")
        return {"integrada": False,
                "motivo": f"git no pudo integrar {rama} en {destino} ({error or 'conflicto'}); "
                          "lo dejé como estaba"}
    _, cabeza, _ = _git(repo, "rev-parse", "HEAD")
    return {"integrada": True, "repo": repo, "rama": rama, "destino": destino, "commit": cabeza}
