---
id: pro-hoss
fecha: 2026-11-04
temas: [board, gtk]
estado: resuelto
solucion: Las opciones van dentro del ScrolledWindow con max_content_height en menu() de tareas/app/cartas.py (commit 6f522f0); pruebas/test_menu_carta.py lo vigila con 40 y 200 modelos. Tras instalar un release, reiniciar el board de fondo por su pid, nunca con pkill -f.
resuelto_el: 2026-11-04
---
# El menú de los 3 puntos de una carta no abre (detalle de pro-fave)

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

Es el mismo de pro-fave, con el detalle que vivía en «Bugs conocidos». Si vuelve a pasar: añade la fecha a «Veces», márcalo recurrente y busca por qué volvió (una prueba que lo vigile o la regla que faltaba) en vez de repetir el arreglo.

- **Veces:** 2026-09-26.
- **Síntoma:** clic en los 3 puntos (o tecla Menú) y no aparece nada, sin error.
- **Causa:** un `Gtk.Popover` que no cabe en la ventana GTK no lo muestra. La lista «ASIGNAR A»
  crece con cada modelo del catálogo (`agentes_disponibles()`, 34 ese día); si las opciones
  salen de su `Gtk.ScrolledWindow` en `menu()` de `tareas/app/cartas.py`, el popover se hace
  más alto que la ventana.
- **Arreglo:** las opciones van en la caja `agentes`, dentro del `ScrolledWindow` con
  `max_content_height` (commit `6f522f0`). Vale para cualquier lista del board que crezca con
  datos del usuario. `pruebas/test_menu_carta.py` lo vigila: construye el menú con 40 y con 200
  modelos y se pone roja si el alto cambia o pasa de 720 px (necesita pantalla; sin ella se salta).
- **Y el board publicado no lo verá hasta el siguiente release**, que es la mitad que engañó la
  primera vez: vive en segundo plano (`--fondo`) y cerrar la ventana no recarga el código.
  Para verlo antes, `cotejo-dev --board` desde el checkout con el arreglo. Después de instalar
  un release, el proceso de fondo se reinicia por su pid (`pkill -f` con el patrón en la línea
  de comandos se lleva por delante la propia shell que lo lanza):

```sh
ps -eo pid,lstart,args | grep '[t]areas --fondo'   # si arrancó antes del release, es el viejo
kill <pid>; setsid cotejo --fondo >/dev/null 2>&1 < /dev/null &
```
