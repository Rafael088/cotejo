---
id: arq-lfay
temas: [arquitectura]
actualizado: 2026-11-04
---
# Arquitectura de Cotejo

Cotejo tiene dos caras sobre el mismo núcleo en Python: el CLI `cotejo` (lo que usan los agentes: `tareas/`, `enrutador/`) y CotejoBoard, la app GTK 4 (`tareas/app/`) donde la persona crea proyectos, reparte, mira y aprueba. Las tareas se leen de una fuente intercambiable (Obsidian, repo, Notion o externa, en `tareas/fuentes/`) y el conocimiento de cada proyecto vive en su `.cotejo/`. Los agentes se lanzan en un worktree propio con su sandbox y entregan con evidencia. El detalle de cada módulo está en las referencias con tema `arquitectura` (`cotejo buscar --tipo referencia --temas arquitectura`).

## Piezas

| Capa | Pieza | Qué es | Tecnología | Tareas |
| --- | --- | --- | --- | --- |
| ve | Tablero | Las columnas Pendiente, Haciendo, Para comprobar y Hecho, con la ficha de cada tarea | GTK 4 (Python) | cotejo-7xsjb8, cotejo-2sxw7p, cotejo-v66btg, cotejo-21y2ah, cotejo-ayy9ok |
| ve | Inicio | La pestaña de bienvenida con el resumen y la constelación de proyectos | GTK 4 | cotejo-k7g353, cotejo-7wc9hb, cotejo-40b35h |
| ve | Proyecto nuevo | La entrevista de seis preguntas, la pantalla Preparando y revisar el plan | GTK 4 | cotejo-kf94so, cotejo-hiifrz, cotejo-m195bn, cotejo-1njap8 |
| ve | Mapa del proyecto | Las cuatro capas de cada proyecto con el estado de sus piezas | GTK 4 | cotejo-p86sa9, cotejo-6xgtq4 |
| ve | Ver mi app | El botón que abre la app del proyecto funcionando | GTK 4 | cotejo-vn4qd2, cotejo-xm56kh |
| ve | Equipo | Detectar, instalar y conectar los agentes de la persona | GTK 4 | cotejo-36mzm0, cotejo-2j6un7 |
| ve | Estilo del board | Letras, colores y contraste de los temas claro y oscuro | CSS de GTK | cotejo-9q0r47, cotejo-bdcyaj, cotejo-hd82wk, cotejo-xq43ho |
| ve | Web | La página cotejo.dev con la descarga para cada sistema | Vite | cotejo-uymg7v |
| hace | Comandos para agentes | Lo que usan los agentes para tomar, entregar y anotar | Python | cotejo-w7oeio |
| hace | Enrutador | Decide qué modelo hace cada tarea y cuántas caben a la vez | Python | cotejo-t46992, cotejo-3mh2si |
| hace | Lanzar agentes | Abre el agente en su propia copia del proyecto, con permisos acotados, y lo sigue | Python | cotejo-7yfw1e, cotejo-amui0f, cotejo-6a7np9, cotejo-0hgn6x, cotejo-srkywv, cotejo-o253bs, cotejo-z7ma7r, cotejo-granqk |
| hace | Maestro | El agente que conversa sobre el proyecto y propone repartir | Python | cotejo-9ybn1a, cotejo-3exwww, cotejo-w8vteb |
| hace | Preparar proyecto | Arma un proyecto nuevo en segundo plano con el agente elegido | Python | cotejo-riqf33, cotejo-fh0iqe, cotejo-iy0xzc, cotejo-uh9s2m, cotejo-p0fybl |
| hace | Integrar al aprobar | Junta el trabajo del agente con el proyecto cuando lo apruebas | git | cotejo-00fwc2 |
| guarda | Tareas | Las tareas de cada proyecto, donde la persona ya las tenga | Markdown | cotejo-0h5r4l, cotejo-x7tvty, cotejo-lbp6zt |
| guarda | Conocimiento | Decisiones, arquitectura, problemas y bitácora de cada proyecto | Markdown | cotejo-urw6hh, cotejo-z4irq9 |
| guarda | Configuración | Los modelos disponibles y la carpeta de cada proyecto, fuera del alcance de los agentes | JSON | cotejo-dgb7l2 |
| guarda | Entregas | La evidencia, el resumen y las capturas de cada tarea | Markdown | cotejo-0e17vu, cotejo-xrmr3h, cotejo-v40nc1 |
| conecta | Agentes de IA | Claude Code, Codex, OpenCode y Gemini, cada uno con sus modelos | CLI de cada uno | cotejo-qixs4j, cotejo-r4yg0n |
| conecta | Git | Una rama y una copia por tarea, con la identidad de la persona | git | cotejo-q93zyw |
| conecta | Fuentes de tareas | Obsidian, un repo de git, Notion u otra app | | cotejo-0h5r4l |

## Cómo se abre

- comando: python3 herramientas/cotejo_dev.py --board
- qué esperar: CotejoBoard de este código en una ventana aparte del Cotejo instalado, abierto en la pestaña Inicio con el vault de prueba; los repos ausentes ofrecen quitarlos y cada mapa permite quitar su proyecto
