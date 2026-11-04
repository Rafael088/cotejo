"""Fechas que se le preguntan a git para la frescura de `proyecto.md` (las usa
`conocimiento.frescura_proyecto`): la del último commit que tocó algo y la del último tag.
Aparte de `conocimiento.py` para que no pase de su tope de líneas. Nunca levantan: la frescura
es una pista y sin git, o si git falla, devuelven None.
"""

import subprocess

from enrutador import subproceso


def fecha(raiz, *args):
    """Fecha (AAAA-MM-DD) que imprime `git log -1 --format=%cs <args>`, o None si no hay git,
    el archivo no está en un commit o algo falla. Nunca levanta: la frescura es una pista."""
    try:
        hecho = subproceso.run(["git", "-C", str(raiz), "log", "-1", "--format=%cs", *args],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    texto = hecho.stdout.strip()
    return texto if hecho.returncode == 0 and texto else None


def ultimo_tag(raiz):
    """(nombre, fecha) del tag más reciente alcanzable desde HEAD, o None si no hay."""
    try:
        hecho = subproceso.run(["git", "-C", str(raiz), "describe", "--tags", "--abbrev=0"],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    nombre = hecho.stdout.strip()
    if hecho.returncode != 0 or not nombre:
        return None
    dia = fecha(raiz, nombre)
    return (nombre, dia) if dia else None
