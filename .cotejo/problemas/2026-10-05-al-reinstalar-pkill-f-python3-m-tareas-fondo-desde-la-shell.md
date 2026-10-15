---
id: pro-8heo
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Buscar el pid con pgrep (descartando la shell) y hacer kill <pid>; relanzar con setsid -f ~/.local/bin/cotejo --fondo en un comando aparte
---
# Al reinstalar, pkill -f 'python3 -m tareas --fondo' desde la shell de Claude cortó el…

Al reinstalar, pkill -f 'python3 -m tareas --fondo' desde la shell de Claude cortó el comando (exit 144) y Cotejo se quedó sin relanzar

**Causa:** pkill -f compara contra la línea de comandos entera, y la de la shell que ejecutaba el comando también contenía el patrón: se mató a sí misma

**Solución:** Buscar el pid con pgrep (descartando la shell) y hacer kill <pid>; relanzar con setsid -f ~/.local/bin/cotejo --fondo en un comando aparte
