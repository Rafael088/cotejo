"""Dónde guarda Cotejo sus cosas, en cada sistema operativo.

Dos carpetas y nada más:

- **la de config** (`config_base()`), de la que cuelgan `cotejo/config.json`, los temas y el
  token de Notion, y también la config de Obsidian, que usa la misma convención;
- **la de estado** (`estado()`), con lo que Cotejo escribe mientras trabaja: `estado.json`,
  `bitacora.jsonl`, `despachos.jsonl`, `ahorro.json` y `board.json`.

- Linux (y cualquier Unix): config en `$XDG_CONFIG_HOME` o `~/.config`; estado en
  `$XDG_STATE_HOME/tareas-obsidian` o `~/.local/state/tareas-obsidian`.
- macOS: config en `~/Library/Application Support`; estado en `…/Application Support/cotejo/estado`.
- Windows: config en `%APPDATA%`; estado en `%LOCALAPPDATA%\\cotejo\\estado`.

`COTEJO_ESTADO` apunta la de estado a otra carpeta en una sola invocación; la de config ya
tiene `COTEJO_CONFIG` (en `configuracion.ruta()`).

En Linux la carpeta de estado sigue llamándose `tareas-obsidian`, y es a propósito: el widget de
la barra lee `estado.json` de ahí, y `estado.json` es un contrato. En macOS y Windows no hay
nadie leyendo de una ruta vieja, así que llevan el nombre del producto.

Ninguna ruta se escribe a mano con el nombre de un usuario: todo sale de `Path.home()` o de las
variables que pone el sistema. No importa GTK, como el resto del núcleo.
"""

import os
import sys
from pathlib import Path

NOMBRE = "cotejo"
# La carpeta de estado en Linux, del tiempo en que el comando se llamaba así.
ESTADO_LINUX = "tareas-obsidian"


def sistema():
    """`windows`, `macos` u `otro` (Linux y demás Unix, que siguen XDG).

    Pública porque no es solo de rutas: el enrutador la usa para elegir con qué terminal se abre
    el maestro (`enrutador/config.py`), y es mejor un solo sitio que decida qué es cada sistema
    que uno por cada cosa que dependa de la plataforma.
    """
    if sys.platform.startswith(("win32", "cygwin")):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "otro"


def _entorno(nombre, defecto):
    valor = os.environ.get(nombre)
    return Path(valor) if valor else defecto


def config_base():
    """La carpeta donde cada app guarda su config, sin el nombre de ninguna app."""
    actual = sistema()
    if actual == "windows":
        return _entorno("APPDATA", Path.home() / "AppData" / "Roaming")
    if actual == "macos":
        return Path.home() / "Library" / "Application Support"
    return _entorno("XDG_CONFIG_HOME", Path.home() / ".config")


def estado():
    """La carpeta de lo que Cotejo escribe mientras trabaja."""
    desde_entorno = os.environ.get("COTEJO_ESTADO")
    if desde_entorno:
        return Path(desde_entorno).expanduser()
    actual = sistema()
    if actual == "windows":
        return _entorno("LOCALAPPDATA", Path.home() / "AppData" / "Local") / NOMBRE / "estado"
    if actual == "macos":
        return config_base() / NOMBRE / "estado"
    return _entorno("XDG_STATE_HOME", Path.home() / ".local" / "state") / ESTADO_LINUX


def datos_xdg():
    """`$XDG_DATA_HOME` o `~/.local/share`: donde otros programas (OpenCode) dejan sus datos.
    Cotejo no escribe ahí; `enrutador/modelos_vivos.py` solo mira si OpenCode tiene sesión."""
    return _entorno("XDG_DATA_HOME", Path.home() / ".local" / "share")


def obsidian():
    """El `obsidian.json` donde Obsidian apunta sus vaults: el primero de los que existan.

    Obsidian es una app de Electron y guarda su config donde toca en cada sistema; en Linux,
    además, la versión de Flatpak la guarda dentro de su caja. Si no hay ninguno, el normal.
    """
    candidatos = [config_base() / "obsidian" / "obsidian.json"]
    if sistema() == "otro":
        candidatos.append(Path.home() / ".var" / "app" / "md.obsidian.Obsidian" / "config"
                          / "obsidian" / "obsidian.json")
    return next((c for c in candidatos if c.exists()), candidatos[0])
