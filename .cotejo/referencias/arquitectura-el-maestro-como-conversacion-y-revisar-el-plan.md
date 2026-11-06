---
id: ref-imu9
temas: [arquitectura, maestro]
resumen: pendiente
---
# Arquitectura · El maestro como conversación y Revisar el plan

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

`enrutador/conversacion.py` es **el maestro como conversación** (v1.3.0, cotejo-9ybn1a). La
barra del pie (`tareas/app/maestro.py`) le manda lo que escribe la persona a
`verbos.hablar_maestro` → `apertura.hablar`, que arma el turno (`apertura.armar`: proyecto,
pendientes asignadas, carpeta de `fuente.carpeta_de`, instrucción con la conversación de
`maestro.instruccion`) y lo lanza sin interfaz por `motores/fondo.lanzar_aparte` (stdout y stderr
aparte: la respuesta de Codex es su stdout). La conversación de cada proyecto vive en
`<estado>/maestro/<proyecto>.json` y viaja entera, recortada (`TURNOS_DE_MEMORIA`), en cada turno:
no todos los clientes documentan cómo retomar su sesión sin interfaz. Un hilo espera el turno, lo
anota con lo que propuso repartir y el board repinta y refresca (lo apuntado sale en el tablero);
un turno con el proceso muerto se cierra al leer. Antes de armar la instrucción,
`tareas/ramas_pendientes.py` compara las ramas `cotejo/*` de las tareas del proyecto con `HEAD` y
le da al maestro las que aún tienen commits fuera, con su columna y el motivo correspondiente.
Así una app vacía no se confunde con trabajo inexistente ni se manda rehacer lo que espera
entrega, aprobación o integración. Las ramas históricas sin tarea en ese tablero no se mezclan.
Permisos por cliente en `conversacion.comando` (v1.3.1, cotejo-va7lgn, dec-qnug): todo lo que
haría la persona en una terminal, sin preguntar, en la carpeta del código (o la de las tareas si
no hay código). Claude `--permission-mode bypassPermissions` y `--setting-sources user`; Codex
`--dangerously-bypass-approvals-and-sandbox` sin confianza en el proyecto; OpenCode `edit`, `bash`
y `webfetch` en `allow`, sin MCP ni plugins del proyecto; Gemini `--approval-mode yolo` y sin lo
de su `.gemini/`; Antigravity `--dangerously-skip-permissions`, ya sin bwrap. Todos con el mismo
`cotejo` del board y la config sin vedar. Lo único vedado, aprobar, lo hace cumplir
`enrutador/candado.py`: `conversacion.empezar` guarda en el turno una foto de lo aprobado (tareas
hechas o por integrar, estado de las decisiones del `.cotejo/`, ramas principales y `cotejo/*`), y
`conversacion._cerrar` (al terminar, al pararlo o al cerrar un turno muerto) devuelve por la fuente
las tareas que pasaron a aprobadas, vuelve a propuesta las decisiones aceptadas
(`Almacen.deshacer_estado`), avisa sin tocar git de un merge de `cotejo/<id>` y lo añade a la
respuesta y a la bitácora. Lo que aprueba la persona en el board durante el turno se apunta en
`candado.lo_aprueba_la_persona` (movimientos, integrar, `decision.aceptar`) y no se deshace.
`pruebas/test_candado_maestro.py` lo prueba de punta a punta. El panel
(`tareas/app/conversacion.py`, `PanelMaestro`) flota en el overlay del tablero (cotejo-w8vteb):
no ocupa sitio en la caja, así que abrirlo no empuja ni redimensiona las columnas; se arrastra
por su título, se minimiza y se cierra sin parar al maestro. «Repartir» va
por `mover`. La CLI es la misma: `cotejo maestro --proyecto X --pedido "…"` espera la respuesta.
`pruebas/test_maestro_conversacion.py` (sin GTK) y `pruebas/test_barra_maestro.py` (board de
verdad) lo prueban de punta a punta con `cliente_falso.py`.

`tareas/revisar_plan.py` es «Revisar el plan» (v1.3.0, cotejo-m195bn), sin GTK; la pinta
`tareas/app/revisar_plan.py`, una página más de la pila (`"plan"`) a la que lleva el botón de
Preparando (`Board.revisar_plan(estado)`). Enseña objetivo y siguiente paso (de `proyecto.md`),
las decisiones y las tareas de la 0.1.0 con quién las haría según el enrutador (las del nivel
humano, «tú»). **Aceptar** es `decision.aceptar`; **Cambiar** es `decision.rechazar` con motivo
obligatorio (estado `rechazada`, que ya no cuenta como vigente) y relanza la misma preparación
con `preparar.rehacer` y el prompt de `inicio.armar_rehacer`, de vuelta a Preparando. Las dos
son de la persona, sin verbo de CLI. **Empezar la 0.1.0** reparte como `cotejo plan`: a lo
pendiente sin dueño le pone el modelo propuesto (o `persona`), sin lanzar nada, y abre el
mapa del proyecto (`abrir_proyecto` con la carpeta). Lee y escribe con la fuente repo
apuntada solo a esa carpeta.
