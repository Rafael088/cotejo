---
id: pro-vsxa
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Logo, un Gdk.Paintable propio que declara alto fijo (22 px) y ancho por proporción y dibuja la textura escalada; el SVG de la app a 4 veces el ancho mostrado para que se vea nítido con escala 2 (commit e244abf)
---
# Con el logo en la cabecera de CotejoBoard, la cabecera crecía a unos 260 px de alto y el…

Con el logo en la cabecera de CotejoBoard, la cabecera crecía a unos 260 px de alto y el logo no se veía

**Causa:** Un Gtk.Picture pide el tamaño natural de lo que pinta (el SVG rasterizado a su tamaño de archivo); set_size_request solo fija el mínimo, no el máximo

**Solución:** Logo, un Gdk.Paintable propio que declara alto fijo (22 px) y ancho por proporción y dibuja la textura escalada; el SVG de la app a 4 veces el ancho mostrado para que se vea nítido con escala 2 (commit e244abf)
