---
id: ref-wac6
temas: [cotejo, planning, v1.1, ax]
resumen: "Planning de la v1.1: tareas que viven en el repo, entrada por MCP desde cualquier cliente, un plan convertido en tareas sin copiarlas a mano, y revisión de lo entregado de un vistazo."
---
# Cotejo - Planning v1.1

# Cotejo — Planning v1.1

> [!abstract] En una frase
> La 1.0 sirve a quien tiene sus tareas en un vault de Obsidian. La 1.1 es para cualquiera que programa con agentes: las tareas viven **en el repo**, se entra por **MCP** desde cualquier cliente, un plan se convierte en tareas sin copiarlas a mano, y lo que entrega un agente se **revisa de un vistazo** sin pisarse con el trabajo de otros.

## De dónde sale

Brainstorming del 2026-10-02. Se miró [bible-strong-avatar-lab](https://github.com/smontlouis/bible-strong-avatar-lab) como referencia: local-first, sin cuentas, export portable en JSON y la lógica separada de la interfaz. Cotejo ya cumple las tres cosas. Lo que no cubre es dónde vive el trabajo de quien hace vibe coding (en el repo, no en un vault) ni el cuello de botella que aparece en cuanto hay varios agentes trabajando: **revisar lo que entregan**.

De las siete ideas que salieron se eligieron tres frentes:

| Frente | Qué resuelve | Ideas del brainstorming |
| --- | --- | --- |
| **A. Fuera de Obsidian** | Que lo pueda usar quien no tiene vault | Fuente repo + servidor MCP |
| **B. Revisar rápido y sin choques** | Que «Para comprobar» se revise de un vistazo y que dos agentes no se pisen | Evidencia verificable + worktree por despacho |
| **C. Del plan a las tareas** | Que un plan.md o un PRD se convierta en tareas con su dificultad | Importar plan |

Quedan para más adelante: el estado en vivo de cada agente (la idea de los avatares), el costo real por tarea e Issues de GitHub como fuente.

## Decisiones tomadas

> [!note] Ajuste del 2026-10-02
> Con el [[cotejo-planning-v1-2|Cotejo - Planning v1.2]], el conocimiento de cada proyecto pasa a vivir en `.cotejo/` dentro del repo. Las tareas de la 1.1 ya van ahí (`.cotejo/tareas.md`) para no tener que migrarlas en la 1.2, e `importar` pasa a ser `importar plan`.

| Pregunta | Decisión | Por qué |
| --- | --- | --- |
| Formato de las tareas en un repo | Un `.cotejo/tareas.md` (ajustado el 2026-10-02 por [[cotejo-planning-v1-2|Cotejo - Planning v1.2]]; antes un `TAREAS.md` en la raíz) con **la misma línea que en Obsidian** (`- [ ] texto #medio #agente/x ^cotejo-id`) | Se reutiliza el parser y la escritura verificada que ya existen y tienen pruebas; además el archivo se lee bien en GitHub y en cualquier editor |
| Qué es un proyecto en la fuente repo | Un repo = un proyecto. La config lista los repos (o una carpeta raíz donde buscarlos) | Así es como piensa quien programa; nada de jerarquías nuevas |
| Cómo se arranca en un repo | `cotejo init` crea `.cotejo/tareas.md` y registra el repo en la fuente | Un solo comando, que es lo que espera alguien que llega desde un README |
| Servidor MCP | `cotejo mcp` por stdio, **sin dependencias** (JSON-RPC a mano, como el resto del núcleo). Expone los mismos verbos que la CLI, y ninguno más | La CLI sigue siendo el contrato y MCP es otra puerta al mismo sitio. La prueba que vigila que no exista un verbo para finalizar tiene que cubrir también las tools de MCP |
| Evidencia | Además del texto libre, `entregar` guarda **evidencia estructurada**: rama, commits, resumen del diff y los comandos de prueba con su salida y código de salida | Revisar tiene que costar menos que hacer. Un texto que dice «pasan las pruebas» no se puede volver a comprobar |
| Volver a comprobar | `cotejo comprobar <id>` vuelve a correr los comandos de prueba de la evidencia en el worktree de la tarea y dice si sigue igual. No cambia el estado | Comprobar es leer; aprobar sigue siendo de la persona |
| Aislamiento | `despachar` crea por defecto un worktree con rama `cotejo/<id>` cuando la tarea es de un repo git | El `git add -A` del 2026-09-17 ya mostró lo que pasa cuando dos agentes comparten árbol |
| Integrar | El botón **Aprobar** del board (solo la persona) finaliza la tarea y ofrece integrar la rama; la CLI no gana ningún verbo para finalizar ni para integrar | Se mantiene la regla de que la transición a hecha es de la persona |
| Importar un plan | `cotejo importar plan <plan.md> --proyecto X` (subcomando: en la 1.2 llega `importar obsidian\|notion`) es un **ensayo por defecto**: lista las tareas que crearía, con la dificultad y el modelo que propone el enrutador. Solo escribe con `--aplicar` | Mismo reparto que en todo lo demás: el agente propone y la persona elige |
| Qué cuenta como tarea en un plan | Las casillas `- [ ]` y, si no hay ninguna, los encabezados de paso (`## Paso N`, `### Tarea N`) | Cubre los formatos de plan más comunes (superpowers writing-plans, PRD con checklist) sin inventarse tareas |

## Orden

1. **A1 → A2**: primero la fuente repo y `init`, porque todo lo demás (worktrees, evidencia de git) da por hecho que la tarea vive en un repo.
2. **B1 → B2 → B3 → B4**: evidencia estructurada, comprobar, worktree por despacho y la vista de revisión en el board.
3. **A3 (MCP)** cuando los verbos nuevos (`init`, `comprobar`, `importar`) estén quietos, para no exponer un contrato que todavía se mueve.
4. **C1** puede ir en paralelo desde el principio: solo depende de `crear` y de `decidir`, que ya existen.
5. Cierre: skill, docs, release 1.1.0.

## Riesgos

- **Windows y los worktrees.** Las rutas largas y Git Bash ya dieron guerra con MSYSTEM. Hay que probar `despachar` con worktree en el runner de windows.yml.
- **Correr comandos de la evidencia.** `comprobar` ejecuta lo que escribió un agente. Solo se corren los comandos que el propio agente registró en su entrega, dentro del worktree, con tiempo límite y nunca con el shell de la persona como intermediario.
- **Dos fuentes a la vez.** Hoy solo hay una fuente activa. Quien tenga el vault y también repos va a querer ver las dos cosas. Por ahora no entra en la 1.1: queda anotado como pregunta abierta.

## Preguntas abiertas

- ~~¿Fuente compuesta (vault + repos a la vez) en la 1.1 o en la 1.2?~~ **Decidido el 2026-10-03: fuera de la 1.1.**
- ~~¿La vista de revisión muestra el diff completo dentro del board o lo abre en la herramienta de diff del sistema?~~ **Decidido el 2026-10-03: las dos.** Dentro del board, el resumen (archivos con +/− y barra proporcional) y el diff unificado por archivo, plegable, con color por línea en GTK4 + Adwaita sin GtkSourceView (sin resaltado de sintaxis, para no sumar dependencias ni DLL en Windows). Para cambios grandes, un botón «Abrir en herramienta» que lanza `git difftool` con la herramienta de la persona.
- ~~¿Issues de GitHub como fuente externa (con `gh`) entra en la 1.1 o espera?~~ **Decidido el 2026-10-03: espera, no entra en la 1.1.**
