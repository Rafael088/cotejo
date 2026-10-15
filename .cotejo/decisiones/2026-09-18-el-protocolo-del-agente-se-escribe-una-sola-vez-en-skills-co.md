---
id: dec-l4c2
fecha: 2026-09-18
temas: []
estado: aceptada
autor: importado
---
# El protocolo del agente se escribe una sola vez en skills/cotejo/SKILL.md y se reparte…

El protocolo del agente se escribe una sola vez en skills/cotejo/SKILL.md y se reparte desde ahí: copia nativa a Claude Code y Codex, bloque entre marcas a Gemini CLI y opencode, y el verbo tareas-obsidian protocolo para cualquiera con terminal

**Por qué:** Dos copias del protocolo acaban contradiciéndose, y la que se pudre sin que nadie lo note es justo la que lee el agente. Con una sola fuente, pruebas/test_skill.py puede ponerse roja si nombra un verbo que ya no existe

**Descartado:** Repetirlo en el README; un AGENTS.md por repositorio; dejar que cada agente lo deduzca del --help
