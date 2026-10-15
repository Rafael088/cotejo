"""Despachar con worktree, entregar y comprobar, de punta a punta, con el Cotejo instalado.

    python empaquetado/windows/probar_despachar.py

Corre después de «Instalar y probar» en `.github/workflows/windows.yml`, con Cotejo ya
instalado en esta misma máquina: repite en el runner de Windows, con Git Bash, lo que el
worktree por despacho (B3) promete y que la batería de `pruebas/` no puede comprobar del todo
porque corre en Linux —un archivo de más de 260 caracteres de ruta dentro del repo, y el
`core.longpaths=true` que `tareas/worktrees.py` solo activa en Windows—.

La carpeta del repo y la del worktree se quedan cortas a propósito: `-C` (y el `cwd` de
cualquier proceso) hace un `chdir` de verdad, y eso en Windows se niega por encima de
MAX_PATH aunque `core.longpaths` esté activo —lo primero que reveló este script en el
runner—. Lo largo es un archivo *dentro* del repo, varios niveles hondo: es lo que `git
worktree add` tiene que escribir en el worktree sin poder chdir ahí, que es exactamente el
caso que `core.longpaths=true` existe para resolver.

La tarea vive en un vault de Obsidian de mentira, no en un repo (`COTEJO_FUENTE=repo`): la
fuente de repos tiene su propio fallo en Windows —`tareas/fuentes/repo.py` compara rutas como
texto («repo/.cotejo/tareas.md») contra lo que arma `str(Path(...))`, que en Windows sale con
`\\` y nunca coincide— y arreglarlo no es de worktrees ni de comprobar; queda descrito en la
evidencia de la entrega para quien le toque. Lo que B5 tiene que probar —el worktree por
despacho— no depende de qué fuente dio la tarea, así que este script usa la misma Obsidian de
mentira que ya cubre `pruebas/test_worktrees.py` en Linux (`enrutador.proyectos` manda al
agente al repo real).

Todo pasa en una carpeta temporal aislada (`COTEJO_VAULT`, `COTEJO_ESTADO` y `COTEJO_CONFIG`
ahí): nada toca el vault real ni la config de verdad, y el motor es `agente` (el que no lanza
ningún proceso, el mismo con el que un agente despacha su propia tarea) para no gastar un
token ni depender de ninguna cuenta en el runner.

La salida de cada comando queda en `construido/registros/despachar-windows.txt`, que el
workflow ya sube como artefacto pequeño junto a los demás registros; nada de instaladores ni de
árboles de trabajo.
"""

import atexit
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REGISTROS = AQUI / "construido" / "registros"
TAREA = "cotejo-prueba-despachar-win"
TEXTO = "Probar despachar con worktree en Windows"
PROYECTO = "ProyectoDePrueba"
CARPETA_PROYECTOS = "Proyectos"
# Un nombre de carpeta largo a propósito, repetido varias veces: lo que hace falta para que la
# ruta de un archivo *dentro* del repo (no la del repo ni la del worktree, que se quedan
# cortas) pase los 260 caracteres de MAX_PATH.
SEGMENTO = "carpeta-de-prueba-para-verificar-que-las-rutas-largas-funcionan-en-windows"
NIVELES_HONDO = 4
ARCHIVO_HONDO = "archivo.txt"
TAREA_REPO = "cotejo-prueba-repo-win"
TEXTO_REPO = "Probar despachar con repo en Windows"


def git(carpeta, *args):
    # `core.longpaths=true`: el repo de prueba lleva a propósito un archivo de ruta larga
    # (`ruta_honda`), y sin esto `git add`/`commit` no llegan a leerlo ni a escribirlo en los
    # objetos del repo.
    hecho = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(carpeta), "-c", "user.name=Prueba",
         "-c", "user.email=prueba@cotejo.invalid", "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True)
    if hecho.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} en {carpeta} salió con {hecho.returncode}:\n"
                           f"{hecho.stdout}\n{hecho.stderr}")
    return hecho.stdout.strip()


def ruta_honda(raiz):
    """`raiz` con `NIVELES_HONDO` carpetas largas colgando, y el archivo al final de todas."""
    honda = raiz
    for _ in range(NIVELES_HONDO):
        honda = honda / SEGMENTO
    return honda / ARCHIVO_HONDO


def preparar_repo(temporal):
    """El repo de prueba (sin tareas: las lleva el vault), con un archivo hondo para que
    `worktree add` lo copie."""
    repo = temporal / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    archivo = ruta_honda(repo)
    archivo.parent.mkdir(parents=True)
    archivo.write_text("una línea, para que el worktree tenga algo que copiar aquí.\n",
                       encoding="utf-8")
    if len(str(archivo)) < 260:
        raise SystemExit(f"el archivo hondo no quedó largo ({len(str(archivo))} "
                          f"caracteres): {archivo}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def preparar_vault(temporal, repo):
    """El vault de mentira con la tarea, y la config que manda su proyecto al repo de verdad."""
    vault = temporal / "vault"
    nota = vault / CARPETA_PROYECTOS / f"{PROYECTO}.md"
    nota.parent.mkdir(parents=True)
    nota.write_text(
        f"---\ntipo: proyecto\n---\n\n- [ ] {TEXTO} #agente/haiku ^{TAREA}\n", encoding="utf-8")
    config = temporal / "config.json"
    config.write_text(json.dumps({"enrutador": {"proyectos": {PROYECTO: str(repo)}}}),
                      encoding="utf-8")
    return vault, config


def preparar_repo_con_tareas(repo):
    """Añade al repo de prueba un archivo `.cotejo/tareas.md` con una tarea."""
    cotejo = repo / ".cotejo"
    cotejo.mkdir(exist_ok=True)
    tareas = cotejo / "tareas.md"
    tareas.write_text(
        f"# Tareas\n\n- [ ] {TEXTO_REPO} #agente/haiku ^{TAREA_REPO}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "añadir tareas.md")


def borrar_al_salir(carpeta):
    """Borra `carpeta` al terminar el script, pase lo que pase, salvo con `COTEJO_CONSERVAR=1`
    (para depurar). Quita antes el solo-lectura que deja git en `.git/objects`: sin eso,
    `rmtree` no puede en Windows, y las rutas largas el Explorador tampoco las borra."""
    if os.environ.get("COTEJO_CONSERVAR") == "1":
        return

    def escribible(funcion, ruta, _error):
        os.chmod(ruta, stat.S_IWRITE)
        funcion(ruta)

    atexit.register(shutil.rmtree, carpeta, onerror=escribible)


def exigir_rutas_largas():
    """En Windows, sale con un mensaje claro si `LongPathsEnabled` no está a 1: sin eso, ni
    Python puede crear las carpetas de prueba, y el traceback de `pathlib` no dice por qué."""
    if os.name != "nt":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as clave:
            valor, _ = winreg.QueryValueEx(clave, "LongPathsEnabled")
    except OSError:
        valor = 0
    if valor != 1:
        raise SystemExit(
            "Este script necesita las rutas largas de Windows activadas (LongPathsEnabled=1; "
            "el runner windows-latest ya las trae). Actívalas en una PowerShell de "
            "administrador y vuelve a correrlo:\n  New-ItemProperty -Path "
            "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem -Name LongPathsEnabled "
            "-Value 1 -PropertyType DWORD -Force")


def main():
    exigir_rutas_largas()
    REGISTROS.mkdir(parents=True, exist_ok=True)
    cotejo = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Cotejo" / "bin" / "cotejo.exe"
    if not cotejo.is_file():
        raise SystemExit(f"No hay {cotejo}: este script espera que ya esté instalado Cotejo "
                          "(corre después del paso «Instalar y probar»).")

    # Corta a propósito: `-C` (y el `cwd` de `cli()`, más abajo) le hacen un `chdir`, y eso se
    # niega en Windows por encima de MAX_PATH sin que `core.longpaths` ayude (es lo que reveló
    # el primer run de esto en el runner). Lo largo va dentro del repo, no en esta carpeta.
    temporal = Path(tempfile.mkdtemp(prefix="cotejo-wt-"))
    borrar_al_salir(temporal)
    repo = preparar_repo(temporal)
    vault, config = preparar_vault(temporal, repo)
    entorno = {**os.environ, "COTEJO_VAULT": str(vault),
               "COTEJO_CARPETA_PROYECTOS": CARPETA_PROYECTOS,
               "COTEJO_ESTADO": str(temporal / "estado"), "COTEJO_CONFIG": str(config)}
    bitacora = []

    def cli(*argumentos):
        hecho = subprocess.run([str(cotejo), *argumentos], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=temporal, env=entorno)
        bitacora.append(f"$ cotejo {' '.join(argumentos)}\n{hecho.stdout}{hecho.stderr}"
                        f"(código {hecho.returncode})\n")
        if hecho.returncode != 0:
            raise RuntimeError(f"cotejo {' '.join(argumentos)} salió con {hecho.returncode}:\n"
                               f"{hecho.stdout}\n{hecho.stderr}")
        return json.loads(hecho.stdout) if hecho.stdout.strip() else None

    try:
        # Prueba 1: fuente Obsidian con worktree
        despacho = cli("despachar", TAREA, "--motor", "agente")
        if not (despacho["aislado"] and despacho["worktree"]["creado"]):
            raise RuntimeError(f"despachar no creó un worktree de verdad: {despacho}")
        worktree = despacho["worktree"]["ruta"]
        if not Path(worktree).is_dir():
            raise RuntimeError(f"el worktree que dijo despachar no existe en disco: {worktree}")
        archivo_hondo = ruta_honda(Path(worktree))
        if not archivo_hondo.is_file():
            raise RuntimeError(
                f"`worktree add` no copió el archivo de ruta larga ({len(str(archivo_hondo))} "
                f"caracteres) al worktree: {archivo_hondo}")

        entrega = cli("entregar", TAREA, "--evidencia",
                      "Prueba automática del runner de Windows (B5): despachar con worktree, "
                      "entregar y comprobar con un archivo de más de 260 caracteres de ruta "
                      "dentro del repo.", "--prueba", "python --version", "--repo", worktree)
        if not entrega["pruebas"][0]["codigo"] == 0:
            raise RuntimeError(f"la prueba de la entrega no salió en 0: {entrega}")

        comprobado = cli("comprobar", TAREA)
        if not comprobado["sigue_igual"]:
            raise RuntimeError(f"comprobar no dio «sigue igual»: {comprobado}")

        antes = cli("worktrees")
        fila = next(f for f in antes["worktrees"] if f["tarea"] == TAREA)
        if fila["sobra"]:
            raise RuntimeError(f"el worktree ya aparece de sobra antes de aprobar: {fila}")

        # Lo que hace una persona al aprobar en CotejoBoard: marcar la línea [x]. Se simula
        # igual que lo haría el board, editando la nota del vault de prueba.
        nota = vault / CARPETA_PROYECTOS / f"{PROYECTO}.md"
        nota.write_text(nota.read_text(encoding="utf-8").replace("- [ ]", "- [x]", 1),
                        encoding="utf-8")

        limpieza = cli("worktrees", "--limpiar")
        fila = next(f for f in limpieza["worktrees"] if f["tarea"] == TAREA)
        if not fila.get("retirado"):
            raise RuntimeError(f"worktrees --limpiar no retiró el worktree: {fila}")
        if Path(worktree).exists():
            raise RuntimeError(f"{worktree} sigue en disco después de limpiar")
        if f"cotejo/{TAREA}" not in git(repo, "branch", "--format=%(refname:short)"):
            raise RuntimeError("limpiar se llevó la rama por delante, y no debía")

        # Prueba 2: fuente repo con worktree (verifica que la normalización de paths en
        # Windows funciona en tareas/fuentes/repo.py)
        preparar_repo_con_tareas(repo)
        entorno_repo = {**entorno, "COTEJO_FUENTE": "repo",
                        "COTEJO_REPOS": str(repo)}
        bitacora.append("--- Prueba con fuente repo ---\n")

        def cli_repo(*argumentos):
            hecho = subprocess.run([str(cotejo), *argumentos], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", cwd=temporal,
                                   env=entorno_repo)
            bitacora.append(f"$ cotejo {' '.join(argumentos)}\n{hecho.stdout}{hecho.stderr}"
                            f"(código {hecho.returncode})\n")
            if hecho.returncode != 0:
                raise RuntimeError(f"cotejo {' '.join(argumentos)} salió con {hecho.returncode}:\n"
                                   f"{hecho.stdout}\n{hecho.stderr}")
            return json.loads(hecho.stdout) if hecho.stdout.strip() else None

        despacho_repo = cli_repo("despachar", TAREA_REPO, "--motor", "agente")
        if not (despacho_repo["aislado"] and despacho_repo["worktree"]["creado"]):
            raise RuntimeError(f"despachar (repo) no creó un worktree: {despacho_repo}")
        worktree_repo = despacho_repo["worktree"]["ruta"]
        if not Path(worktree_repo).is_dir():
            raise RuntimeError(f"el worktree (repo) no existe: {worktree_repo}")

        entrega_repo = cli_repo("entregar", TAREA_REPO, "--evidencia",
                                "Prueba automática del runner de Windows (B5): fuente repo, "
                                "despachar, entregar con archivo de ruta larga.",
                                "--prueba", "python --version", "--repo", worktree_repo)
        if not entrega_repo["pruebas"][0]["codigo"] == 0:
            raise RuntimeError(f"la prueba de entrega (repo) no salió en 0: {entrega_repo}")
    finally:
        (REGISTROS / "despachar-windows.txt").write_text(
            "\n".join(bitacora) +
            f"\nArchivo de ruta larga: {len(str(ruta_honda(repo)))} caracteres.\n",
            encoding="utf-8")

    print(f"despachar con worktree (con un archivo a {len(str(ruta_honda(repo)))} caracteres "
          "de ruta), entregar, comprobar, limpiar (fuente Obsidian), y fuente repo: "
          "todo bien en Windows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
