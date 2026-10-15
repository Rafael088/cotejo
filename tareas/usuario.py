"""Lo que Cotejo pone en el $HOME de cada usuario, y si ya está puesto.

Un paquete del sistema (pacman, en /usr) no puede tocar el $HOME de nadie: el protocolo en los
agentes, el widget de la barra de Omarchy y la mudanza de la config vieja los pone
`<destino>/linux/usuario.sh`, una vez por usuario. Antes había que correrlo a mano, y el aviso
se perdía en la salida de pacman: en una instalación limpia el widget no aparecía nunca
(cotejo-8ecldw).

Ahora `usuario.sh` deja escrito al terminar qué versión puso y con qué opciones
(`<estado>/usuario.json`), y con eso:

- el board, al arrancar, lo corre solo si falta o si es de otra versión (el Widget.qml puede
  cambiar al actualizar), con las mismas opciones que se eligieron la vez anterior;
- `cotejo doctor` lo dice, con el comando, si falta o si el widget no está en la barra.

La CLI no lo corre por su cuenta: la llaman los agentes cien veces al día, y escribir en el
$HOME de alguien es algo que se hace cuando esa persona abre la app, no de rebote.

Fuera de Linux, o corriendo desde el repo (sin `<destino>/linux/usuario.sh` al lado), no hay
nada que hacer: en Windows lo hace el instalador.
"""

import json
import sys
from pathlib import Path

from . import __version__, rutas

DESTINO = Path(__file__).resolve().parent.parent


def archivo():
    return rutas.estado() / "usuario.json"


def script():
    """El `usuario.sh` de esta instalación, o None si no hay (repo, Windows, macOS)."""
    ruta = DESTINO / "linux" / "usuario.sh"
    return ruta if sys.platform.startswith("linux") and ruta.is_file() else None


def leer():
    """Lo que dejó escrito `usuario.sh` la última vez, o None."""
    try:
        datos = json.loads(archivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def opciones(datos):
    """Las opciones con que se corrió la última vez, para repetirlas al actualizar."""
    if not datos:
        return []
    salida = []
    if datos.get("widget") == "no":
        salida.append("--sin-widget")
    if datos.get("agentes") is False:
        salida.append("--sin-agentes")
    return salida


def hace_falta():
    """¿Hay que correr `usuario.sh` ahora? Devuelve el argv para hacerlo, o None.

    Falta si nunca se corrió en este usuario, o si lo que puso es de otra versión. Si alguien
    lo quitó (`usuario.sh --quitar`), no se vuelve a poner solo.
    """
    ruta = script()
    if ruta is None:
        return None
    datos = leer()
    if datos and (datos.get("quitado") or datos.get("version") == __version__):
        return None
    return ["sh", str(ruta), *opciones(datos)]


def widget_puesto():
    return (rutas.config_base() / "omarchy" / "plugins" / "cotejo.barra" / "Widget.qml").is_file()


def revisar():
    """Para `doctor`: lo que le falta a este usuario, con el comando que lo arregla."""
    ruta = script()
    if ruta is None:
        return {"aplica": False}
    datos = leer()
    informe = {"aplica": True, "script": str(ruta), "puesto": bool(datos),
               "version": (datos or {}).get("version"), "avisos": []}
    if datos and datos.get("quitado"):
        informe["avisos"].append(f"Lo de este usuario se quitó a propósito. Para volver a "
                                 f"ponerlo: sh {ruta}")
        return informe
    if not datos:
        informe["avisos"].append(f"Falta lo de este usuario (protocolo de los agentes y widget "
                                 f"de Omarchy). Se pone solo al abrir el board, o ahora con: "
                                 f"sh {ruta}")
    elif datos.get("version") != __version__:
        informe["avisos"].append(f"Lo de este usuario es de la {datos.get('version')} y Cotejo es "
                                 f"la {__version__}. Se pone al día al abrir el board, o ahora "
                                 f"con: sh {ruta}")
    hay_omarchy = (rutas.config_base() / "omarchy").is_dir()
    informe["widget"] = widget_puesto()
    if hay_omarchy and not informe["widget"] and (datos or {}).get("widget") != "no":
        informe["avisos"].append(f"Hay Omarchy pero el widget de Cotejo no está en la barra. "
                                 f"Ponlo con: sh {ruta} --widget")
    return informe
