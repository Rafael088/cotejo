"""Instala Cotejo en Linux y comprueba que quedó usable, como en un PC recién estrenado.

    python3 empaquetado/linux/probar_instalado.py --pacman <cotejo-…-any.pkg.tar.zst> --version X
    python3 empaquetado/linux/probar_instalado.py --tar <cotejo-…-linux.tar.gz> --version X [--sin-board]

Lo usa `.github/workflows/linux.yml` dentro de un contenedor recién creado (Arch para el paquete,
Ubuntu para el tar.gz): instala de verdad, en el sistema, y por eso **no se corre en la máquina
de nadie**. Cada orden corre con un $HOME vacío y desde una carpeta vacía, sin config, contra el
vault de prueba de `herramientas/vault_prueba.py`, como lo haría el usuario después de instalar:
`cotejo` en el PATH y con la versión del release, `doctor`, crear-tomar-entregar, la entrada del
menú, lo que pone `usuario.sh` (agentes y widget de Omarchy), que el board abre y se queda
abierto, y que desinstalar se lleva los comandos. Para ver la ventana hace falta un servidor X:
el workflow lo corre bajo `xvfb-run`. Lo que dijo cada orden queda en `registros/`, al lado del
paquete, que el workflow sube como artefacto.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
# Lo que tarda el board en rendirse si algo falla al arrancar. Vivo después de esto es abierto.
ESPERA = 20
TMP = Path(tempfile.mkdtemp(prefix="cotejo-limpio-"))
HOGAR = TMP / "hogar"
# Desde donde corren los comandos: una carpeta vacía. Desde la raíz del repo, un `tareas/` del
# directorio actual no suplanta al instalado (el lanzador lo evita), pero mejor no probarlo así.
VACIA = TMP / "escritorio"
REGISTROS = None


def entorno(**extra):
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("XDG_", "COTEJO_", "FOCO_", "PYTHON"))}
    base.update(HOME=str(HOGAR), NO_COLOR="1", LANG="C.UTF-8")
    base["PATH"] = f"{HOGAR / '.local/bin'}{os.pathsep}{base.get('PATH', '')}"
    base.update(extra)
    return base


def correr(*orden, registro=None, comprobar=True, **extra):
    hecho = subprocess.run([str(o) for o in orden], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=VACIA,
                           env=entorno(**extra), timeout=300)
    if registro:
        (REGISTROS / registro).write_text(f"$ {' '.join(map(str, orden))}\n{hecho.stdout}\n"
                                          f"{hecho.stderr}", encoding="utf-8")
    if comprobar and hecho.returncode:
        raise RuntimeError(f"{' '.join(map(str, orden))} salió con {hecho.returncode}:\n"
                           f"{hecho.stdout}\n{hecho.stderr}")
    return hecho


# --- instalar y desinstalar ---------------------------------------------------------------

def instalar_pacman(paquete):
    # Las dependencias opcionales del board ya están en el contenedor; el paquete solo pide python.
    correr("pacman", "-U", "--noconfirm", paquete, registro="instalar.txt")
    # Lo que cada usuario corre una vez (el paquete no puede tocar ningún $HOME).
    correr("sh", "/usr/share/tareas-obsidian/linux/usuario.sh", registro="usuario.txt")
    return Path("/usr/bin"), Path("/usr/share")


def instalar_tar(tarball, sin_board):
    destino = TMP / "descomprimido"
    with tarfile.open(tarball) as tar:
        tar.extractall(destino, filter="data")
    carpeta = next(destino.iterdir())
    opciones = ["--sin-board"] if sin_board else []
    correr("sh", carpeta / "install.sh", *opciones, registro="instalar.txt")
    return HOGAR / ".local/bin", HOGAR / ".local/share"


def desinstalar(modo, bin_):
    if modo == "pacman":
        correr("pacman", "-R", "--noconfirm", "cotejo", registro="desinstalar.txt")
    else:
        # install.sh no copia uninstall.sh: se corre el del tar.gz descomprimido.
        carpeta = next((TMP / "descomprimido").iterdir())
        correr("sh", carpeta / "uninstall.sh", registro="desinstalar.txt")
    return [n for n in ("cotejo", "cotejoboard", "tareas-obsidian", "foco")
            if (bin_ / n).exists()]


# --- el board ---------------------------------------------------------------------------

def ventana_cotejoboard():
    arbol = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True)
    return '"CotejoBoard"' in arbol.stdout


def board_se_queda_abierto(bin_, vault):
    """¿Sigue vivo a los ESPERA segundos, con su ventana y sin traceback?

    Vivo no basta: la app hace `hold()`, así que un error al crear la ventana la deja viva y
    sin ventana (lo que pasó en Windows). Por eso se busca la ventana en el servidor X.
    """
    registro = REGISTROS / "board.txt"
    with open(registro, "w", encoding="utf-8") as salida:
        proceso = subprocess.Popen([str(bin_ / "cotejoboard")], stdout=salida,
                                   stderr=subprocess.STDOUT, cwd=VACIA,
                                   env=entorno(COTEJO_VAULT=str(vault), GDK_BACKEND="x11"))
        limite = time.monotonic() + ESPERA
        visible = False
        while time.monotonic() < limite and proceso.poll() is None:
            visible = visible or ventana_cotejoboard()
            time.sleep(1)
        captura = REGISTROS / "board.xwd"
        subprocess.run(["xwd", "-root", "-silent", "-out", str(captura)], capture_output=True)
        vivo = proceso.poll() is None
        if vivo:
            proceso.terminate()
            try:
                proceso.wait(10)
            except subprocess.TimeoutExpired:
                proceso.kill()
    texto = registro.read_text(encoding="utf-8", errors="replace")
    if vivo and visible and "Traceback" not in texto:
        return None
    if not vivo:
        return f"el board se cerró solo (código {proceso.returncode}):\n{texto}"
    if not visible:
        return f"el board sigue vivo pero no hay ventana CotejoBoard:\n{texto}"
    return f"el board sigue abierto pero se quejó:\n{texto}"


# --- todo junto -------------------------------------------------------------------------

def main(argumentos=None):
    global REGISTROS
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    paquete = analizador.add_mutually_exclusive_group(required=True)
    paquete.add_argument("--pacman", type=Path, help="el .pkg.tar.zst de Arch")
    paquete.add_argument("--tar", type=Path, help="el -linux.tar.gz")
    analizador.add_argument("--version", required=True, help="la que tiene que decir cotejo")
    analizador.add_argument("--sin-board", action="store_true",
                            help="instala solo la CLI (--tar) y no prueba el board")
    analizador.add_argument("--registros", type=Path, help="dónde dejar lo que dijo cada orden")
    args = analizador.parse_args(argumentos)
    if args.sin_board and args.pacman:
        analizador.error("--sin-board es del tar.gz: el paquete lleva siempre el board")
    archivo = (args.pacman or args.tar).resolve()
    REGISTROS = (args.registros or archivo.parent / "registros").resolve()
    REGISTROS.mkdir(parents=True, exist_ok=True)
    HOGAR.mkdir()
    VACIA.mkdir()
    # Un Omarchy de mentira y un Claude Code instalado: lo que usuario.sh mira para decidir.
    omarchy = HOGAR / ".config/omarchy"
    omarchy.mkdir(parents=True)
    (omarchy / "shell.json").write_text(json.dumps(
        {"bar": {"layout": {"right": [{"id": "reloj"}]}}}), encoding="utf-8")
    (HOGAR / ".claude").mkdir()

    modo = "pacman" if args.pacman else "tar"
    board = not args.sin_board
    fallos = []
    if modo == "pacman":
        bin_, share = instalar_pacman(archivo)
    else:
        bin_, share = instalar_tar(archivo, args.sin_board)
    print(f"Instalado ({modo}) con los comandos en {bin_}")

    cotejo = shutil.which("cotejo", path=entorno()["PATH"])
    # En Arch /usr/sbin es un enlace a /usr/bin: cuenta el archivo, no el camino.
    if not cotejo or Path(cotejo).resolve() != (bin_ / "cotejo").resolve():
        fallos.append(f"`cotejo` del PATH es {cotejo}, no el de {bin_}")
        cotejo = str(bin_ / "cotejo")

    version = correr(cotejo, "--version", registro="version.txt", comprobar=False)
    dice = (version.stdout + version.stderr).strip()
    print("cotejo --version:", dice)
    if version.returncode or args.version not in dice.split():
        fallos.append(f"cotejo --version dice «{dice}» y se esperaba {args.version}")

    sys.path.insert(0, str(RAIZ / "herramientas"))
    import vault_prueba
    vault = vault_prueba.crear(TMP / "vault")
    con_vault = {"COTEJO_VAULT": str(vault)}
    try:
        doctor = json.loads(correr(cotejo, "doctor", registro="doctor.txt", **con_vault).stdout)
        if not doctor.get("ok") or doctor["fuente"]["proyectos"] != 2:
            fallos.append(f"cotejo doctor no ve el vault de prueba: {doctor}")

        tarea = json.loads(correr(cotejo, "crear", "Tarea de la prueba de instalación limpia",
                                  "--proyecto", "Faro", **con_vault).stdout)["tarea"]["id"]
        correr(cotejo, "tomar", tarea, "--agente", "opus", **con_vault)
        correr(cotejo, "entregar", tarea, "--evidencia", "La prueba de instalación limpia.",
               **con_vault)
        lista = json.loads(correr(cotejo, "tareas", "--proyecto", "Faro", "--estado",
                                  "por-validar", registro="tareas.txt", **con_vault).stdout)
        if tarea not in json.dumps(lista):
            fallos.append(f"la tarea entregada {tarea} no sale en Por validar")
    except (RuntimeError, json.JSONDecodeError, KeyError) as error:
        fallos.append(f"la CLI contra el vault de prueba falla: {error}")

    if not (HOGAR / ".claude/skills/cotejo/SKILL.md").exists():
        fallos.append("no se escribió la skill de Cotejo en ~/.claude")

    escritorio = share / "applications/io.github.cotejoapp.Cotejo.desktop"
    widget = omarchy / "plugins/cotejo.barra/Widget.qml"
    if board:
        if not escritorio.is_file():
            fallos.append(f"no hay entrada del menú en {escritorio}")
        if not (share / "icons/hicolor/scalable/apps/io.github.cotejoapp.Cotejo.svg").is_file():
            fallos.append("no hay ícono del menú")
        if not widget.is_file():
            fallos.append("el widget de Omarchy no quedó puesto")
        problema = board_se_queda_abierto(bin_, vault)
        if problema:
            fallos.append(problema)
    else:
        if (bin_ / "cotejoboard").exists() or escritorio.exists() or widget.exists():
            fallos.append("--sin-board dejó board, menú o widget")

    sobran = desinstalar(modo, bin_)
    if sobran:
        fallos.append(f"después de desinstalar siguen: {', '.join(sobran)}")

    if fallos:
        print("Falló:\n- " + "\n- ".join(fallos))
        return 1
    print(f"Instalado y usable ({modo}{', sin board' if not board else ''}): cotejo {args.version} "
          f"en el PATH, la CLI contra un vault limpio"
          f"{', menú, widget y el board abre' if board else ''}; desinstalar lo quita.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
