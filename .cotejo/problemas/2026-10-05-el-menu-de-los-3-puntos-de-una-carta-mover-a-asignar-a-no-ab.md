---
id: pro-fave
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Opciones de modelos dentro de un Gtk.ScrolledWindow (max 320 px) en menu() de tareas/app.py (commit 6f522f0); ./install.sh y reiniciar el proceso de fondo. Si vuelve a pasar: marcarlo como bug recurrente (ver CLAUDE.md del repo, Bugs conocidos)"
---
# El menú de los 3 puntos de una carta (MOVER A / ASIGNAR A) no abría en CotejoBoard

El menú de los 3 puntos de una carta (MOVER A / ASIGNAR A) no abría en CotejoBoard

**Causa:** Con el catálogo de modelos la lista ASIGNAR A pasó de 30 opciones (34); el popover no cabía en la ventana y GTK no lo mostraba. La caja con scroll existía pero las opciones no entraban en ella. Además el arreglo no se veía: el board sigue vivo con --fondo y cerrar la ventana no recarga el código

**Solución:** Opciones de modelos dentro de un Gtk.ScrolledWindow (max 320 px) en menu() de tareas/app.py (commit 6f522f0); ./install.sh y reiniciar el proceso de fondo. Si vuelve a pasar: marcarlo como bug recurrente (ver CLAUDE.md del repo, Bugs conocidos)
