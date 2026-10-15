---
id: dec-v9vf
fecha: 2026-09-16
temas: []
estado: aceptada
autor: importado
---
# Al marcar, verificar que la línea siga igual antes de escribir, y escribir con archivo…

Al marcar, verificar que la línea siga igual antes de escribir, y escribir con archivo temporal + `os.replace`

**Por qué:** Si la nota se editó por fuera, no pisa nada: avisa y recarga. El reemplazo atómico evita dejar notas a medio escribir

**Descartado:** Escribir por número de línea a ciegas
