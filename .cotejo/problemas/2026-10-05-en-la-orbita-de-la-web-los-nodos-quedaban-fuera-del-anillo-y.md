---
id: pro-w2ci
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: position:absolute + translate:-50% -50% en el puesto; en móvil se oculta el anillo de agentes
---
# En la órbita de la web los nodos quedaban fuera del anillo y los radios no llegaban a…

En la órbita de la web los nodos quedaban fuera del anillo y los radios no llegaban a ellos

**Causa:** Cada puesto era una caja de 0x0 en grid: la esquina del nodo, no su centro, caía en el punto del anillo, y el desfase giraba con la órbita

**Solución:** position:absolute + translate:-50% -50% en el puesto; en móvil se oculta el anillo de agentes
