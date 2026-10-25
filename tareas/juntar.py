"""Las tareas de «juntar» que crea «Que lo resuelva un agente» (cotejo-00fwc2), sin GTK.

Cuando aprobar una entrega en un proyecto del Inicio choca, el board crea una tarea para que un
agente junte los dos trabajos. Qué rama quedó fuera se guarda aquí, en
`rutas.estado()/juntar/<id de la tarea de juntar>.json`, y no en el texto de la tarea: el texto
es para leerlo, y una persona puede reescribirlo. Cuando la tarea de juntar se aprueba y entra
limpia, `borrar_original` borra la rama original con `branch -d`, que git solo hace si ya está
integrada; si no lo está, no se fuerza y se dice.
"""

import json
import os
import re
import subprocess

from . import rutas

CARPETA = rutas.estado() / "juntar"


def _ruta(tarea_id):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", tarea_id or ""):
        raise ValueError(f"«{tarea_id}» no es el id de una tarea")
    return CARPETA / f"{tarea_id}.json"


def anotar(tarea_id, rama, repo):
    """Apunta que la tarea `tarea_id` junta la rama `rama` de `repo`. Reemplazo atómico."""
    ruta = _ruta(tarea_id)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f".{ruta.name}.tmp")
    temporal.write_text(json.dumps({"rama": rama, "repo": str(repo)}, ensure_ascii=False),
                        encoding="utf-8")
    os.replace(temporal, ruta)


def de_tarea(tarea_id):
    """`{rama, repo}` si `tarea_id` es una tarea de juntar; None si no (o si el registro está roto)."""
    try:
        datos = json.loads(_ruta(tarea_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) and datos.get("rama") and datos.get("repo") else None


def borrar_original(tarea_id):
    """Tras integrar la tarea de juntar: `branch -d` de la rama original. `{rama, borrada,
    motivo?}`, o None si `tarea_id` no es de juntar. El registro se olvida en los dos casos: un
    segundo intento daría lo mismo, y la rama que queda se ve en git."""
    datos = de_tarea(tarea_id)
    if datos is None:
        return None
    rama, repo = datos["rama"], datos["repo"]
    try:
        hecho = subprocess.run(["git", "-C", repo, "branch", "-d", rama], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL, timeout=60,
                               env={**os.environ, "LC_ALL": "C"})
        codigo, error = hecho.returncode, hecho.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as fallo:
        codigo, error = None, str(fallo)
    try:
        _ruta(tarea_id).unlink()
    except OSError:
        pass
    if codigo == 0:
        return {"rama": rama, "borrada": True}
    if "not found" in (error or ""):
        return {"rama": rama, "borrada": True, "ya_no_estaba": True}
    return {"rama": rama, "borrada": False, "motivo": error or "git no contestó"}
