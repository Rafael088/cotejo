---
id: dec-2fnm
fecha: 2026-09-18
temas: []
estado: aceptada
autor: importado
---
# install.sh solo deja el protocolo en los agentes que ya están instalados en la máquina…

install.sh solo deja el protocolo en los agentes que ya están instalados en la máquina, y en un archivo ajeno escribe siempre entre las marcas cotejo:inicio y cotejo:fin, con copia .bak

**Por qué:** Crear un ~/.gemini para quien no usa Gemini deja basura, y sobrescribir el AGENTS.md de alguien le borra sus propias instrucciones: dos maneras de fallar en silencio en la casa del usuario

**Descartado:** Escribir en todas las rutas conocidas por si acaso; anexar al final sin marcas, que duplica el bloque en cada reinstalación
