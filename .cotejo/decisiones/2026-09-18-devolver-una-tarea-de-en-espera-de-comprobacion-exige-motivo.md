---
id: dec-1x7s
fecha: 2026-09-18
temas: []
estado: aceptada
autor: importado
---
# Devolver una tarea de En espera de comprobación exige motivo, y el board no deja…

Devolver una tarea de En espera de comprobación exige motivo, y el board no deja confirmar en vacío

**Por qué:** Es la simétrica de la evidencia obligatoria al entregar. Un rechazo mudo deja al agente exactamente donde estaba: vuelve a entregar lo mismo, y la columna se convierte en un ciclo infinito. El motivo viaja de vuelta en el JSON de tareas y de tomar, que es donde el agente lo va a leer antes de rehacerla

**Descartado:** Motivo opcional; rechazar con un comentario suelto en la nota
