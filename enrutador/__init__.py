"""Quién atiende cada tarea de Cotejo: modelos configurados y una persona.

Cotejo resolvió *qué* hay que hacer. Esto resuelve *quién lo hace*, y vive aquí dentro porque
las dos preguntas son de la misma tarea: el enrutador lee las tareas de Cotejo, las toma a
nombre de quien las va a hacer y no sabe hacer nada más.

El paquete no importa GTK, igual que `tareas/cli.py`: un agente que pregunta a quién le toca
una tarea no debe pagar el arranque de la ventana.
"""
