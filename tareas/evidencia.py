"""La evidencia que se puede volver a comprobar: rama, commits, diff y pruebas con su salida.

El texto libre de `entregar --evidencia` dice lo que el agente cree que hizo. Esto guarda lo
que se puede mirar sin creerle: en qué rama y en qué commits quedó el trabajo, qué archivos
cambiaron y cuánto, y qué comandos de prueba corrió **Cotejo mismo** —no el agente— con su
salida y su código de salida. Un «pasan las pruebas» escrito a mano no se puede repetir; un
`argv` con su código de salida sí, y es lo que `comprobar` (B2) volverá a correr.

Por eso las pruebas se guardan como `argv` (una lista), además del texto: volver a correrlas
no puede depender de un shell, ni del de la persona ni de ninguno. Se parten con `shlex` y se
lanzan sin shell, con tiempo límite.

Nada de aquí falla la entrega por no poder mirar git: una tarea del segundo cerebro que no es
de código no tiene repo, y eso no la hace inentregable. Si no hay repo, no hay clave `git`.

No importa GTK, como el resto del núcleo.
"""

import argparse
import os
import shlex
import subprocess
import time

# Versión de lo que va dentro de `git` y `pruebas` en la bitácora. Las claves se agregan; no
# se renombran ni se quitan (el mismo contrato que la bitácora y `estado.json`).
ESQUEMA = 1

# Cuánto de la salida de cada prueba se guarda. La bitácora se lee por la cola (256 KiB): una
# salida entera de un `pytest -v` empujaría fuera del tope lo último de las demás tareas. Se
# guarda el final, que es donde las herramientas de pruebas ponen el resumen y el fallo.
SALIDA_MAX = 4000

# Tiempo límite por prueba, en segundos. Una prueba colgada no puede dejar la entrega colgada.
TIEMPO_PRUEBA = 900

# Cuántos commits se apuntan como mucho: una rama larga no tiene que llenar la bitácora.
COMMITS_MAX = 50

# Las ramas contra las que se mide «lo que hizo esta rama», por orden de preferencia.
BASES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")


def partir(comando):
    """El texto de una prueba como argv. Lanza ValueError si no se puede partir (comillas)."""
    argv = shlex.split(comando)
    if not argv:
        raise ValueError("una prueba vacía no comprueba nada")
    return argv


def correr_prueba(comando, carpeta, tiempo=TIEMPO_PRUEBA):
    """Corre una prueba sin shell y devuelve lo que se guarda de ella.

    `codigo` es None cuando no llegó a terminar (no existe el programa, o se pasó del tiempo):
    eso no es un 0 ni un 1, y no se puede disfrazar de ninguno de los dos.
    """
    argv = partir(comando)
    registro = {"comando": comando, "argv": argv, "carpeta": str(carpeta)}
    inicio = time.monotonic()
    try:
        hecho = subprocess.run(argv, cwd=carpeta, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=tiempo)
        registro["codigo"] = hecho.returncode
        salida = hecho.stdout
    except subprocess.TimeoutExpired as error:
        registro["codigo"] = None
        registro["error"] = f"se pasó de {tiempo} s"
        salida = error.output or b""
    except OSError as error:
        registro["codigo"] = None
        registro["error"] = str(error)
        salida = b""
    registro["segundos"] = round(time.monotonic() - inicio, 2)
    texto = salida.decode("utf-8", "replace")
    registro["salida"] = texto[-SALIDA_MAX:]
    if len(texto) > SALIDA_MAX:
        registro["salida_recortada"] = True
    return registro


def _git(carpeta, *args):
    """La salida de un git, o None si falla. Sin shell, sin entrada y con tiempo límite."""
    try:
        hecho = subprocess.run(["git", "-C", str(carpeta), *args], stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if hecho.returncode != 0:
        return None
    return hecho.stdout.decode("utf-8", "replace").strip()


def _base(carpeta):
    """La rama de la que salió esta y el commit donde se separaron, o (None, None).

    Si la rama actual es la base misma (se trabajó sobre master), no hay separación que medir.
    """
    cabeza = _git(carpeta, "rev-parse", "HEAD")
    for nombre in BASES:
        if _git(carpeta, "rev-parse", "--verify", "--quiet", nombre + "^{commit}") is None:
            continue
        separacion = _git(carpeta, "merge-base", "HEAD", nombre)
        if separacion and separacion != cabeza:
            return nombre, separacion
    return None, None


def git(carpeta):
    """Rama, commits y resumen del diff del repo en `carpeta`, o None si no es un repo."""
    raiz = _git(carpeta, "rev-parse", "--show-toplevel")
    if raiz is None:
        return None
    cabeza = _git(carpeta, "rev-parse", "HEAD")
    if cabeza is None:  # repo sin ningún commit
        return {"repo": raiz, "rama": _git(carpeta, "symbolic-ref", "--short", "HEAD"),
                "commits": [], "sin_commitear": bool(_git(carpeta, "status", "--porcelain"))}
    rama = _git(carpeta, "symbolic-ref", "--short", "-q", "HEAD") or None  # None: HEAD suelto
    base, separacion = _base(carpeta)
    rango = f"{separacion}..HEAD" if separacion else "-1"
    crudo = _git(carpeta, "log", "--format=%H%x09%s", f"--max-count={COMMITS_MAX}", rango) or ""
    commits = [dict(zip(("hash", "asunto"), linea.split("\t", 1)))
               for linea in crudo.splitlines() if linea]
    desde = separacion or (cabeza + "^" if _git(carpeta, "rev-parse", "-q", "--verify",
                                                 cabeza + "^") else None)
    datos = {"repo": raiz, "rama": rama, "head": cabeza, "base": base,
             "desde": separacion, "commits": commits,
             "sin_commitear": bool(_git(carpeta, "status", "--porcelain"))}
    if desde:
        datos["diff"] = _diff(carpeta, desde)
    return datos


def _diff(carpeta, desde):
    """Archivos tocados con sus +/- entre `desde` y HEAD. Los binarios llevan None."""
    crudo = _git(carpeta, "diff", "--numstat", "-z", desde, "HEAD") or ""
    archivos = []
    partes = crudo.split("\0")
    i = 0
    while i < len(partes):
        campo = partes[i]
        i += 1
        if not campo:
            continue
        mas, menos, ruta = (campo.split("\t", 2) + ["", ""])[:3]
        if not ruta:  # renombrado: con -z vienen origen y destino en los dos campos siguientes
            ruta = partes[i + 1] if i + 1 < len(partes) else ""
            i += 2
        archivos.append({"ruta": ruta,
                         "mas": int(mas) if mas.isdigit() else None,
                         "menos": int(menos) if menos.isdigit() else None})
    return {"archivos": archivos,
            "mas": sum(a["mas"] or 0 for a in archivos),
            "menos": sum(a["menos"] or 0 for a in archivos)}


def reunir(carpeta=None, pruebas=()):
    """Lo que se agrega a la línea de `entregar` en la bitácora: `git` y `pruebas`.

    Solo las claves que hay: sin repo no va `git`, sin `--prueba` no va `pruebas`.
    """
    carpeta = os.path.abspath(carpeta or os.getcwd())
    datos = {"evidencia_esquema": ESQUEMA}
    repo = git(carpeta)
    if repo is not None:
        datos["git"] = repo
    if pruebas:
        datos["pruebas"] = [correr_prueba(comando, carpeta) for comando in pruebas]
    return datos


def resumen_para_humanos(texto):
    """El `--resumen` de `entregar`: opcional, pero si viene no puede venir vacío.

    Es una clave que se AGREGA a la evidencia; sin ella la anotación queda como siempre.
    """
    if not texto.strip():
        raise argparse.ArgumentTypeError(
            "el resumen viene vacío. Cuenta qué cambió visto desde fuera y cómo probarlo uno "
            "mismo, sin jerga; o quita --resumen.")
    return texto.strip()
