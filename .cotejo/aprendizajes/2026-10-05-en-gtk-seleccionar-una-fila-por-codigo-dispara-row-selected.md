---
id: apr-vk7k
fecha: 2026-10-05
temas: []
---
# En GTK, seleccionar una fila por código dispara row-selected igual que un clic

En GTK, seleccionar una fila por código dispara row-selected igual que un clic. Si el repintado selecciona, hay que bloquear el manejador durante la selección o la vista se pinta dos veces y se anima cuando nadie tocó nada.
