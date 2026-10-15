---
id: dec-q071
fecha: 2026-09-23
temas: []
estado: aceptada
autor: importado
---
# Los iconos de CotejoBoard se declaran con trazos y se emiten como contorno relleno…

Los iconos de CotejoBoard se declaran con trazos y se emiten como contorno relleno, generados por `data/iconos/generar.py`

**Por qué:** GTK, al cargar un icono simbólico, le fuerza el `fill` y descarta el `stroke`: una palomita de trazo llega a la pantalla como un triángulo macizo. Pero el recoloreado por CSS sí funciona, y es lo que permite que el mismo dibujo salga en plata dentro de un chip, en verde en la columna que espera y en ámbar en una devolución. Generarlos mantiene las dos cosas: se editan como trazos y se sirven como relleno

**Descartado:** Dibujar los 28 SVG a mano como contornos (imposible de editar después); cargarlos como archivo plano sin el canal simbólico (pierde el recoloreado por CSS, y con él los estados de hover); convertir el trazo con Inkscape (no está instalado)
