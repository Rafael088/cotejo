"""El widget de Cotejo en la barra de Omarchy: ponerlo y quitarlo, en el usuario que lo corre.

    python3 widget.py poner --lanzador RUTA [--forzar]
    python3 widget.py quitar

Vive en la instalación (`<destino>/linux/`), junto a `barra/cotejo.barra`, y lo llama
`usuario.sh`. `poner` no hace nada si el usuario no tiene Omarchy, salvo con `--forzar`.

El `Widget.qml` del repo supone la instalación de siempre: `~/.local/bin/tareas-obsidian` y el
`estado.json` en `~/.local/state`. Al copiarlo se le escriben las dos rutas de *esta*
instalación —el lanzador que se instaló y la carpeta de estado que dice `tareas.rutas`—, así que
un paquete en `/usr` o un `XDG_STATE_HOME` propio no dejan la barra leyendo de otro sitio.

El widget se agrega a `shell.json` una sola vez (con copia `.bak`); después se respeta dónde lo
haya puesto el usuario. Al quitarlo se saca también de ahí: una entrada que apunta a un plugin
que ya no existe es un hueco en la barra.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESTINO))

from tareas import rutas  # noqa: E402

ID = "cotejo.barra"
# El mismo widget con el nombre de antes: se quita para que no haya dos.
VIEJO = "rafael.foco"
ORIGEN = DESTINO / "barra" / ID


def omarchy():
    return rutas.config_base() / "omarchy"


def ajustar(qml, lanzador, archivo):
    """El `Widget.qml` con las rutas de esta instalación en vez de las de siempre."""
    for propiedad, valor in (("archivo", archivo), ("lanzador", lanzador)):
        qml, cuantas = re.subn(rf"(readonly property string {propiedad}: ).*",
                               lambda m: m.group(1) + json.dumps(str(valor)), qml, count=1)
        if not cuantas:
            sys.exit(f"Widget.qml ya no declara «{propiedad}»: actualiza empaquetado/linux/widget.py")
    return qml


def registrar(shell_json):
    """Lo agrega a la derecha la primera vez; si estaba con el nombre de antes, lo renombra."""
    try:
        datos = json.loads(shell_json.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"No pude leer {shell_json}: {error}. Agrega el widget {ID} a mano.")
        return
    layout = datos.setdefault("bar", {}).setdefault("layout", {})
    widgets = [w for s in layout.values() for w in s]
    viejos = [w for w in widgets if w.get("id") == VIEJO]
    if not viejos and any(w.get("id") == ID for w in widgets):
        print("La barra ya tiene el widget de Cotejo.")
        return
    shutil.copy(shell_json, shell_json.with_name(shell_json.name + ".bak"))
    if viejos:
        for w in viejos:
            w["id"] = ID
        mensaje = f"Widget de la barra renombrado de {VIEJO} a {ID}"
    else:
        layout.setdefault("right", []).insert(0, {"id": ID})
        mensaje = "Widget de Cotejo agregado a la barra"
    shell_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{mensaje} (copia previa en {shell_json.name}.bak).")


def desregistrar(shell_json):
    try:
        datos = json.loads(shell_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    layout = datos.get("bar", {}).get("layout", {})
    if not any(w.get("id") in (ID, VIEJO) for s in layout.values() for w in s):
        return
    shutil.copy(shell_json, shell_json.with_name(shell_json.name + ".bak"))
    for seccion, widgets in layout.items():
        layout[seccion] = [w for w in widgets if w.get("id") not in (ID, VIEJO)]
    shell_json.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Widget de Cotejo quitado de la barra (copia previa en {shell_json.name}.bak).")


def poner(lanzador, forzar=False):
    if not omarchy().is_dir() and not forzar:
        print("Sin Omarchy en este usuario: el widget de la barra no se instala.")
        return
    if not ORIGEN.is_dir():
        print("Esta instalación es solo la CLI (--sin-board): no trae el widget de la barra.")
        return
    # La barra no hereda el COTEJO_ESTADO de quien instala: lee de donde escribe sin él.
    os.environ.pop("COTEJO_ESTADO", None)
    plugins = omarchy() / "plugins"
    plugins.mkdir(parents=True, exist_ok=True)
    for nombre in (ID, VIEJO):
        shutil.rmtree(plugins / nombre, ignore_errors=True)
    destino = plugins / ID
    shutil.copytree(ORIGEN, destino, ignore=shutil.ignore_patterns("__pycache__"))
    qml = destino / "Widget.qml"
    qml.write_text(ajustar(qml.read_text(encoding="utf-8"), lanzador,
                           rutas.estado() / "estado.json"), encoding="utf-8")
    print(f"Widget de la barra en {destino}")
    # El shell recarga los plugins al guardarlos, sin reiniciar.
    if (omarchy() / "shell.json").exists():
        registrar(omarchy() / "shell.json")


def quitar():
    plugins = omarchy() / "plugins"
    for nombre in (ID, VIEJO):
        if (plugins / nombre).exists():
            shutil.rmtree(plugins / nombre, ignore_errors=True)
            print(f"Widget de la barra quitado de {plugins / nombre}")
    desregistrar(omarchy() / "shell.json")


def main(argumentos=None):
    analizador = argparse.ArgumentParser(prog="widget.py", description=__doc__.splitlines()[0])
    sub = analizador.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("poner")
    p.add_argument("--lanzador", required=True, help="ruta absoluta de tareas-obsidian")
    p.add_argument("--forzar", action="store_true", help="aunque no haya Omarchy todavía")
    sub.add_parser("quitar")
    args = analizador.parse_args(argumentos)
    if args.accion == "poner":
        poner(args.lanzador, args.forzar)
    else:
        quitar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
