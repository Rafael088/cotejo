---
id: pro-19an
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: "Recorrer el árbol de widgets: son `.header .heading` y `.header .body`"
---
# Los títulos de proyecto no tomaban Sora ni Plex Mono

Los títulos de proyecto no tomaban Sora ni Plex Mono

**Causa:** Los selectores `.title` / `.description` no existen en `AdwPreferencesGroup`

**Solución:** Recorrer el árbol de widgets: son `.header .heading` y `.header .body`
