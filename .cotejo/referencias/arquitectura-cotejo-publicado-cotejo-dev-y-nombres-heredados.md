---
id: ref-98dq
temas: [arquitectura, pruebas]
resumen: pendiente
---
# Arquitectura · Cotejo publicado, cotejo-dev y nombres heredados de Foco

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

**El Cotejo instalado es la versión publicada, no este repo.** Desde el 2026-10-10 el dueño
usa Cotejo como un usuario más (el paquete del release) y aquí no se corre `./install.sh`: un
`master` a medias no puede dejarle sin sus tareas. El código del repo se prueba con
`cotejo-dev` (`herramientas/cotejo_dev.py`), que corre el código del checkout donde estés —el
repo o un worktree— con su propia config, estado y worktrees en `~/.local/state/cotejo-dev`,
sobre un vault de prueba (Faro y Horizonte) que crea la primera vez, y abre el board con otro
APP_ID, al lado del publicado. `COTEJO_VAULT=/ruta cotejo-dev …` apunta a otro vault en una sola
invocación. Lo que arreglas aquí llega al Cotejo de todos los días cuando sale en un release
(skill `cotejo-release`). El comando instalado se llama `cotejo`, y `foco` y `tareas-obsidian`
son el mismo programa con sus nombres de antes.

**El producto se llamó Foco hasta el 2026-09-26.** Lo que quedó de entonces sigue valiendo, a
propósito: los ids `foco-…` (las marcas del vault se migraron a `cotejo-…`, pero una evidencia,
un despacho o la bitácora los siguen nombrando así: `modelo.id_actual()` los traduce en
`buscar`, en `bitacora.ultimas()` y en `revisar`), las variables `FOCO_*` (`tareas/__init__.py`
las copia a `COTEJO_*` si faltan), la carpeta `~/.config/foco` si es la única
(`configuracion.carpeta()`), los comandos `foco` y `foco-notion`, y las skills y marcas `foco`
que `skill.py` limpia al instalar.
