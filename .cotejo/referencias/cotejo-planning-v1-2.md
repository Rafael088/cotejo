---
id: ref-lesy
temas: [cotejo, planning, v1.2, ax]
resumen: "Planning de la v1.2: el conocimiento de cada proyecto vive en .cotejo/ dentro de su repo, un agente se entera en menos de 1k tokens, y los proyectos de Obsidian o Notion se importan una sola vez."
---
# Cotejo - Planning v1.2

# Cotejo — Planning v1.2

> [!abstract] En una frase
> El conocimiento de cada proyecto (decisiones, arquitectura, problemas, referencias, bitácora) vive en una carpeta `.cotejo/` dentro de su repo, un agente se entera de él en una llamada de menos de 1k tokens y pide solo lo que necesita, y los proyectos de Obsidian o Notion se traen una vez, sin volver a depender de esas apps.

## De dónde sale

Brainstorming del 2026-10-02, con la skill `brainstorming` de superpowers y los criterios de `/ax`. La idea grande: que Cotejo sea la herramienta para gestionar de punta a punta los proyectos hechos con IA, desde la idea hasta el soporte, empezando por los desarrolladores que hacen vibe coding. Obsidian deja de ser una fuente: el segundo cerebro pasa a ser una carpeta dentro de cada repo que Cotejo sirve por MCP gastando pocos tokens, y Obsidian y Notion quedan como apps de donde se importa.

## Hoja de ruta

| Versión | Qué trae | Por qué ahí |
| --- | --- | --- |
| **1.1** | Lo ya planeado en [[cotejo-planning-v1-1|Cotejo - Planning v1.1]], con las tareas en `.cotejo/tareas.md` en vez de `TAREAS.md` | Cerrar lo pendiente. Es la base de todo lo demás |
| **1.2** | El almacén `.cotejo/`, los verbos para leerlo y escribirlo (también por MCP) y los importadores de Obsidian y Notion | Sin importadores no puedes llevarte tus proyectos y Obsidian sigue siendo necesario |
| **1.3** | Soporte: un reporte (formulario, Sentry, issue de GitHub) entra como tarea y el enrutador la asigna | Escribe en el almacén de la 1.2 |
| **2.0** | Grafo y vault visual dentro de la app | Es el salto visible y el punto en que Obsidian deja de hacer falta del todo |
| Después | Del inicio al plan (`crear proyecto`, entrevista que deja un brief, arquitectura con diagramas) y el lanzamiento como control con evidencia | Se decide con lo que salga de usar la 1.2 y la 1.3 |

Cada versión lleva su propia spec, su plan y su release.

## Decisiones tomadas

| Pregunta | Decisión | Por qué |
| --- | --- | --- |
| Para quién primero | Desarrolladores que hacen vibe coding | Es el camino más corto: se construye sobre la 1.1 y después se baja hacia quien no programa |
| Papel de Obsidian y Notion | Dejan de ser fuentes y pasan a ser **importadores de un solo sentido** | Escribir en sistemas ajenos es donde Cotejo más ha tenido que blindarse; la sincronización de ida y vuelta es lo que más se rompe |
| Dónde vive el conocimiento | En `.cotejo/` dentro de cada repo, versionado con el código. Cotejo mantiene la lista de repos para la vista general | Viaja con el código y cualquier agente que abra el repo lo encuentra |
| Qué es un proyecto | Una carpeta con git. A un proyecto que no tiene repo (Seorigen, Eco) el importador le crea uno | Un solo camino para todos; los worktrees y la evidencia de la 1.1 lo necesitan |
| Estructura | Esqueleto fijo con tipos que Cotejo entiende y frontmatter mínimo, más `referencias/` para el resto | Lo tipado da respuestas baratas y precisas |
| Granularidad | **Un archivo por entrada**, con un id en el frontmatter | Id estable que se encuentra con `grep`, diffs limpios, dos agentes no se pisan, leer una entrada cuesta solo esa entrada |
| Información que no es código (marca, investigación, políticas) | Es relevante: va a `referencias/` con `temas` y un `resumen` de una línea, en una sola carpeta filtrada por temas | Cada negocio tiene clases distintas; con temas no hay que inventar tipos y una referencia puede tener dos temas |
| Imágenes | En `recursos/`, cada una con su ficha `.md` | Ver una imagen le cuesta a un agente unos 1.000–1.600 tokens; leer la ficha, unos 50 |
| Decisiones | El agente las **propone**; la persona las **acepta** desde el board. No existe un verbo para aceptar ni en la CLI ni en el MCP. Una decisión no se edita: se reemplaza | La misma regla que con las tareas: así «decidimos X» significa que alguien lo firmó |
| Problemas | `resolver` lo deja el agente | Un problema resuelto es un hecho, no una firma; si no lo estaba, se vuelve a abrir sin costo |
| Clasificar al importar | Mecánico siguiendo la plantilla del vault, por defecto en ensayo, y crea la tarea «Revisar lo importado» | Determinista, se puede probar, no gasta tokens; lo que no encaja lo resuelve un agente con el ciclo que ya existe |
| Nota original en Obsidian | No se toca. Cotejo marca el proyecto como migrado en su config y deja de leerlo desde Obsidian | Cero escrituras en el vault, se deshace quitando la marca, no salen tareas duplicadas en el board |
| Verbo de importar | `cotejo importar plan <plan.md>` (1.1) y `cotejo importar obsidian\|notion <proyecto>` (1.2) | Un solo verbo para traer cosas a Cotejo, sin choque de nombres |
| MCP | No se diseña aparte: `cotejo mcp` (de la 1.1) expone los verbos nuevos tal cual, uno a uno | Primero se ensaya el ciclo a mano en la CLI; el MCP es un envoltorio |
| Fuente compuesta (E1, 2026-10-04) | **Entra en la 1.2, mínima**: solo obsidian + repo. Los proyectos marcados como migrados se leen de su repo y el resto del vault; si un nombre está en los dos sitios, gana el repo. Nada de componer N fuentes cualesquiera (Notion incluida) | El paso 8 del importador ya la da por hecha, y sin ella importar un proyecto obliga a pasar toda la config a `repo` y deja fuera del board el resto del vault. La fuente `repo` ya hereda de `obsidian`, así que es un envoltorio que reparte por proyecto |
| Aceptar una decisión en el board (E2, 2026-10-04) | **Carta propia + aviso**: la decisión propuesta sale como carta propia en «Para comprobar» y se abre con la misma vista de revisión (su texto y, si reemplaza, la vieja al lado), con el único botón de Aceptar. La revisión de una tarea solo avisa «esta entrega propone dec-xxxx», sin aceptar ahí. Aprobar o integrar la tarea **nunca** acepta la decisión | Un solo sitio para firmar. Las decisiones propuestas fuera de una tarea también tienen dónde salir, y la que viaja en la rama `cotejo/<id>` se ve mientras se revisa la entrega que la trajo |

## Lo que se midió antes de diseñar

Con `medir.py` de la skill `ax`, sobre el propio Cotejo, el 2026-10-02:

| Camino | Costo |
| --- | --- |
| Leer las 8 notas de Cotejo | ~45.300 tokens |
| Solo `Cotejo.md` | ~25.800 tokens: Tareas ~8k, Decisiones ~6,9k, Bitácora ~2,9k, Problemas ~2,8k, Aprendizajes ~2,6k |
| `cotejo tareas --proyecto Cotejo` | ~19.500 tokens, porque trae también las hechas |
| `cotejo tareas --proyecto Cotejo --estado pendiente` | ~1.400 tokens |

Las decisiones pesan casi tanto como las tareas y hoy no hay forma barata de leerlas. Eso es lo que justifica el esqueleto tipado. El defecto de `tareas` sin filtro queda como tarea de la 1.1.

## Diseño

### 1. Estructura de `.cotejo/`

```
.cotejo/
  proyecto.md                          ← objetivo, stack, enlaces, siguiente paso
  tareas.md                            ← la misma línea de hoy (v1.1)
  decisiones/2026-10-02-auth-con-jwt.md
  arquitectura/flujo-de-pago.md
  problemas/2026-09-17-git-add-a.md
  aprendizajes/2026-09-18-medir-no-estimar.md
  bitacora/2026-10-02.md               ← un archivo por día, solo se añade al final
  referencias/manual-de-marca.md       ← todo lo que informa el desarrollo sin ser decisión
  recursos/logo-principal.svg
  recursos/logo-principal.md           ← la ficha de la imagen
```

Todo es Markdown con `[[enlaces]]` compatibles con Obsidian; el grafo de la 2.0 sale de esos enlaces.

| Tipo | Frontmatter | Estados |
| --- | --- | --- |
| decisión | `id: dec-x7k2`, `fecha`, `temas`, `estado`, `autor`, `reemplaza` | `propuesta` → `aceptada` (solo la persona) → `reemplazada` |
| problema | `id: pro-…`, `fecha`, `temas`, `estado` | `abierto` → `resuelto` |
| arquitectura | `id: arq-…`, `temas`, `actualizado` | — |
| aprendizaje | `id: apr-…`, `fecha`, `temas` | — |
| bitácora | `fecha` (el día es el id) | — |
| referencia | `id: ref-…`, `temas`, `resumen`, `origen` | `resumen: pendiente` hasta que se revise |
| recurso (ficha) | `id: rec-…`, `archivo`, `temas`, `resumen`, `origen` | `ficha: pendiente` hasta que se revise |

Reglas:

- Los ids siguen la convención de `^cotejo-xxxx`: prefijo por tipo y 4 caracteres en base36. Son estables aunque el archivo cambie de nombre.
- `temas` es lo que permite pedir «las decisiones sobre autenticación» sin leer nada más.
- `proyecto.md`, las entradas de arquitectura y las referencias se editan en el sitio, siempre con escritura verificada por versión. Las decisiones nunca se editan.
- Fuera a propósito: el índice en caché (`indice.json`) hasta que se mida que leer el frontmatter es lento, y partir las tareas en archivos sueltos.

### 2. Verbos

Primero en la CLI y ensayados a mano. `cotejo mcp` los expone uno a uno.

**Para enterarse, de menos a más:**

| Verbo | Qué devuelve | Costo esperado |
| --- | --- | --- |
| `cotejo contexto` | Objetivo, stack, tareas por estado, siguiente paso, decisiones vigentes (id y título), problemas abiertos y los temas que existen con cuántas entradas tiene cada uno | < 1k tokens |
| `cotejo buscar [--tipo] [--temas] [--estado] [--desde] [--texto] [--limite]` | Una línea por entrada: id, tipo, título y resumen | ~30 tokens por entrada |
| `cotejo leer <id>` | La entrada completa con frontmatter y `version` (hash). Si es un recurso, la ficha y la ruta, no la imagen | Lo que mida la entrada |

**Para actuar:**

| Verbo | Qué hace |
| --- | --- |
| `cotejo proponer decision --titulo --temas --texto [--reemplaza <id>]` | Crea una decisión `propuesta` con el agente como autor |
| `cotejo anotar <problema\|aprendizaje\|referencia\|arquitectura> --titulo --temas --texto` | Crea la entrada con su id |
| `cotejo bitacora "texto"` | Añade al final del archivo del día |
| `cotejo editar <id> --version <hash> --texto` | Arquitectura, referencias y `proyecto.md`. Se niega si la versión no coincide |
| `cotejo resolver <pro-id> --solucion` | Pasa un problema a `resuelto` |

Toda escritura devuelve la entrada que dejó (id, ruta, versión nueva), para que el agente no tenga que volver a leer.

**Lo que el agente no puede hacer:** aceptar una decisión. La prueba que vigila que no exista un verbo para finalizar tareas se amplía a la aceptación, en la CLI y en el MCP.

### 3. Importador

`cotejo importar obsidian <proyecto> [--destino <carpeta>] [--aplicar]`

1. **Localiza el proyecto:** la nota del proyecto, sus subnotas (`proyecto: "[[X]]"`) y los adjuntos que enlazan, usando la ruta del vault que ya está en la config.
2. **Resuelve el repo:** si `repo:` es una ruta local, la usa; si hay un `.git` en una subcarpeta, la usa (caso Cotejo); si `repo:` es una URL o no hay nada, exige `--destino` y hace `git init` ahí.
3. **Reparte:**

| De la nota | A `.cotejo/` | Estado |
| --- | --- | --- |
| Objetivo, Stack, Enlaces, Siguiente paso | `proyecto.md` | — |
| Tareas | `tareas.md` | Conserva los `^cotejo-id` y el estado |
| Decisiones técnicas | `decisiones/`, un archivo por decisión | `aceptada`, `autor: importado` |
| Bitácora (cada `### fecha`) | `bitacora/<fecha>.md` | — |
| Problemas y soluciones | `problemas/` | `resuelto` si tiene solución |
| Aprendizajes | `aprendizajes/` | — |
| Subnotas | `referencias/` | `resumen: pendiente` |
| Imágenes y adjuntos | `recursos/` con ficha | `ficha: pendiente` |
| Lo que no se pudo leer | `referencias/` con tema `sin-clasificar` | — |

4. **Reescribe los enlaces:** los internos al proyecto apuntan a los archivos nuevos; los que van a otros proyectos quedan como texto con su origen.
5. **Ensayo por defecto:** cuántas entradas van a cada tipo, qué queda `sin-clasificar` y qué hará con el repo. `--aplicar` escribe pero **no hace commit**: la persona revisa con `git diff` y hace el commit.
6. **Crea la tarea** «Revisar lo importado: resúmenes, temas y fichas», con el modelo que proponga el enrutador. El primer párrafo queda como resumen provisional.
7. **Idempotente:** cada entrada guarda su `origen` y volver a correrlo no duplica.
8. **Marca el proyecto como migrado** en la config de Cotejo, que deja de leerlo desde Obsidian. La nota original no se toca.

Excepción asumida: el importador crea decisiones `aceptada` sin pasar por la persona. Se justifica porque las escribió ella en su vault, y queda como `autor: importado`.

**Notion** es más modesto en la 1.2: importa las tareas por el adaptador que ya existe y las páginas como referencias. El resto pasa por la tarea de revisión.

### 4. Errores, pruebas y criterio de éxito

**Errores**, en el formato JSON de la CLI y con el siguiente paso:

| Situación | Respuesta |
| --- | --- |
| `editar` con versión vieja | «`arq-k2m9` cambió desde que la leíste: `cotejo leer arq-k2m9` y reintenta» |
| `editar` una decisión | «Las decisiones no se editan: `cotejo proponer decision --reemplaza dec-x7k2`» |
| Id inexistente | «No hay `dec-x7k3`. ¿Buscabas `dec-x7k2`? Usa `cotejo buscar --texto …`» |
| Pedir aceptar | «Aceptar es de la persona: se hace desde el board» |
| Repo sin `.cotejo/` | «Este repo no tiene `.cotejo/`: `cotejo init`» |
| Importar sin repo ni `--destino` | «Seorigen no tiene repo: pasa `--destino <carpeta>`» |
| Frontmatter roto | No rompe nada: sale como aviso en `contexto` con el mecanismo de avisos que ya existe |

**Pruebas:**

- Almacén: un repo de mentira con `.cotejo/`. Todos los verbos, conflicto de versión, reemplazo de decisiones, ids que sobreviven a un cambio de nombre y bitácora que solo crece.
- Importador: una nota de prueba con la plantilla y su árbol de salida esperado; correrlo dos veces no duplica; enlaces reescritos; lo ilegible va a `sin-clasificar`.
- Contrato: ningún verbo para finalizar ni para aceptar, en la CLI ni en el MCP.
- Windows: los verbos nuevos en el runner de `windows.yml`, sobre todo las rutas de `recursos/`.

**Criterio de éxito, medido:**

1. Importar Cotejo y Seorigen, primero en ensayo y después con `--aplicar`.
2. Con `medir.py` sobre Cotejo ya importado: `cotejo contexto` < 1k tokens (hoy `Cotejo.md` cuesta 25,8k), y contestar «¿qué decidimos sobre X?» con `buscar` y `leer` cuesta al menos 10 veces menos que leer la sección de Decisiones (6,9k).
3. Una semana en la que los agentes que trabajan en esos repos usan `contexto` y `buscar` en vez de abrir las notas.

## Riesgos

- **Que la plantilla no sea tan uniforme como parece.** Si muchas notas se salen de ella, `sin-clasificar` crece y la tarea de revisión se vuelve un trabajo grande. El ensayo sobre Cotejo y Seorigen lo dirá antes de escribir nada.
- **Resúmenes malos.** Si el `resumen` no deja decidir sin abrir la entrada, el agente lee igual el original y costó las dos cosas. La tarea de revisión tiene que tratarlos como lo más importante.
- **Dos sitios con tareas mientras dure la migración.** Los proyectos migrados se leen del repo y los demás de Obsidian. Lo resuelve la fuente compuesta mínima (E1, tarea A3).

## Preguntas abiertas

- ¿Hace falta algún tipo propio para lo que no es código (por ejemplo `marca/`) o basta `referencias/` con temas? Se decide después de importar Seorigen y ver qué cae en `sin-clasificar`.

## Siguiente paso

**La 1.1 está cerrada (2026-10-03) y las tareas de la 1.2 ya están en [[proyecto|Cotejo]]**, con el prefijo `v1.2 ·` y la letra de su bloque: E (decisiones de la persona), A (almacén), B (verbos para enterarse), C (verbos para actuar), D (importadores) y F (Windows, medición, uso y release). Lo primero son E1 y E2, que pueden cambiar el diseño, y A1, de la que dependen casi todas las demás.
