"""CotejoBoard: la interfaz de Cotejo, lo único que importa GTK.

Antes era un solo `app.py` que llegó a 3.700 líneas en tres semanas. Ahora cada parte del
board vive en su módulo, y `Board` (`ventana.py`) las junta como mezclas: cada mezcla es una
clase con los métodos de una parte (la banda, las columnas, la revisión…) que se usan desde
`self` igual que antes. Dónde va cada cosa:

- `comun.py`: constantes, medidas, funciones sin widgets y `board.json`.
- `piezas.py`: widgets sueltos que usa más de una parte (icono, chip, vacío, logo…).
- `estilo.py`: el CSS, sin un color.
- `ventana.py`: `Board`, la cabecera, la búsqueda, los temas y `pintar`.
- Una mezcla por parte: `banda`, `columnas`, `cartas`, `detalle`, `decisiones`,
  `vista_revision`, `teclado`, `movimientos`, `maestro`, `pie`, `capa_dot`, y
  `pestana_inicio` (las pestañas Inicio | Tablero y lo que se pinta en Inicio).
- `constelacion.py`: el widget de la constelación de proyectos del Inicio (no es una mezcla).
- `aplicacion.py`: `App` y `main`.

Algo nuevo va en la parte a la que pertenece, o en un módulo nuevo si no es de ninguna; nunca
en `ventana.py` por comodidad. `pruebas/test_tamano_de_modulos.py` se pone roja si un módulo
pasa del tope.

`board.json` se lee y se escribe por el módulo (`comun.guardar_board(...)`), no con el nombre
importado suelto, para que una prueba lo cambie en un solo sitio.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from .aplicacion import App, main  # noqa: E402
from .ventana import Board  # noqa: E402

__all__ = ["App", "Board", "main"]
