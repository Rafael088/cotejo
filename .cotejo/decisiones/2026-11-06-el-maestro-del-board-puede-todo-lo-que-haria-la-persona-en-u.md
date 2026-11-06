---
id: dec-qnug
fecha: 2026-11-06
temas: [maestro, enrutador]
estado: aceptada
autor: agente
reemplaza: dec-ku4d
aceptada_el: 2026-11-06
---
# El maestro del board puede todo lo que haría la persona en una terminal, menos aprobar

Pedido del dueño del 2026-11-06 (cotejo-va7lgn, v1.3.1). En el chat del board el maestro lee y edita el código, corre comandos, hace commits en ramas, crea, edita y asigna tareas, despacha y lanza agentes, entrega y bloquea, con cualquier cliente (Claude, Codex, OpenCode, Gemini, Antigravity) y sin que nadie conteste permisos (enrutador/conversacion.py, comando). Lo único vedado es aprobar: dar una tarea por hecha ([x] o por-integrar), integrar la rama cotejo/<id> de una tarea en la principal y aceptar una decisión propuesta. REPARTIR sigue como atajo del board.

Aprobar no se le confía al prompt: el candado (enrutador/candado.py) fotografía antes de cada turno lo aprobado y, al cerrarlo (también si muere o se para), devuelve por la fuente las tareas que pasaron a aprobadas, vuelve a propuesta las decisiones aceptadas (Almacen.deshacer_estado) y avisa, sin deshacer git, de un merge de cotejo/<id>. Lo deja en la respuesta del maestro y en la bitácora. Lo que aprueba la persona en el board durante el turno no se toca.

**También toca:** dec-7aqz (gastar lo decide una persona) en lo que respecta al maestro: asignar modelo y despachar ya no esperan a una persona cuando se lo piden al maestro en el chat; el pedido escrito en el chat es la persona decidiéndolo. Las guardas de despachar siguen (nivel humano sin --forzar, sin modelo se pregunta). Y dec-1wh6: lo que despache el maestro lanza agentes desde un mensaje del board, no solo por mover una carta.

**Por qué:** el dueño quiere que el maestro haga el trabajo y no solo lo proponga; lo que protege de verdad el proyecto es que nadie más que una persona dé por bueno el trabajo, y eso Cotejo lo puede comprobar fuera del agente.
