---
id: dec-vqhc
fecha: 2026-09-18
temas: []
estado: aceptada
autor: importado
---
# El medidor de ahorro mide las dos mitades en caracteres (lo que devolvió la CLI contra…

El medidor de ahorro mide las dos mitades en caracteres (lo que devolvió la CLI contra lo que pesaban las notas que la fuente leyó) y guarda el supuesto dentro del dato, en la clave supuesto

**Por qué:** Las dos mitades salen de datos que ya existían, así que contar no cuesta una segunda lectura. Lo único no medible —que sin Cotejo habrías leído esas notas enteras— viaja a la vista para que el número no pase por más de lo que es

**Descartado:** Estimar el ahorro como hasta ahora hacía el README; contar también las llamadas de estado, que las hace el widget de la barra sin que haya agente; guardarlo en bitacora.jsonl
