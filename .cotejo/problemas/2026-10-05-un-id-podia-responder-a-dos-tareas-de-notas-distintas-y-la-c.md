---
id: pro-0wed
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: buscar() junta todas las coincidencias y lanza IdAmbiguo si hay más de una, nombrando las notas; la CLI lo traduce a un error que dice qué hacer y no escribe nada. Además las marcas pasaron de cuatro caracteres a seis
---
# Un id podía responder a dos tareas de notas distintas y la CLI habría escrito en la…

Un id podía responder a dos tareas de notas distintas y la CLI habría escrito en la primera que encontrara

**Causa:** Las marcas se generan comprobando que no se repitan dentro de la nota, pero buscar() recorre todas las notas del vault y devolvía la primera coincidencia. Comprobar la unicidad global obligaría a releer el vault entero en cada escritura

**Solución:** buscar() junta todas las coincidencias y lanza IdAmbiguo si hay más de una, nombrando las notas; la CLI lo traduce a un error que dice qué hacer y no escribe nada. Además las marcas pasaron de cuatro caracteres a seis
