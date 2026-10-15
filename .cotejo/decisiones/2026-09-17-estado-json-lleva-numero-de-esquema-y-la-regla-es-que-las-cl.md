---
id: dec-j012
fecha: 2026-09-17
temas: []
estado: aceptada
autor: importado
---
# estado.json lleva número de esquema, y la regla es que las claves se agregan pero nunca…

estado.json lleva número de esquema, y la regla es que las claves se agregan pero nunca se renombran ni se quitan

**Por qué:** Lo leen el widget QML de la barra y, desde la CLI de agentes, cualquiera desde fuera. Romper ese formato no da error en ningún sitio: simplemente el widget deja de contar y nadie se entera. Con el número, quien lo lee puede darse cuenta de que cambió

**Descartado:** Dejar el formato sin versionar y avisar a mano cuando cambie
