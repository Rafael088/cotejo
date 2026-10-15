---
id: pro-zwz3
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Copia del `.desktop` en `~/.local/share/applications` con `Exec=/usr/bin/obsidian %U`
---
# Obsidian no abría desde el menú

Obsidian no abría desde el menú

**Causa:** `~/.local/bin/obsidian` (el CLI de Obsidian) tapaba a `/usr/bin/obsidian` en el PATH; el CLI solo funciona con la app abierta

**Solución:** Copia del `.desktop` en `~/.local/share/applications` con `Exec=/usr/bin/obsidian %U`
