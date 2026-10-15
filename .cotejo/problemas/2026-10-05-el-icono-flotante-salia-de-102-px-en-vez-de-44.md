---
id: pro-aclo
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "`Gtk.Image` con `pixel_size`"
---
# El ícono flotante salía de 102 px en vez de 44

El ícono flotante salía de 102 px en vez de 44

**Causa:** `Gtk.Picture` con SVG pide el tamaño natural del archivo (100 px) aunque tenga `size_request`

**Solución:** `Gtk.Image` con `pixel_size`
