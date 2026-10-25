"""Cotejo: las tareas de los proyectos del segundo cerebro, y quién las atiende.

Se llamó Foco, y sus variables de entorno eran `FOCO_*`. Una `FOCO_X` sigue valiendo mientras
no haya `COTEJO_X`: se copia aquí, al importar, que es antes de que nadie las lea, y así el
resto del código solo conoce el nombre nuevo.

`__version__` es la versión de Cotejo y la única: la leen `cotejo --version`, `cotejo doctor`,
`empaquetado/linux/construir.sh` y `empaquetado/windows/construir.py`. Se cambia aquí y en
ningún otro sitio (el `manifest.json` del widget de la barra la repite, y una prueba vigila
que no se separen).
"""

import os

__version__ = "1.2.6"

for _viejo, _valor in list(os.environ.items()):
    if _viejo.startswith("FOCO_"):
        os.environ.setdefault("COTEJO_" + _viejo[len("FOCO_"):], _valor)
