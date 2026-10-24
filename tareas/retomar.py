"""La nota de retomar (v1.3.0, cotejo-z7ma7r): lo que se le dice al agente nuevo de una tarea
que otro ya había empezado.

Devolver a mano una tarea de Haciendo a Pendiente en el board la **pausa**: su agente se para
(`despacho_board.detener`) pero el worktree, la rama y el modelo asignado se quedan. Pasarla otra
vez a Haciendo lanza un agente **nuevo** —nunca se mantiene vivo ni se resume el viejo— con el
encargo de siempre más esta nota pegada al final, armada sola y sin IA con tres cosas que ya
están en disco:

1. los commits de la rama desde que salió de su base (`git log base..HEAD`);
2. lo que hay sin commitear en el worktree (`git status --porcelain`);
3. las últimas líneas legibles del log del agente anterior (`lanzados.legible`), solo las de
   su lanzamiento (desde su `log_desde`).

Es corta a propósito: el agente nuevo tiene el worktree delante y lo que necesita es saber que
no empieza de cero y por dónde mirar, no un resumen. Sin GTK y sin importar el enrutador.

Para quien venga detrás (el fin y el rechazo de un agente, cotejo-o253bs): `datos(registro)`
reúne lo de arriba como dict, `armar(datos, motivo=...)` lo pasa a texto y `nota(registro,
motivo=...)` hace las dos cosas. `registro` es el de `lanzados.leer(id)` del lanzamiento
anterior, antes de que el nuevo lo pise.
"""

import subprocess
from pathlib import Path

from . import lanzados, worktrees

ULTIMAS = 8          # líneas del agente anterior
MAX_COMMITS = 15
MAX_CAMBIOS = 20
LINEA = 300          # cada línea del log, recortada
TIEMPO_GIT = 15

TITULO = "## Retomas esta tarea: no empiezas de cero"


def _git(carpeta, *args):
    """Las líneas de un git sin shell, o None si no se pudo. Sin `strip` del principio: en
    `status --porcelain` el espacio de delante es parte del código."""
    try:
        hecho = subprocess.run(["git", "-C", str(carpeta), *args], stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=TIEMPO_GIT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if hecho.returncode != 0:
        return None
    return [l for l in hecho.stdout.decode("utf-8", "replace").splitlines() if l.strip()]


def carpeta_de_trabajo(registro):
    """Dónde trabajó el agente anterior: su worktree si tenía, o la carpeta del proyecto."""
    worktree = (registro or {}).get("worktree") or {}
    for ruta in (worktree.get("ruta"), (registro or {}).get("trabajo")):
        if ruta and Path(ruta).is_dir():
            return Path(ruta)
    return None


def base_de(registro):
    """El commit del que salió la rama: el que guardó el primer lanzamiento, el del registro
    del worktree o, si no queda ninguno, donde se separa del repo."""
    registro = registro or {}
    if registro.get("base"):
        return registro["base"]
    de_wt = worktrees.de_tarea(registro.get("id", "")) if registro.get("id") else None
    if de_wt and de_wt.get("desde"):
        return de_wt["desde"]
    worktree = registro.get("worktree") or {}
    trabajo = carpeta_de_trabajo(registro)
    if worktree.get("repo") and trabajo:
        cabeza = _git(worktree["repo"], "rev-parse", "HEAD")
        if cabeza:
            separacion = _git(trabajo, "merge-base", "HEAD", cabeza[0])
            if separacion:
                return separacion[0]
    return None


def ultimas_lineas(registro, cuantas=ULTIMAS):
    """Las últimas `cuantas` líneas legibles del lanzamiento anterior, en orden."""
    registro = registro or {}
    try:
        with open(registro.get("log") or "", "rb") as archivo:
            archivo.seek(int(registro.get("log_desde") or 0))
            crudo = archivo.read()
    except (OSError, ValueError):
        return []
    lineas = []
    for linea in crudo.decode("utf-8", "replace").splitlines():
        texto = lanzados.legible(linea)
        if texto:
            lineas.extend(t[:LINEA] for t in texto.splitlines() if t.strip())
    return lineas[-cuantas:]


def datos(registro, cuantas=ULTIMAS):
    """Lo que dice la nota, sin pasarlo a texto: `commits` y `sin_commitear` (listas de
    líneas; None si no es un repo de git), `ultimas`, `rama`, `base` y `modelo`."""
    registro = registro or {}
    trabajo = carpeta_de_trabajo(registro)
    base = base_de(registro)
    commits = sin_commitear = None
    if trabajo is not None:
        sin_commitear = _git(trabajo, "status", "--porcelain", "--untracked-files=all")
        if base:
            commits = _git(trabajo, "log", "--oneline", "--no-decorate",
                           f"--max-count={MAX_COMMITS + 1}", f"{base}..HEAD")
    return {"rama": (registro.get("worktree") or {}).get("rama"), "base": base,
            "trabajo": str(trabajo) if trabajo else None, "modelo": registro.get("modelo"),
            "commits": commits, "sin_commitear": sin_commitear,
            "ultimas": ultimas_lineas(registro, cuantas)}


def _lista(lineas, maximo):
    salida = ["  " + l for l in lineas[:maximo]]
    if len(lineas) > maximo:
        salida.append(f"  … y {len(lineas) - maximo} más")
    return salida


def armar(d, motivo=""):
    """La nota en texto, corta, para pegar al final del encargo."""
    quien = d.get("modelo") or "otro agente"
    por = f": {motivo.strip()}" if motivo and motivo.strip() else "."
    partes = [TITULO, "",
              f"Otro agente ({quien}) ya trabajó en ella y se paró{por} Lo que hizo sigue "
              f"ahí. Estabas haciendo esto y quedaste en lo que sigue:"]
    rama = d.get("rama")
    if d.get("commits") is not None:
        partes += ["", f"Commits en {rama or 'la rama'} desde que salió de su base:"]
        partes += _lista(d["commits"], MAX_COMMITS) if d["commits"] else ["  (ninguno todavía)"]
    if d.get("sin_commitear") is not None:
        partes += ["", "Sin commitear en " + ("el worktree:" if rama else "la carpeta:")]
        partes += (_lista(d["sin_commitear"], MAX_CAMBIOS) if d["sin_commitear"]
                   else ["  (nada)"])
    if d.get("ultimas"):
        partes += ["", "Lo último que dijo el agente anterior:"]
        partes += ["  > " + l for l in d["ultimas"]]
    partes += ["", "Mira `git log` y `git diff` antes de rehacer nada, y sigue desde ahí: lo "
                   "que ya está bien no se vuelve a hacer."]
    return "\n".join(partes)


def nota(registro, motivo="", cuantas=ULTIMAS):
    """`armar(datos(registro))`: la nota de retomar del lanzamiento anterior."""
    return armar(datos(registro, cuantas), motivo=motivo)


def motivo_de(registro):
    """Por qué se paró el anterior: el de su `detenido`, o el que tenía antes de quedar en
    espera de hueco (`lanzados.poner_en_espera` lo guarda en `motivo_antes`)."""
    registro = registro or {}
    if registro.get("fase") == lanzados.DETENIDO:
        return registro.get("motivo") or ""
    return registro.get("motivo_antes") or ""


def es_retomable(registro):
    """¿Ya se lanzó alguna vez (hay un agente anterior del que retomar)?"""
    return bool(registro and registro.get("pid") and registro.get("log"))


def resumen(reanudacion):
    """Una frase para el detalle: «Es una reanudación (2.ª vez): 1 commit y 2 cambios…»."""
    if not reanudacion:
        return ""
    vez = reanudacion.get("vez") or 2
    trozos = []
    commits, cambios = reanudacion.get("commits"), reanudacion.get("sin_commitear")
    if commits is not None:
        trozos.append(f"{commits} commit" + ("s" if commits != 1 else ""))
    if cambios is not None:
        trozos.append(f"{cambios} cambio" + ("s" if cambios != 1 else "") + " sin commitear")
    de = f" de {reanudacion['anterior']}" if reanudacion.get("anterior") else ""
    lleva = f": sigue con {' y '.join(trozos)}" if trozos else ""
    return (f"Es una reanudación (vez {vez}): retoma lo que dejó el agente "
            f"anterior{de}{lleva}.")
