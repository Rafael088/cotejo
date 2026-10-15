"""`cotejo release` (v1.2.4) con el `cotejo` ya instalado, contra un repo con y sin tags.

    python empaquetado/windows/probar_release.py [COTEJO]

Pensado para el runner de `.github/workflows/windows.yml`, después de «Instalar y probar»,
como `probar_almacen.py`, del que toma cómo encontrar el `cotejo`, la raíz larga con espacios
y acentos y cómo correrlo. Lo que se prueba es lo que en Windows puede romperse:
`.cotejo/releases/vX.Y.Z.md` bajo esa raíz, la ruta del JSON siempre con `/`, que el archivo
se escriba igual dos veces (sin `\\r\\n` que cambie su hash) y que el `git tag` que devuelve
lleve la ruta entre comillas. Recorre:

1. Sin tags: se niega nombrando la tarea abierta de la versión; con todo aprobado, el ensayo
   no escribe; `--aplicar` escribe, repetirlo no cambia nada, y nadie etiqueta.
2. La persona etiqueta (este script hace de persona): la en curso pasa al parche siguiente y
   las notas nuevas solo traen lo cerrado después del tag.

Todo en carpetas temporales (`COTEJO_ESTADO`, `COTEJO_CONFIG`); nada toca la config de verdad.
La salida de cada `cotejo ...` queda en `construido/registros/release.txt`.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from probar_almacen import (REGISTROS, Fallos, borrar_al_salir, cli, exigir_rutas_largas,
                            git_init, localizar_cotejo, raiz_al_limite)

ABIERTA, HECHA, OTRA = "cotejo-ab12cd", "cotejo-ef34gh", "cotejo-ij56kl"


def git(repo, *args):
    previo = ["-c", "core.longpaths=true"] if os.name == "nt" else []
    return subprocess.run(["git", *previo, "-C", str(repo), "-c", "user.name=prueba",
                           "-c", "user.email=prueba@ejemplo", "-c", "commit.gpgsign=false",
                           "-c", "tag.gpgsign=false", *args],
                          check=True, capture_output=True, text=True, timeout=60).stdout


def tareas(repo, *lineas):
    """Las tareas del repo como las dejaría la persona en el board (aprobar no es de la CLI)."""
    (repo / ".cotejo" / "tareas.md").write_text("# Tareas\n\n" + "".join(
        f"{linea}\n" for linea in lineas), encoding="utf-8", newline="")


def main():
    exigir_rutas_largas()
    REGISTROS.mkdir(parents=True, exist_ok=True)
    cotejo = localizar_cotejo(sys.argv[1:])
    print(f"Probando release con {cotejo}")
    fallos = Fallos()
    bitacora = []
    temporal = Path(tempfile.mkdtemp(prefix="cotejo-release-"))
    borrar_al_salir(temporal)
    repo = raiz_al_limite(temporal, "repo")
    repo.mkdir(parents=True)
    entorno = {**os.environ, "COTEJO_ESTADO": str(temporal / "estado"),
               "COTEJO_CONFIG": str(temporal / "config.json")}

    def correr(*argumentos):
        return cli(cotejo, entorno, temporal, bitacora, *argumentos)

    def release(*argumentos):
        return correr("release", "--proyecto", repo.name, *argumentos)

    git_init(repo, temporal)
    (repo / "LEEME.md").write_text("prueba\n", encoding="utf-8")
    git(repo, "add", "LEEME.md")
    git(repo, "commit", "-q", "-m", "primero")
    for argumentos in (("init", "--repo", str(repo)), ("fuentes", "usar", "repo")):
        codigo, datos, *_ = correr(*argumentos)
        if codigo != 0:
            raise SystemExit(f"`{' '.join(argumentos)}` falló ({codigo}): {datos}")

    # --- 1. sin tags -----------------------------------------------------------------------
    tareas(repo, f"- [ ] Abierta de la 0.1.0 #v0.1.0 ^{ABIERTA}",
           f"- [x] Hecha de la 0.1.0, con tildes: revisión #v0.1.0 — 2099-01-01 ^{HECHA}")
    codigo, datos, *_ = release()
    if codigo == 0 or not datos or ABIERTA not in str(datos.get("error")):
        fallos.anota(f"`release` no se negó nombrando la tarea abierta: {codigo}, {datos}")

    tareas(repo, f"- [x] Hecha de la 0.1.0, con tildes: revisión #v0.1.0 — 2099-01-01 ^{HECHA}")
    codigo, datos, *_ = correr("anotar", "problema", "--titulo", "Rutas con acentos",
                               "--texto", "Se rompían.", "--repo", str(repo))
    pro = (datos or {}).get("id")
    correr("resolver", str(pro), "--solucion", "Con pathlib.", "--repo", str(repo))
    codigo, datos, *_ = release()
    if codigo != 0 or not datos:
        fallos.anota(f"el ensayo de `release` falló: {codigo}, {datos}")
    else:
        if [t["id"] for t in datos["tareas"]] != [HECHA]:
            fallos.anota(f"el ensayo no trae la tarea aprobada: {datos['tareas']}")
        if [p["id"] for p in datos["problemas"]] != [pro]:
            fallos.anota(f"el ensayo no trae el problema resuelto: {datos['problemas']}")
        if datos["archivo"] != ".cotejo/releases/v0.1.0.md":
            fallos.anota(f"la ruta del JSON no es la esperada (con /): {datos['archivo']}")
        if (repo / ".cotejo" / "releases").exists():
            fallos.anota("el ensayo escribió .cotejo/releases/")

    codigo, datos, *_ = release("--aplicar")
    notas = repo.joinpath(*".cotejo/releases/v0.1.0.md".split("/"))
    if codigo != 0 or not datos or datos.get("hecho") != "escrita" or not notas.is_file():
        fallos.anota(f"`release --aplicar` no escribió las notas: {codigo}, {datos}")
    else:
        print(f"Notas: {notas} ({len(str(notas))} caracteres)")
        if notas.read_text(encoding="utf-8") != datos["notas"]:
            fallos.anota("las notas escritas no son las que devolvió el JSON")
        if "tag -a v0.1.0" not in datos.get("comando", "") or \
                f'"{datos["repo"]}"' not in datos["comando"]:
            fallos.anota(f"el comando de git tag no es el esperado: {datos.get('comando')}")
        antes = notas.read_bytes()
        codigo, datos, *_ = release("--aplicar")
        if codigo != 0 or (datos or {}).get("hecho") != "ya-estaba" or \
                notas.read_bytes() != antes:
            fallos.anota(f"repetir `release --aplicar` cambió algo: {codigo}, {datos}")
    if git(repo, "tag", "--list").strip():
        fallos.anota("`release` etiquetó: eso es de la persona")

    # --- 2. la persona etiqueta; lo siguiente es la 0.1.1 ------------------------------------
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "notas de la 0.1.0")
    git(repo, "tag", "-a", "v0.1.0", "-m", "0.1.0")
    tareas(repo, f"- [x] Hecha de la 0.1.0, con tildes: revisión #v0.1.0 — 2099-01-01 ^{HECHA}",
           f"- [x] Hecha de la 0.1.1 #v0.1.1 — 2099-01-02 ^{OTRA}")
    codigo, datos, *_ = release()
    if codigo != 0 or not datos:
        fallos.anota(f"`release` con tag falló: {codigo}, {datos}")
    elif (datos["version"], datos["desde"]["tag"], [t["id"] for t in datos["tareas"]]) != \
            ("0.1.1", "v0.1.0", [OTRA]):
        fallos.anota(f"con tag, la 0.1.1 no trae solo lo nuevo: {datos}")
    codigo, datos, *_ = release("--version", "0.1.0")
    if codigo == 0:
        fallos.anota(f"`release --version 0.1.0` ya etiquetada no se negó: {datos}")

    (REGISTROS / "release.txt").write_text("\n".join(bitacora), encoding="utf-8")
    if fallos:
        print(f"\n{len(fallos)} fallos:\n" + "\n".join(f"- {f}" for f in fallos))
        return 1
    print("release: todo bien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
