"""Trabajo de tareas que existe en ramas de Git pero todavía no en la rama principal.

El maestro conversa desde la carpeta principal del proyecto. Mirar solo sus archivos hace que
un trabajo aislado en ``cotejo/<id>`` parezca inexistente. Este módulo prepara una foto de solo
lectura para el prompt: ramas con commits fuera de ``HEAD``, la tarea a la que pertenecen y la
razón que explica su estado. No integra ni modifica Git.
"""

import os
import subprocess
from pathlib import Path

from . import worktrees


TIEMPO_GIT = 60


def _git(carpeta, *args):
    try:
        hecho = subprocess.run(
            ["git", "-C", str(carpeta), *args], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIEMPO_GIT,
            env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return hecho.returncode, hecho.stdout.strip()


def _motivo(estado):
    return {
        "en-curso": "sigue en Haciendo: aún no se ha entregado ni aprobado",
        "por-validar": ("está en Para comprobar: falta que una persona la apruebe; "
                        "al aprobar se intenta integrar"),
        "pendiente": ("está en Pendiente: el trabajo no tiene una entrega aprobada que "
                      "se pueda integrar"),
        "hecha": ("figura finalizada, pero esta rama no está integrada; la integración "
                  "quedó pendiente o falló"),
    }.get(estado, "la rama tiene trabajo sin integrar y no encuentro su tarea en el tablero")


def detectar(carpeta, tareas):
    """Ramas ``cotejo/*`` con commits que no están en ``HEAD``.

    ``tareas`` son las filas del proyecto, de cualquier columna. Las ramas ajenas al formato de
    Cotejo y las que ya no corresponden a una tarea del proyecto no se incluyen: pueden ser
    restos históricos de otra fuente y tapar las ramas actuales con decenas de falsos avisos.
    """
    if not carpeta or not Path(carpeta).is_dir():
        return []
    codigo, cabeza = _git(carpeta, "rev-parse", "--verify", "HEAD")
    if codigo != 0 or not cabeza:
        return []
    codigo, salida = _git(
        carpeta, "for-each-ref",
        "--format=%(refname:short)%00%(objectname)%00%(subject)", "refs/heads/cotejo/")
    if codigo != 0:
        return []

    por_rama = {worktrees.rama_de(t.get("id")): t for t in tareas if t.get("id")}
    pendientes = []
    for linea in salida.splitlines():
        partes = linea.split("\0", 2)
        if len(partes) != 3:
            continue
        rama, punta, asunto = partes
        tarea = por_rama.get(rama)
        if tarea is None:
            continue
        if punta == cabeza:
            continue
        integrado, _ = _git(carpeta, "merge-base", "--is-ancestor", punta, cabeza)
        if integrado == 0:
            continue
        codigo, cuantos = _git(carpeta, "rev-list", "--count", f"{cabeza}..{punta}")
        try:
            commits = int(cuantos) if codigo == 0 else 0
        except ValueError:
            commits = 0
        if not commits:
            continue
        estado = tarea.get("estado") or "desconocida"
        pendientes.append({
            "rama": rama, "punta": punta, "commits": commits, "ultimo": asunto,
            "id": tarea.get("id"), "texto": tarea.get("texto"), "estado": estado,
            "motivo": _motivo(estado),
        })

    prioridad = {"en-curso": 0, "por-validar": 1, "pendiente": 2, "hecha": 3,
                 "desconocida": 4}
    return sorted(pendientes, key=lambda r: (prioridad.get(r["estado"], 4), r["rama"]))
