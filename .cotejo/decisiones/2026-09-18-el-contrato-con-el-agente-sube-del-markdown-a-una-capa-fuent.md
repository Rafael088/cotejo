---
id: dec-gymf
fecha: 2026-09-18
temas: []
estado: aceptada
autor: importado
---
# El contrato con el agente sube del Markdown a una capa Fuente

El contrato con el agente sube del Markdown a una capa Fuente: modelo.py (qué es una tarea), fuente.py (la interfaz) y fuentes/obsidian.py (el único que sabe de notas y tags)

**Por qué:** Mientras «la tarea está en curso» significara «hay un #en-curso en su línea», Cotejo solo servía para un vault de Obsidian con 01-Proyectos/, y cada segundo cerebro nuevo era un contrato nuevo y un agente que reprogramar. Con la interfaz en medio, Logseq, una carpeta de Markdown pelada o Todoist son adaptadores de cuatro métodos. Se hizo ahora y no antes porque abstraer antes de saber qué verbos aguantan es abstraer la forma equivocada: los verbos ya estaban probados contra Obsidian

**Descartado:** Dejar los tags como contrato y escribir un MCP por cada fuente; un adaptador por fuente copiando vault.py entero
