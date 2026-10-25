"""La escala de Windows que GTK no le da al board (cotejo-x968aw).

GTK en Windows solo escala por enteros: calcula `DPI / 96` con división entera, así que una
pantalla al 125, 150 o 175 % —lo normal en un portátil— se queda en 1 y el board se dibuja
al 100 %. Y lo que se dibuja no sigue al DPI de ninguna otra forma: el CSS escribe la letra en
`px`, que GTK no toca con `gtk-xft-dpi` (solo los `pt`). Resultado: letras de 11 y 12 px
reales en una pantalla que Windows trata como de 150 %, que es lo que contaban los usuarios.

Lo que falta se pone aquí: `factor` es lo que le queda por escalar a GTK (el DPI real del
monitor entre 96, dividido por la escala que GTK ya aplicó) y se multiplica en los `px` del
CSS y en el tamaño de los iconos. Para que el DPI sea el del monitor donde está la ventana, y
no el del sistema al iniciar sesión, el lanzador pone `GDK_WIN32_PER_MONITOR_HIDPI`; la app
mira cada segundo si la ventana cambió de monitor y, si el factor cambia, recarga el CSS y
reescala los iconos.

La letra que no es nuestra (la de Adwaita: entradas, diálogos, botones) va en `pt` y la escala
`gtk-xft-dpi`. GTK lo pone solo en el modo de un DPI para todo el sistema (`dpi * 1024 /
escala`, `gdkwin32misc.c`); en el modo por monitor no lo pone, y sin `poner_dpi_de_letra`
esa letra se quedaría al 100 %.

Fuera de Windows el factor es siempre 1: en Linux la escala fraccionaria la resuelve el
compositor, y ahí no hay nada que tocar. `COTEJO_ESCALA=1.5` lo fija a mano en cualquier
sistema: para ver aquí cómo queda el board en Windows, o para corregirlo allá si Windows
contesta un DPI que no es.
"""

import os
import re
import sys

DPI_BASE = 96

# El factor con el que se crean los iconos de ahora en adelante. Lo cambia `App` cuando cambia
# el del monitor; `piezas.icono` lo lee al crear cada uno.
FACTOR = 1.0

# Un número seguido de `px`, que no sea parte de otra palabra (`-gtk-…`) ni de otro número.
_PX = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)px\b")


def calcular_factor(dpi, escala_gtk=1):
    """Lo que GTK no escaló: `dpi / 96 / escala_gtk`, con dos decimales y nunca menos de 1.

    Sin DPI (fuera de Windows, o si no se pudo preguntar) es 1: mejor el board de siempre que
    uno a una escala inventada.
    """
    if not dpi or dpi <= 0:
        return 1.0
    factor = round(dpi / DPI_BASE / max(1, escala_gtk or 1), 2)
    return factor if factor > 1 else 1.0


def forzado():
    """El factor de `COTEJO_ESCALA`, o None si no está o no tiene sentido (fuera de 0,5 a 4)."""
    try:
        factor = float(os.environ.get("COTEJO_ESCALA", ""))
    except ValueError:
        return None
    return factor if 0.5 <= factor <= 4 else None


def escalar_css(css, factor):
    """El CSS con cada medida en `px` multiplicada por `factor`.

    Las de 1 px o menos se quedan: son bordes y separadores, y un borde de 1,5 px sale borroso
    en vez de más visible.
    """
    if factor == 1:
        return css

    def escalar(m):
        valor = float(m.group(1))
        if abs(valor) <= 1:
            return m.group(0)
        return f"{round(valor * factor, 2):g}px"

    return _PX.sub(escalar, css)


def tamano(base):
    """Un tamaño en px (un icono) a la escala de ahora."""
    return max(1, round(base * FACTOR))


def dpi_de_letra(factor, original=None):
    """El `gtk-xft-dpi` que corresponde a `factor`: el de GTK en Windows (`96 * factor`, en
    1024avos), o `original` escalado donde ya había uno (Linux con `COTEJO_ESCALA`)."""
    base = original if original and original > 0 and sys.platform != "win32" else DPI_BASE * 1024
    return round(base * factor)


def reescalar_iconos(raiz):
    """Pone a la escala de ahora cada icono de `raiz` y de lo que cuelga de ella.

    Solo los que creó `piezas.icono`, que apuntan su tamaño sin escalar en `cotejo_tamano`.
    """
    pendientes = [raiz]
    while pendientes:
        widget = pendientes.pop()
        base = getattr(widget, "cotejo_tamano", None)
        if base is not None:
            widget.set_pixel_size(tamano(base))
        hijo = widget.get_first_child()
        while hijo is not None:
            pendientes.append(hijo)
            hijo = hijo.get_next_sibling()


# --- preguntarle a Windows ------------------------------------------------------------------

def dpi_de(superficie):
    """El DPI del monitor donde está `superficie`, o None fuera de Windows o si no se pudo.

    Sin superficie todavía (la ventana aún no existe) es el del sistema: el del monitor
    principal, que es donde se abre casi siempre.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = _hwnd(superficie) if superficie is not None else None
        if hwnd:
            dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd))
            if dpi:
                return dpi
        return user32.GetDpiForSystem() or None
    except (AttributeError, ImportError, OSError, ValueError):
        # Un Windows sin GetDpiForWindow (anterior a 10 1607) o sin la typelib de GdkWin32.
        return None


def _hwnd(superficie):
    import gi
    gi.require_version("GdkWin32", "4.0")
    from gi.repository import GdkWin32
    return GdkWin32.Win32Surface.get_handle(superficie)
