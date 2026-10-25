"""El `git` que va primero en el PATH del agente que lanza el board (cotejo-7yfw1e, dec-kiik).

Deja pasar todo tal cual al `git` de verdad (`COTEJO_GIT_REAL`) menos dos de los prohibidos de
fábrica, que aquí se leen de los argumentos y no de cómo esté escrito el comando:

- `git push` a la fuerza: `--force`, `--force-with-lease`, `-f` (también dentro de `-uf`), una
  refspec con `+`, `--mirror`; y `--all`/`--branches`, que empujarían también `main`.
- `git push` a `main` o a la rama por defecto (`COTEJO_RAMAS_PROTEGIDAS`, más la que el remoto
  diga que es su `HEAD`): `origin main`, `HEAD:main`, `x:refs/heads/main`, `--delete main`, y un
  `git push` a secas cuya rama de destino (`@{push}`) es una de ellas.

Y una cortesía para el sandbox de Claude (cotejo-amui0f, `COTEJO_SANDBOX=1`): ahí el `.git/config`
del repo no se puede escribir (un `core.hooksPath` que dejara el agente lo correría después el
`git` de la persona), así que `git push -u` empujaba la rama pero fallaba al guardar su upstream
y salía con error. Dentro del sandbox se le quita el `-u` (`sin_upstream`) y se avisa: la rama
se empuja igual.

Es la segunda capa, debajo de lo que niega cada cliente (`clientes.prohibidos`): quien llame a
otro `git` por su ruta completa se la salta, y por eso no es la única. Solo usa la biblioteca
estándar: corre con `python -I -S` en cada llamada a `git` del agente.
"""

import os
import subprocess
import sys

# Opciones de `git` antes del subcomando que llevan su valor aparte (`git -C dir push`).
GLOBALES_CON_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
                      "--super-prefix"}
# Opciones de `git push` que llevan su valor aparte.
PUSH_CON_VALOR = {"--repo", "--receive-pack", "--exec", "--push-option", "-o"}

AVISO = ("Cotejo: {motivo}. Es uno de los prohibidos de fábrica del agente que lanza "
         "CotejoBoard (no subir privilegios, no git push --force, no empujar a main ni a la rama "
         "por defecto, no borrar fuera del worktree). Empuja tu rama sin forzar, o bloquea la "
         "tarea con el motivo.")


def partir(args):
    """(opciones globales, subcomando, resto) de una llamada a git."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in GLOBALES_CON_VALOR:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return args[:i], a, args[i + 1:]
    return args, None, []


def leer_push(args):
    """(remoto, refspecs, motivo) de los argumentos de `git push`; `motivo` si ya se ve que es
    a la fuerza o de todas las ramas."""
    remoto, refspecs, fin, i = None, [], False, 0
    while i < len(args):
        a = args[i]
        i += 1
        if not fin and a == "--":
            fin = True
            continue
        if not fin and a.startswith("--"):
            nombre = a.split("=", 1)[0]
            if nombre.startswith("--force"):
                return remoto, refspecs, f"«{nombre}» empuja a la fuerza"
            if nombre in ("--mirror", "--all", "--branches"):
                return remoto, refspecs, f"«{nombre}» empujaría también main"
            if nombre in PUSH_CON_VALOR and "=" not in a:
                if nombre == "--repo" and i < len(args):
                    remoto = args[i]
                i += 1
            continue
        if not fin and a.startswith("-") and len(a) > 1:
            letras = a[1:]
            for j, letra in enumerate(letras):
                if letra == "f":
                    return remoto, refspecs, f"«{a}» empuja a la fuerza"
                if letra == "o":
                    if j == len(letras) - 1:
                        i += 1   # `-o valor`; con `-ovalor` el valor va pegado
                    break
            continue
        if remoto is None:
            remoto = a
        else:
            refspecs.append(a)
    for refspec in refspecs:
        if refspec.startswith("+"):
            return remoto, refspecs, f"la refspec «{refspec}» empuja a la fuerza"
    return remoto, refspecs, ""


SIN_UPSTREAM = ("Cotejo: empujo sin «-u»: dentro del sandbox no se puede escribir el "
                ".git/config del repo, que es donde git guarda el upstream. La rama se empuja "
                "igual; para los siguientes push di el remoto y la rama.")


def sin_upstream(args):
    """`(args, quitado)`: la llamada a `git push` sin `-u`/`--set-upstream` (también dentro de
    `-uq`), o tal cual si no es un push o no los lleva."""
    globales, sub, resto = partir(args)
    if sub != "push":
        return args, False
    salida, quitado, fin, i = [], False, False, 0
    while i < len(resto):
        a = resto[i]
        i += 1
        if fin or a == "--":
            fin = True
            salida.append(a)
            continue
        if a == "--set-upstream":
            quitado = True
            continue
        if a.startswith("--"):
            salida.append(a)
            if a.split("=", 1)[0] in PUSH_CON_VALOR and "=" not in a and i < len(resto):
                salida.append(resto[i])
                i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            letras, valor = a[1:], ""
            if "o" in letras:
                letras, valor = letras[:letras.index("o")], letras[letras.index("o"):]
            limpias = letras.replace("u", "")
            quitado = quitado or limpias != letras
            if limpias or valor:
                salida.append("-" + limpias + valor)
            if valor == "o" and i < len(resto):
                salida.append(resto[i])
                i += 1
            continue
        salida.append(a)
    return [*globales, sub, *salida], quitado


def _git(real, globales, *args):
    try:
        hecho = subprocess.run([real, *globales, *args], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return hecho.stdout.strip() if hecho.returncode == 0 else ""


def _sin_heads(rama):
    return rama[len("refs/heads/"):] if rama.startswith("refs/heads/") else rama


def protegidas(real, globales, remoto):
    ramas = {"main"} | {r.strip() for r in os.environ.get("COTEJO_RAMAS_PROTEGIDAS", "").split(",")
                        if r.strip()}
    cabeza = _git(real, globales, "symbolic-ref", "--short", "-q",
                  f"refs/remotes/{remoto or 'origin'}/HEAD")
    if "/" in cabeza:
        ramas.add(cabeza.split("/", 1)[1])
    return ramas


def destinos(real, globales, remoto, refspecs):
    """Las ramas del remoto a las que iría este push."""
    actual = _git(real, globales, "symbolic-ref", "--short", "-q", "HEAD")
    if not refspecs:
        empuje = _git(real, globales, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                      "@{push}")
        if empuje:
            prefijo = (remoto or empuje.split("/", 1)[0]) + "/"
            return [empuje[len(prefijo):] if empuje.startswith(prefijo) else empuje]
        return [actual] if actual else []
    salida = []
    for refspec in refspecs:
        origen, _, destino = refspec.partition(":")
        destino = destino or origen
        if destino == "HEAD":
            destino = actual
        salida.append(_sin_heads(destino))
    return salida


def motivo(args, real):
    """Por qué no se deja correr esta llamada a git, o "" si se deja."""
    globales, sub, resto = partir(args)
    if sub != "push":
        return ""
    remoto, refspecs, por = leer_push(resto)
    if por:
        return por
    vedadas = protegidas(real, globales, remoto)
    for destino in destinos(real, globales, remoto, refspecs):
        if destino in vedadas:
            return f"empujar a «{destino}» está prohibido: es main o la rama por defecto"
    return ""


def real_git():
    real = os.environ.get("COTEJO_GIT_REAL")
    if real and os.path.isfile(real):
        return real
    import shutil
    propia = os.path.normcase(os.path.abspath(os.environ.get("COTEJO_GUARDAS") or os.curdir))
    camino = os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                             if p and os.path.normcase(os.path.abspath(p)) != propia)
    return shutil.which("git", path=camino) or "git"


def main(args):
    real = real_git()
    por = motivo(args, real)
    if por:
        sys.stderr.write(AVISO.format(motivo=por) + "\n")
        return 1
    if os.environ.get("COTEJO_SANDBOX") == "1":
        args, quitado = sin_upstream(args)
        if quitado:
            sys.stderr.write(SIN_UPSTREAM + "\n")
    if os.name == "nt":
        return subprocess.call([real, *args])
    os.execv(real, [real, *args])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
