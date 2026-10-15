# El resumen de una entrega (`--resumen`)

`cotejo entregar` guarda, junto a la evidencia, un `--resumen` para quien **no programa**: la
persona que abre CotejoBoard, ve la tarea en «Para comprobar» y decide si la da por buena. La
evidencia es para quien revisa el código; el resumen, para quien revisa el resultado. Escríbelo
siempre, y en lenguaje de calle.

**Dos partes, en este orden:**

1. **Qué cambió visto desde fuera**: lo que alguien notaría usando el producto, no lo que tocaste.
2. **Cómo probarlo uno mismo**: los pasos que haría esa persona, con lo que debería ver.

**Sin jerga:** nada de nombres de archivos, funciones, ramas, commits ni «refactor», «endpoint»,
«parser». Si hace falta un término técnico, dilo con palabras de uso («la pantalla de inicio»,
«el botón Guardar»). No lo dejes vacío ni lo rellenes con «ver evidencia»: Cotejo rechaza el
vacío, y un resumen que remite a otro texto no resume nada. Si el cambio no se ve desde fuera,
dilo así y explica qué comprobar para confirmar que nada se rompió.

**Ejemplo:**

```sh
cotejo entregar <id> --evidencia "..." --prueba "python3 -m unittest discover pruebas" \
  --resumen "Ahora la lista de tareas se puede ordenar por fecha. Para probarlo: abre la lista, pulsa «Fecha» arriba a la derecha y comprueba que las más recientes salen primero."
```

Es opcional en la CLI (una entrega sin él funciona igual), pero tu trabajo no está bien entregado
sin él. En el MCP es el parámetro `resumen` de `entregar`.
