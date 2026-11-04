---
id: dec-kiik
fecha: 2026-10-23
temas: [agentes, seguridad, board]
estado: aceptada
autor: agente
aceptada_el: 2026-10-23
---
# Agente del board: terminal libre en su worktree con prohibidos de fábrica

El dueño eligió (2026-10-24) que el agente que lanza el board tenga terminal libre dentro del worktree de su tarea, para que pueda correr pruebas y builds sin configurar nada; la seguridad la dan el worktree y la rama propios (nada llega a main sin merge de la persona) y una lista corta de prohibidos de fábrica: sudo/su, git push --force, push a la rama por defecto y borrar fuera del worktree. Descartado: solo cotejo y git (el agente entregaría sin probar) y una lista de permitidos por proyecto (configuración que quien no programa no sabría escribir).
