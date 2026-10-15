---
id: dec-0k4z
fecha: 2026-10-01
temas: []
estado: aceptada
autor: importado
---
# Con el paquete de pacman, el board corre usuario.sh solo (la primera vez y tras cada…

Con el paquete de pacman, el board corre usuario.sh solo (la primera vez y tras cada versión); la CLI nunca escribe en el HOME

**Por qué:** El paquete no puede tocar ningún HOME y el aviso se perdía en la salida de pacman; la CLI la llaman agentes sin parar, y escribir en el HOME de alguien se hace cuando esa persona abre la app

**Descartado:** Solo el mensaje post_install; que la CLI lo haga en cualquier verbo
