---
id: dec-pxtt
fecha: 2026-11-04
temas: [arquitectura, gtk]
estado: propuesta
autor: agente
---
# El núcleo no importa GTK: solo tareas/app/ (y el widget del dot) lo hace

Solo el paquete tareas/app/ importa GTK, y solo tareas/board.py importa tareas.app; la otra pieza de interfaz es tareas/dot_widget.py, que solo importa tareas/app/capa_dot.py. Dos puntos de entrada: cotejo → tareas.cli:main y cotejoboard → tareas.board:main.

**Por qué:** de ahí salen los 32 ms de --estado y es lo que deja empaquetar la CLI sola.

**Lo vigila:** pruebas/test_nucleo_sin_gtk.py, que corre cada verbo sin poder importar gi; un verbo nuevo sin fila en INVOCACIONES también la pone roja.

Sale de «Lo que no se cambia sin decisión consciente» del CLAUDE.md (texto completo en ref-62y4); se propone al acortarlo en cotejo-d9cbol porque no había decisión vigente que la recogiera.
