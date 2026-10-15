---
id: dec-fsiy
fecha: 2026-09-17
temas: []
estado: aceptada
autor: importado
---
# En CotejoBoard el Tab salta de columna en columna, no de carta en carta, y las cartas…

En CotejoBoard el `Tab` salta de columna en columna, no de carta en carta, y las cartas pasan a ser filas de un `Gtk.ListBox`

**Por qué:** Las cartas eran `Gtk.Box` sin foco: el `Tab` solo paraba en los `⋮`, sin anillo visible, y parecía que el teclado no hacía nada. El ListBox hace enfocable cada carta y trae las flechas de fábrica; y con 60 pendientes, tabular una a una para llegar a la columna de al lado no lleva a ningún lado

**Descartado:** Cartas enfocables sueltas en un Box; recorrer todas las cartas con Tab
