---
id: pro-vjt4
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: escanear() recoge lo que no pudo leer en una lista opcional de avisos con la nota y el motivo; estado.escribir() devuelve el motivo del fallo; el resumen y el listado de tareas los traen, las dos ventanas los muestran en una banda ámbar bajo el encabezado y el widget los suma a su tooltip
---
# Una nota que Cotejo no podía leer desaparecía del board sin dejar rastro, y si no podía…

Una nota que Cotejo no podía leer desaparecía del board sin dejar rastro, y si no podía escribir estado.json la barra enseñaba el conteo de ayer para siempre

**Causa:** _leer() devolvía lista vacía ante un UnicodeDecodeError o un OSError, y estado.escribir() se tragaba el OSError. Las dos cosas eran silencios deliberados para que un archivo roto no tumbara la app, pero convertían un fallo en una ausencia, y una nota sin tareas se ve exactamente igual que una nota que no se pudo abrir

**Solución:** escanear() recoge lo que no pudo leer en una lista opcional de avisos con la nota y el motivo; estado.escribir() devuelve el motivo del fallo; el resumen y el listado de tareas los traen, las dos ventanas los muestran en una banda ámbar bajo el encabezado y el widget los suma a su tooltip
