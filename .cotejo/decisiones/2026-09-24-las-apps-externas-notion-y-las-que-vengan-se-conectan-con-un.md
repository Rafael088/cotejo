---
id: dec-h1bx
fecha: 2026-09-24
temas: []
estado: aceptada
autor: importado
---
# Las apps externas (Notion y las que vengan) se conectan con un adaptador aparte, por…

Las apps externas (Notion y las que vengan) se conectan con un adaptador aparte, por subproceso y JSON, que solo implementa primitivas: escanear, estado, agente, marcar, crear; toda escritura lleva --esperado

**Por qué:** Las reglas del trabajo (evidencia obligatoria al entregar, motivo al bloquear, bitácora) siguen en un solo sitio, cli.py; si cada adaptador tuviera su entregar, cada uno validaría distinto y la evidencia acabaría en la app de fuera. --esperado da la misma garantía que Obsidian: no pisar una tarea que alguien cambió

**Descartado:** Adaptador con tomar/entregar/bloquear/asignar (lo que decía el planning); módulos Python dentro de tareas/fuentes; hablar con Notion por su MCP
