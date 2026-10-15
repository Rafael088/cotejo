---
id: pro-60gi
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "grid-template-columns: minmax(0,1fr) en .hero y min-width:0 en los contenedores; el comando se desplaza dentro de su caja"
---
# En móvil el hero de la web se salía de la pantalla (titular cortado)

En móvil el hero de la web se salía de la pantalla (titular cortado)

**Causa:** El comando en white-space:pre ensanchaba la columna de un grid con place-items:center, cuyo track crece al contenido

**Solución:** grid-template-columns: minmax(0,1fr) en .hero y min-width:0 en los contenedores; el comando se desplaza dentro de su caja
