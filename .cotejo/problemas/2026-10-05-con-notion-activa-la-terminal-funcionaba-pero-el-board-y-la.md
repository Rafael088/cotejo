---
id: pro-ydn6
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: cotejo-notion lee también ~/.config/cotejo/notion.token (600) cuando la variable no está (aab32bc)
---
# Con Notion activa, la terminal funcionaba pero el board y la barra no encontraban el token

Con Notion activa, la terminal funcionaba pero el board y la barra no encontraban el token

**Causa:** El token estaba como variable universal de fish, y Hyprland y Quickshell no pasan por fish

**Solución:** cotejo-notion lee también ~/.config/cotejo/notion.token (600) cuando la variable no está (aab32bc)
