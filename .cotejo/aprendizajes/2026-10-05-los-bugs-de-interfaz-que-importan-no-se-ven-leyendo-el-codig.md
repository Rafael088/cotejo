---
id: apr-3e99
fecha: 2026-10-05
temas: []
---
# Los bugs de interfaz que importan no se ven leyendo el código

Los bugs de interfaz que importan no se ven leyendo el código: los tres de esta sesión (Ctrl+F muerto, la columna recortada, el chip de persona con icono de modelo) aparecieron al abrir la app y usarla, y dos de ellos los introduje yo al implementar. Medir los widgets con `measure()` en vez de mirar capturas da la respuesta exacta —256 px contra 1202 px de ancho mínimo— y sirve igual cuando el compositor no deja redimensionar la ventana para probar.
