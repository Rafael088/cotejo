---
id: pro-b21m
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: La acción `buscar` mira `get_active_window()` y enfoca la búsqueda del board si es el board, o abre la de CotejoList si no. El manejador que había puesto en la ventana era inalcanzable y se quitó
---
# En CotejoBoard, Ctrl+F no hacía nada, y es la tecla que el propio campo de búsqueda…

En CotejoBoard, Ctrl+F no hacía nada, y es la tecla que el propio campo de búsqueda lleva escrita al lado

**Causa:** `Ctrl+F` estaba registrado como acelerador de la aplicación apuntando a la barra de búsqueda de CotejoList. Los aceleradores de la aplicación se atienden antes que los controladores de tecla de la ventana, así que el board nunca veía la tecla

**Solución:** La acción `buscar` mira `get_active_window()` y enfoca la búsqueda del board si es el board, o abre la de CotejoList si no. El manejador que había puesto en la ventana era inalcanzable y se quitó
