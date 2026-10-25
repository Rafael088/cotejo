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

`datos(registro)` reúne lo de arriba como dict, `armar(datos, motivo=...)` lo pasa a texto y
`nota(registro, motivo=...)` hace las dos cosas. `registro` es el de `lanzados.leer(id)` del
lanzamiento anterior, antes de que el nuevo lo pise.

**El rechazo** (cotejo-o253bs): devolver una entrega de Para comprobar a Haciendo con motivo
guarda en el registro `rechazo` (`rechazo(motivo, entrega)`: el motivo y la entrega anterior en
llano) y el agente nuevo recibe, después de la nota de retomar, «Lo que te pidieron cambiar»
(`armar_rechazo`). Vale hasta que vuelva a entregar (`rechazo_vigente`): si se pausa antes,
el siguiente también lo lleva.
"""

import subprocess
import time
from pathlib import Path

from . import lanzados, worktrees

ULTIMAS = 8          # líneas del agente anterior
MAX_COMMITS = 15
MAX_CAMBIOS = 20
LINEA = 300          # cada línea del log, recortada
TIEMPO_GIT = 15

TITULO = "## Retomas esta tarea: no empiezas de cero"
TITULO_RECHAZO = "## Lo que te pidieron cambiar"
# Por qué se paró el anterior cuando vuelve desde Para comprobar (el motivo va aparte, entero).
POR_RECHAZO = "entregó y se la devolvieron desde Para comprobar"


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


# --- el rechazo (cotejo-o253bs) ---------------------------------------------------------------

def entrega_en_llano(entrega):
    """Lo que dejó la entrega anterior, en pocas líneas: su resumen, su evidencia, el commit y
    cómo salieron las pruebas. `entrega` es la anotación de `bitacora.ultima_entrega`."""
    if not entrega:
        return []
    lineas = []
    if (entrega.get("resumen") or "").strip():
        lineas.append("Resumen: " + " ".join(entrega["resumen"].split())[:LINEA * 2])
    if (entrega.get("evidencia") or "").strip():
        lineas.append("Evidencia: " + " ".join(entrega["evidencia"].split())[:LINEA * 2])
    git = entrega.get("git") if isinstance(entrega.get("git"), dict) else {}
    if git.get("head"):
        lineas.append(f"Commit: {str(git['head'])[:7]}"
                      + (f" en {git['rama']}" if git.get("rama") else ""))
    for prueba in entrega.get("pruebas") or ():
        if isinstance(prueba, dict) and prueba.get("comando"):
            lineas.append(f"Prueba: {prueba['comando']} → {prueba.get('estado') or '?'}")
    return lineas


def rechazo(motivo, entrega, ahora=None):
    """Lo que se guarda en el registro al devolver de Para comprobar a Haciendo: el motivo de
    la persona y la entrega que rechazó, ya en llano."""
    return {"motivo": (motivo or "").strip(), "entrega": entrega_en_llano(entrega),
            "entrega_ts": (entrega or {}).get("cuando"),
            "ts": int(ahora if ahora is not None else time.time())}


def rechazo_vigente(registro, entrega):
    """El rechazo del registro si sigue valiendo: el agente aún no volvió a entregar después
    de él (una entrega más nueva lo deja atrás). None si no hay o ya no vale."""
    r = (registro or {}).get("rechazo")
    if not r or not r.get("motivo"):
        return None
    if entrega and int(entrega.get("cuando") or 0) > int(r.get("ts") or 0):
        return None
    return r


def armar_rechazo(r):
    """La parte de la nota con el rechazo: el motivo, entero, y la entrega anterior."""
    partes = [TITULO_RECHAZO, "",
              "Entregaste esta tarea y una persona la revisó y te la devolvió. Esto es lo que "
              "te pidió cambiar, y es lo primero que tienes que resolver:", "",
              "  " + r["motivo"].replace("\n", "\n  ")]
    if r.get("entrega"):
        partes += ["", "Tu entrega anterior (la que no le valió):"]
        partes += ["  " + l for l in r["entrega"]]
    partes += ["", "Cuando lo hayas cambiado, vuelve a entregar con `cotejo entregar` diciendo "
                   "en la evidencia qué cambiaste respecto a la entrega anterior."]
    return "\n".join(partes)


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
    frase = (f"Es una reanudación (vez {vez}): retoma lo que dejó el agente "
             f"anterior{de}{lleva}.")
    if reanudacion.get("rechazo"):
        frase += f" Se la devolvieron desde Para comprobar: «{reanudacion['rechazo']}»."
    return frase
