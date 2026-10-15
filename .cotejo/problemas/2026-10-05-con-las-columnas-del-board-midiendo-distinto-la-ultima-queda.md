---
id: pro-vd0w
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "El tablero va dentro de un `Gtk.ScrolledWindow` horizontal. El mínimo de cada columna se respeta y lo que no cabe se alcanza desplazando, en vez de dejar de existir. Medido con `measure()`: el mínimo de la ventana baja de 1202 px a 256 px"
---
# Con las columnas del board midiendo distinto, la última quedaba fuera de la pantalla y…

Con las columnas del board midiendo distinto, la última quedaba fuera de la pantalla y sin forma de llegar a ella en una ventana estrecha

**Causa:** Al pasar de `homogeneous=True` a anchos proporcionales, el mínimo del tablero subió a 970 px: la ventana no podía bajar de 1202 px sin recortar. Antes no pasaba porque las cuatro columnas encogían a la vez

**Solución:** El tablero va dentro de un `Gtk.ScrolledWindow` horizontal. El mínimo de cada columna se respeta y lo que no cabe se alcanza desplazando, en vez de dejar de existir. Medido con `measure()`: el mínimo de la ventana baja de 1202 px a 256 px
