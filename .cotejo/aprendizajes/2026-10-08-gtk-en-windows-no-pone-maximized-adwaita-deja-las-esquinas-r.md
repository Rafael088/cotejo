---
id: apr-y6gb
fecha: 2026-10-08
temas: [windows, gtk, ui]
---
# GTK en Windows no pone .maximized: Adwaita deja las esquinas redondeadas a pantalla completa

En Windows, GTK no le añade la clase .maximized a la ventana maximizada o en pantalla completa, así que Adwaita dejaba el radio (~14 px) y la sombra y se veía el escritorio por las esquinas. Se arregló en tareas/app.py: el Board escucha notify::maximized y notify::fullscreened y se pone la clase propia .a-pantalla (--window-radius 0, sin sombra ni contorno). Se verificó en board-maximizada.png del run 36776293070, que tiene las 4 esquinas del color del board.
