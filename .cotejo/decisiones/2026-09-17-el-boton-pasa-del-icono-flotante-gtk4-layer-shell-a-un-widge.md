---
id: dec-wsc0
fecha: 2026-09-17
temas: []
estado: aceptada
autor: importado
---
# El botón pasa del ícono flotante (gtk4-layer-shell) a un widget propio de la barra de…

El botón pasa del ícono flotante (gtk4-layer-shell) a un widget propio de la barra de Omarchy (cotejo.barra)

**Por qué:** El ícono flotaba encima de las ventanas maximizadas y competía con ellas por el espacio; la barra ya es el sitio donde vive el estado del sistema y no tapa nada. De paso desaparece la dependencia de gtk4-layer-shell y el LD_PRELOAD del lanzador

**Descartado:** Dejar el ícono flotante; ícono en la bandeja del sistema
