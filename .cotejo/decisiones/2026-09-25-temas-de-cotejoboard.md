---
id: dec-x652
fecha: 2026-09-25
temas: []
estado: aceptada
autor: importado
---
# Temas de CotejoBoard

Temas de CotejoBoard: un tema es un JSON con 22 tokens de color con nombre de papel (fondo, superficie, texto, tenue, senal, sobre-senal…). Los de fábrica en data/temas/ (oscuro, claro); los de agentes en ~/.config/cotejo/temas/. El CSS de app.py no lleva ningún color literal.

**Por qué:** Un color con nombre de color (--k-blanco) miente en un tema claro, y un #FFFFFF suelto se ve bien en oscuro y deja algo invisible en claro. Con nombres de papel y cero literales (vigilado por pruebas/test_temas.py) un tema nuevo es solo un archivo, y el contraste WCAG se puede medir antes de usarlo.

**Descartado:** Mantener los nombres de la marca anterior (negro, grafito, plata, blanco); dos proveedores CSS con el :root repartido (depende del orden en que GTK los resuelva); guardar la elección en board.json (la CLI no podría cambiar el tema del board abierto)
