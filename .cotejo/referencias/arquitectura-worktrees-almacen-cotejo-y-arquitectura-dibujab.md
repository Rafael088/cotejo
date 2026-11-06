---
id: ref-k6ew
temas: [arquitectura, worktrees]
resumen: pendiente
---
# Arquitectura · Worktrees, almacén .cotejo y arquitectura dibujable

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

`tareas/worktrees.py` es el aislamiento de la 1.1 (B3): si la tarea es de un repo de git
(`enrutador.proyectos` o, en la fuente repo, `Fuente.carpeta_de`), `despachar` le crea un
worktree con rama `cotejo/<id>` **fuera del repo y del vault** (por defecto en
`rutas.estado()/wt`; `enrutador.worktrees.carpeta` o `COTEJO_WORKTREES` lo mueven, y una carpeta
dentro de cualquiera de los dos se rechaza antes de tomar la tarea). Se registra en
`rutas.estado()/worktrees/<id>.json`, de donde lo leen `entregar`, `comprobar`, `revisar` y el
board, que lo retira al aprobar o devolver a Pendiente (salvo si la lanzó el board: entonces
está pausada y el worktree se queda para retomarla). Retirar nunca borra la rama ni lo que
esté sin commitear. `--sin-aislar` (o `worktrees.aislar: false`) es el comportamiento de antes.

`tareas/almacen.py` es el almacén de la 1.2 (A1): el resto de `.cotejo/` —decisiones,
arquitectura, problemas, aprendizajes, bitácora, referencias y fichas de recursos—, una
entrada por archivo con frontmatter mínimo (`TIPOS`). El id va en el frontmatter (`dec-x7k2`:
prefijo por tipo y 4 caracteres base36) y se busca por ahí, nunca por el nombre del archivo; la
bitácora es un archivo por día y la fecha es su id. Un frontmatter roto sale en `avisos` y no
rompe la lectura. Toda escritura pasa la `version` (hash del archivo) que se leyó y levanta
`EntradaCambiada` si ya no es esa; las decisiones no se editan (`NoSeEdita`), solo cambian de
estado por `TRANSICIONES`. Quién puede pedir cada transición —aceptar es de la persona— lo
deciden los verbos, no el almacén. Ningún verbo ni el importador abren `.cotejo/` por su cuenta.

`tareas/arquitectura.py` es la arquitectura dibujable de la 1.3.0: la sección `## Piezas` de una
entrada `arquitectura` (tabla de capa `ve|hace|guarda|conecta`, pieza, qué es, tecnología y
tareas). Es puro —ni archivos ni GTK—: `analizar(cuerpo)` valida y da las piezas,
`estado_pieza(columnas)` el estado (`por-comprobar` > `hecho` > `en-curso` > `falta`; sin tareas,
`falta`), `con_estado` y `resumen_por_capa` lo que enseñan `leer` y `contexto`. La constelación y
el mapa del board leen por `conocimiento.piezas_del_repo(alm)`, no por su cuenta. Una entrada sin
la sección es texto libre, como antes.
