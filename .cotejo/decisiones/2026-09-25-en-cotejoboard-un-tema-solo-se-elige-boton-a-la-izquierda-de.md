---
id: dec-xme4
fecha: 2026-09-25
temas: []
estado: aceptada
autor: importado
---
# En CotejoBoard un tema solo se elige (botón ◐ a la izquierda de recargar, se aplica al…

En CotejoBoard un tema solo se elige (botón ◐ a la izquierda de recargar, se aplica al momento y queda como tema en la config). Crearlo y comprobarlo es de la CLI: cotejo temas, temas nuevo, temas comprobar (mide contraste WCAG), temas usar (se niega si no pasa).

**Por qué:** Un editor de colores en la interfaz es mucho código para algo que se hace una vez, y deja pasar temas ilegibles. Por CLI el agente recibe qué es cada token y qué par no llega, y un tema roto nunca llega a elegirse; como la app vigila la config, temas usar cambia también el board abierto.

**Descartado:** Editor de temas dentro del board; aceptar cualquier valor CSS como color (un tema podría colar una regla entera)
