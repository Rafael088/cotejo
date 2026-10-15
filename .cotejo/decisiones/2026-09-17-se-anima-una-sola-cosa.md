---
id: dec-dz1g
fecha: 2026-09-17
temas: []
estado: aceptada
autor: importado
---
# Se anima una sola cosa

Se anima una sola cosa: la entrada del tablero al cambiar de proyecto, y solo si gtk-enable-animations está activo

**Por qué:** La guía de UX consultada es explícita: uno o dos elementos animados por vista, y respetar la preferencia de movimiento del sistema. Animar cada repintado sería animar cada vez que se guarda una nota

**Descartado:** Transiciones en cada repintado; animar las cartas una por una
