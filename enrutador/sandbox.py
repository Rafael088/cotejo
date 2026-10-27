"""El sandbox de Claude Code para el agente que lanza el board (v1.3.0, cotejo-amui0f, dec-kiik).

Hasta aquí «no borrar fuera del worktree» era un patrón sobre el texto del comando
(`clientes.prohibidos`): paraba `rm -rf /x`, pero no `python3 -c 'import os; os.remove("/x")'`,
`find /x -delete` ni `cd /x && rm y`. Solo Codex lo paraba de verdad, con su sandbox. Claude Code
trae uno propio para su Bash (bubblewrap en Linux, Seatbelt en macOS), que se enciende con la
clave `sandbox` de la config, y Cotejo se la pasa con `--settings` (sin tocar ningún archivo de
la persona). Con él, todo lo que corre el Bash del agente:

- **escribe solo** en su carpeta de trabajo, el `.git` del repo (sus commits), la carpeta de
  estado de Cotejo (el `cotejo` del PATH escribe ahí la bitácora) y la carpeta donde vive
  el archivo de su tarea (el `.cotejo/` del repo o la carpeta de la nota en el vault: ahí escribe
  `cotejo entregar`). Más un remoto que sea una carpeta (un `git push` a un repo desnudo local es
  escribir en él) y lo que diga `lanzar.sandbox.escritura`;
- **no escribe** la config de Cotejo (`lanzar.sandbox: false` o un `argumentos_extra` le
  quitarían el sandbox a los lanzamientos siguientes; cotejo-dgb7l2): su carpeta no es de las
  suyas y sus archivos van vedados aunque otra carpeta los contenga;
- **no escribe** dentro de lo anterior en los `hooks` ni el `config` de ese `.git` (un hook o un
  `core.hooksPath` que dejara el agente lo correría después el `git` de la persona, fuera del
  sandbox) ni en los demás worktrees del repo (el trabajo sin commitear de otras tareas). Por
  eso `git push -u` no puede guardar el upstream: la guarda de `git` le quita el `-u`;
- **sale a la red** solo hacia los servidores de sus remotos (`github.com`, y `api.github.com`
  para `gh`) y los de `lanzar.sandbox.dominios`: el resto se niega solo, sin preguntar.

Lo que cambia para el agente, probado con Claude de verdad:

- Las pruebas y los builds corren igual (escriben en su carpeta y en el temporal del sandbox).
- `git push` de su rama por HTTPS funciona, pero el sandbox no deja hablar con el llavero del
  escritorio (los sockets de Unix están cerrados), y ahí es donde `gh` guarda el token en Linux:
  sin más, el push pedía usuario y fallaba. Por eso, si el repo tiene un remoto en GitHub, el
  agente recibe `GH_TOKEN` (el de `gh auth token`, el mismo que ya usaba fuera del sandbox).
  Un remoto por SSH no funciona dentro del sandbox (no hay DNS ni conexión directa): su push
  falla y se dice en la nota del lanzamiento.
- `cotejo` funciona: escribe en su estado y el archivo de la tarea. La config solo la lee.
- Un navegador sin interfaz arranca si es Firefox (`navegador.py`, cotejo-xrmr3h): Chromium se
  aborta, porque al empezar crea un socket de Unix y el filtro seccomp de Claude niega
  `socket(AF_UNIX)`. Ese filtro no se abre (por ahí se hablaría con el D-Bus y el systemd del
  escritorio): Firefox no lo necesita y escribe solo en su perfil del `TMPDIR` y en la captura.

**Si el sandbox no está** (en Linux faltan `bwrap` o `socat`, o bubblewrap no puede crear su
espacio de nombres; o es Windows), Claude Code correría el Bash sin él avisando por stderr. Cotejo
lo mira antes (`disponible`) y entonces no lo pide: el agente trabaja como en cotejo-7yfw1e, con
los prohibidos de fábrica sobre el texto del comando y las guardas del PATH, y el lanzamiento
anota `sandbox: {"activo": false, "motivo": ...}` para que se vea por qué. Nunca deja al agente
sin poder trabajar. `lanzar.sandbox: false` en la config lo apaga a propósito.

Aquí no se lanza nada: solo se arma lo que se le pasa a Claude.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Lo que necesita el sandbox de Claude Code en Linux (lo dice el propio Claude cuando faltan).
DEPENDENCIAS_LINUX = ("bwrap", "socat")
# Los servidores que, además del del remoto, necesita cada forja conocida.
DOMINIOS_EXTRA = {"github.com": ("api.github.com",)}

_DISPONIBLE = {}


def _sistema():
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "windows"
    return "otro"


def disponible(sistema=None, which=shutil.which, probar=None):
    """`(sí/no, motivo en llano)`: si el sandbox de Claude Code puede encerrar el Bash aquí.

    - **Linux**: `bwrap` y `socat` en el PATH, y que bubblewrap pueda crear de verdad su espacio
      de nombres (`probar`; hay sistemas que tienen bwrap pero no dejan a un usuario sin
      privilegios crear uno, y ahí Claude correría sin sandbox).
    - **macOS**: `sandbox-exec` viene con el sistema.
    - **Windows** y el resto: no se pide (en Windows Claude no deja correr el Bash encerrado sin
      preguntar, y el agente del board no tiene a quién).

    El resultado se recuerda mientras dure el proceso (el board lo pregunta en cada
    lanzamiento)."""
    sistema = sistema or _sistema()
    clave = (sistema, which, probar)
    if clave in _DISPONIBLE:
        return _DISPONIBLE[clave]
    if sistema == "linux":
        faltan = [d for d in DEPENDENCIAS_LINUX if not which(d)]
        if faltan:
            resultado = (False, f"falta {' y '.join(faltan)} en esta máquina (instala "
                                f"bubblewrap y socat)")
        elif not (probar or _probar_bwrap)(which("bwrap")):
            resultado = (False, "bubblewrap está instalado pero no puede crear su espacio de "
                                "nombres en esta máquina")
        else:
            resultado = (True, "")
    elif sistema == "macos":
        resultado = ((True, "") if which("sandbox-exec") or Path("/usr/bin/sandbox-exec").exists()
                     else (False, "falta sandbox-exec"))
    else:
        resultado = (False, "el sandbox de Claude Code no se usa en este sistema")
    _DISPONIBLE[clave] = resultado
    return resultado


def _probar_bwrap(bwrap):
    """¿Arranca bubblewrap con lo que usa el sandbox (usuario, red y pids aparte)?"""
    try:
        hecho = subprocess.run([bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
                                "--unshare-all", "--die-with-parent", "true"],
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return hecho.returncode == 0


def ajustes_claude(escritura, vedadas=(), dominios=()):
    """La clave `sandbox` para `claude --settings`: el Bash encerrado, sin preguntar (no hay a
    quién), sin salida por `dangerouslyDisableSandbox`, escribiendo solo en `escritura` (menos
    `vedadas`) y saliendo a la red solo hacia `dominios`."""
    return {"sandbox": {
        "enabled": True,
        # Sin sandbox no se arranca a ciegas: lo decide `disponible` antes, y si Claude no
        # pudiera, corre sin él con los prohibidos de siempre (no deja al agente sin Bash).
        "failIfUnavailable": False,
        "autoAllowBashIfSandboxed": True,
        "allowUnsandboxedCommands": False,
        "filesystem": {"allowWrite": _unicas(escritura), "denyWrite": _unicas(vedadas)},
        "network": {"allowedDomains": _unicas(dominios)},
    }}


def argumentos_claude(ajustes):
    """`--settings <json>`: se funde con la config de la persona sin tocar sus archivos."""
    return ["--settings", json.dumps(ajustes, ensure_ascii=False, separators=(",", ":"))]


def _unicas(lista):
    return list(dict.fromkeys(str(x) for x in lista if x))


# --- lo que sale del repo de la tarea -----------------------------------------------------------

def _git(repo, *args):
    try:
        hecho = subprocess.run(["git", "-C", str(repo), *args], stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return hecho.stdout if hecho.returncode == 0 else ""


def remotos(repo):
    """Las URLs de los remotos del repo (las de traer y las de empujar), sin repetir."""
    urls = []
    for linea in _git(repo, "remote", "-v").splitlines():
        partes = linea.split()
        if len(partes) >= 2:
            urls.append(partes[1])
    return list(dict.fromkeys(urls))


def leer_remoto(url, repo=None):
    """`("red", servidor, ssh)` o `("carpeta", ruta, False)` para la URL de un remoto, o None si
    no se entiende. `ssh` dice si va por SSH (que el sandbox no deja salir)."""
    if not url:
        return None
    if "://" in url:
        partes = urlparse(url)
        if partes.scheme == "file":
            return ("carpeta", str(Path(partes.path)), False)
        if partes.hostname:
            return ("red", partes.hostname.lower(), partes.scheme in ("ssh", "git+ssh"))
        return None
    # La forma corta de SSH: [usuario@]servidor:ruta (sin barra antes de los dos puntos).
    antes, dos_puntos, _ = url.partition(":")
    if dos_puntos and "/" not in antes and len(antes) > 1:
        return ("red", antes.rsplit("@", 1)[-1].lower(), True)
    ruta = Path(url)
    if not ruta.is_absolute() and repo is not None:
        ruta = Path(repo) / ruta
    return ("carpeta", os.path.abspath(ruta), False)


def otros_worktrees(repo, propio=None):
    """Las carpetas de los demás worktrees del repo (sin el principal ni el propio)."""
    rutas = [linea[len("worktree "):] for linea in
             _git(repo, "worktree", "list", "--porcelain").splitlines()
             if linea.startswith("worktree ")]
    principal = os.path.abspath(repo)
    propio = os.path.abspath(propio) if propio else None
    return [r for r in rutas[1:] if os.path.abspath(r) not in (principal, propio)]


def token_de_gh(entorno=None, correr=subprocess.run):
    """El token de `gh` si no hay ya uno en el entorno, o "" (sin `gh`, o sin sesión)."""
    entorno = os.environ if entorno is None else entorno
    if entorno.get("GH_TOKEN") or entorno.get("GITHUB_TOKEN") or not shutil.which("gh"):
        return ""
    try:
        hecho = correr(["gh", "auth", "token"], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return hecho.stdout.strip() if hecho.returncode == 0 else ""


def del_lanzamiento(escritura, repo=None, propio=None, carpeta_tarea=None, ajustes=None,
                    entorno=None, token=token_de_gh, vedadas=()):
    """Lo que el sandbox del agente del board necesita para esta tarea:
    `{"ajustes": <para claude --settings>, "entorno": {...}, "avisos": [...]}`.

    `escritura` son las carpetas de siempre (`despacho_board.carpetas_de_escritura`), `repo` el
    repo de la tarea (si lo es), `propio` su worktree, `carpeta_tarea` donde vive el archivo de
    la tarea en su fuente, `ajustes` lo que diga `lanzar.sandbox` (`dominios`, `escritura`) y
    `vedadas` lo que no escribe aunque caiga dentro de lo anterior (`armado.vedados`: la config
    de Cotejo, cotejo-dgb7l2). Lo vedado gana."""
    ajustes = ajustes if isinstance(ajustes, dict) else {}
    escribir = list(escritura) + ([carpeta_tarea] if carpeta_tarea else [])
    escribir += [str(Path(c).expanduser()) for c in ajustes.get("escritura") or ()
                 if isinstance(c, str)]
    # `COTEJO_SANDBOX` lo lee la guarda de `git` (`guarda_git.sin_upstream`).
    vedadas, dominios, avisos, extra = list(vedadas), [], [], {"COTEJO_SANDBOX": "1"}
    for carpeta in list(escribir):
        if Path(carpeta).name == ".git":
            vedadas += [str(Path(carpeta) / "hooks"), str(Path(carpeta) / "config")]
    if repo:
        vedadas += otros_worktrees(repo, propio)
        github = False
        for url in remotos(repo):
            leido = leer_remoto(url, repo)
            if not leido:
                continue
            tipo, donde, ssh = leido
            if tipo == "carpeta":
                escribir.append(donde)
                continue
            dominios += [donde, *DOMINIOS_EXTRA.get(donde, ())]
            github = github or donde == "github.com"
            if ssh:
                avisos.append(f"El remoto {url} va por SSH, y el sandbox no deja salir por SSH: "
                              f"el push de la rama fallará (usa un remoto HTTPS).")
        if github:
            valor = token(entorno) if token else ""
            if valor:
                extra["GH_TOKEN"] = valor
    dominios += [d for d in ajustes.get("dominios") or () if isinstance(d, str)]
    return {"ajustes": ajustes_claude(escribir, vedadas, dominios), "entorno": extra,
            "avisos": avisos}


__all__ = ["disponible", "ajustes_claude", "argumentos_claude", "del_lanzamiento",
           "leer_remoto", "remotos", "otros_worktrees", "token_de_gh"]
