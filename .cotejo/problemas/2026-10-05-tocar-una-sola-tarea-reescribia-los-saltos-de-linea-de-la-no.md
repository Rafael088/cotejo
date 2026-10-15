---
id: pro-rhw2
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Leer y escribir con newline='' en _reescribir, para que los saltos pasen tal cual. Una línea cambiada tiene que verse como una línea cambiada y no como un archivo reformateado, sobre todo si alguien versiona su vault
---
# Tocar una sola tarea reescribía los saltos de línea de la nota entera, de CRLF a LF

Tocar una sola tarea reescribía los saltos de línea de la nota entera, de CRLF a LF

**Causa:** Path.read_text() traduce los \r\n a \n al leer y write_text() los escribe como \n, así que el reemplazo atómico devolvía el archivo completo con otros saltos aunque solo hubiera cambiado una línea

**Solución:** Leer y escribir con newline='' en _reescribir, para que los saltos pasen tal cual. Una línea cambiada tiene que verse como una línea cambiada y no como un archivo reformateado, sobre todo si alguien versiona su vault
