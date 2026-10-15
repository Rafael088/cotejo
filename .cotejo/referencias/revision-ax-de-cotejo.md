---
id: ref-446i
temas: [nota, ax]
resumen: "Revisión de Agent Experience de Cotejo (skill /ax, 2026-09-17): qué falta para salir a producción y para que cualquier agente la maneje contra cualquier segundo cerebro, con costos medidos en tokens."
---
# Revisión AX de Cotejo

> [!abstract] En una frase
> Qué le falta a [[proyecto|Cotejo]] para salir a producción y para que cualquier agente la maneje contra cualquier segundo cerebro, con los costos medidos en tokens en vez de estimados.

Revisión hecha con la skill `/ax` el 2026-09-17, sobre el código de [[proyecto|Cotejo]] tal como quedó tras CotejoBoard. Es la continuación práctica de Apps para agentes: aquella nota dice qué se quiere; esta dice qué falta y en qué orden.

## 🎯 El ciclo del agente

Lee qué tareas faltan, toma una, la hace, la entrega con evidencia y espera que una persona la apruebe o la rechace.

Ese ciclo ya existe y se ensaya a mano en CotejoBoard. Todo lo que sigue es lo que falta para que lo corra un agente de verdad.

## 📏 Lo que cuesta enterarse (medido, no estimado)

| Pregunta del agente | Camino de hoy | Costo |
| --- | --- | --- |
| ¿Cuántas faltan? | `tareas-obsidian --estado` | ~80 tokens · 32 ms |
| ¿Cuáles faltan, en Cotejo? | leer `Cotejo.md` entero | ~4.732 tokens |
| ¿Cuáles faltan, en NFC Manizales? | leer 9 notas | ~17.039 tokens |
| ¿Cuáles faltan, en todo? | leer `01-Proyectos/` (18 notas) | ~36.588 tokens |
| *(lo mismo, si existiera `--tareas`)* | *un JSON filtrado* | *~200 / ~3.873 tokens* |

**El número que importa:** para los conteos hay un camino 457 veces más barato que leer el vault. Para saber *cuáles* son las tareas no hay ninguno, y es la pregunta que el agente hace en cada vuelta del ciclo.

## 🧩 Los componentes, y en qué deberían convertirse

| Pieza | Qué es hoy | Qué debería ser |
| --- | --- | --- |
| `vault.py` | Cuatro cosas juntas: descubrir Obsidian, recorrer `01-Proyectos/`, parsear `- [ ]` + tags, escribir verificado | Tres: un modelo, una **fuente** intercambiable y un escritor verificado |
| `estado.py` | El camino barato: conteos en JSON, sin GTK, 32 ms | Igual, más versión de esquema y más cortes |
| `app.py` | CotejoList + CotejoBoard; **el único que sabe llamar a los verbos** | Un cliente más de la misma capa que usa el agente |
| `barra/cotejo.barra` | Widget QML que lee `estado.json` | Primer consumidor externo del contrato: ya obliga a versionarlo |
| *(no existe)* | — | La CLI de verbos: lo que convierte a Cotejo en algo enlazable |

## 📌 Cómo va (2026-09-18: los ocho, hechos)

Los ocho hallazgos están cerrados, y por el camino salieron siete fallos que nadie había visto.

| # | Hallazgo | Estado |
| --- | --- | --- |
| 1 | El hueco entre «cuántas» y «cuáles» | ✅ `tareas` filtrado en JSON |
| 2 | El agente no tiene verbos | ✅ `tomar`, `entregar`, `bloquear`, `asignar` |
| 3 | El contrato son los tags de Obsidian | ✅ capa `Fuente`: `modelo.py` + `fuente.py` + `fuentes/obsidian.py` |
| 4 | Sin identificador estable | ✅ marca de bloque `^cotejo-a1b2` |
| 5 | Entregar no exige evidencia ni deja bitácora | ✅ `--evidencia` obligatoria, `bitacora.jsonl`, y la evidencia y el motivo se ven en la carta |
| 6 | `estado.json` sin versión de esquema | ✅ `"esquema": 1` |
| 7 | Fallos que no dejan rastro | ✅ `avisos` en el resumen, banda ámbar en las ventanas, tooltip en la barra |
| 8 | Sin pruebas ni control de versiones | ✅ git + 172 pruebas |

Lo que cambió respecto al plan: el **5** se partió en dos (la evidencia en el board llegó un día después que la bitácora) y fue esa segunda mitad la que desbloqueó `bloquear`, porque las dos necesitaban la misma respuesta: **dónde vive el texto libre**. Vive en la bitácora, no en la línea de la tarea.

Lo que queda no es un hallazgo, es una espera: **usar el ciclo completo unos días** antes de programar el MCP. La revisión ya lo decía — si los verbos están bien puestos, el servidor es un envoltorio de una tarde; lo que no se puede adivinar es si el flujo se aguanta a mano.

## 🔍 Hallazgos, por impacto

### 1. El hueco entre «cuántas» y «cuáles» · Lectura barata
`--estado` devuelve conteos; para tomar una tarea concreta hay que leer las notas. Sacar las 4 tareas de Cotejo cuesta 4.732 tokens cuando la respuesta útil son 200, y lo que se lee de más son decisiones, bitácoras y frontmatter que el agente tiene que descartar.
**Cambio:** `--tareas [--proyecto] [--estado] [--agente]` en JSON. Tres tamaños, tres costos: conteos (80) → tareas filtradas (200) → la nota entera (4.700) solo si de verdad hace falta el contexto.

### 2. El agente no tiene verbos · Verbos estrechos
`marcar`, `poner_estado` y `poner_agente` verifican la línea y escriben atómico, pero solo los llama `app.py`. Un agente hoy edita el Markdown con sus propias herramientas, **saltándose la única protección que tiene el vault**.
**Cambio:** exponerlos como `tomar`, `entregar`, `bloquear`, `asignar`, cada uno devolviendo el estado nuevo en JSON para que el agente no vuelva a preguntar. Sin verbo `finalizar`: marcar `[x]` sigue siendo humano.

### 3. El contrato del agente son los tags de Obsidian, no Cotejo · Contrato separado de la vista
«El agente escribe `#en-curso` en la línea» solo es cierto si la fuente es un vault de Obsidian con `01-Proyectos/` y tareas `- [ ]`. Mientras el contrato sea el tag, **cada segundo cerebro nuevo es un contrato nuevo** y cada agente hay que reprogramarlo.
**Cambio:** subir el contrato un piso. El agente habla con Cotejo (`cotejo tomar T-a1b2`) y los tags pasan a ser detalle de cómo la fuente Obsidian guarda las cosas. Entonces Logseq, Silverbullet, una carpeta de Markdown pelada, Todoist o Notion son adaptadores, no reescrituras.
**Lo que lo hace viable:** `app.py` solo usa 11 símbolos de `vault.py` (`escanear`, `marcar`, `poner_estado`, `poner_agente`, `directorios`, `cargar_config`, `COLUMNAS`, `AGENTES`, `HECHA`, `CONFIG_PATH`, `TareaCambiada`). Eso es una interfaz, no un refactor.
**Cómo quedó (2026-09-18):** `modelo.py` (qué es una tarea, sin Markdown), `fuente.py` (la interfaz y qué fuente se usa) y `fuentes/obsidian.py` (el único que sabe de notas, tags y marcas). Añadir un segundo cerebro son cuatro métodos. La estimación se quedó corta en una cosa: lo que de verdad marcaba la frontera no eran las funciones sino los datos —mientras la tarea llevara `nota` y `línea` a la vista, la ventana seguía comparando rutas—, así que el modelo quedó con `donde` y un `sitio` opaco que solo mira su fuente.

### 4. Una tarea no tiene identificador estable · Identificadores estables
Una tarea es `(nota, número de línea)`. Editar la nota por arriba cambia la identidad de todas las de abajo. Hoy no duele porque la interfaz reescanea todo el tiempo; va a doler el día uno del agente, que necesita nombrar tareas entre una llamada y la siguiente.
**Cambio:** identificador de bloque al final de la línea (`^cotejo-a1b2`), que es el mecanismo nativo de Obsidian, sobrevive a las ediciones y es Markdown portable.
**Hay que hacerlo antes** de que un agente empiece a guardar IDs.

### 5. Entregar no exige evidencia y no queda bitácora · Evidencia
Mover a «por validar» es cambiar un tag; nada dice qué se hizo. Si revisar una entrega cuesta lo mismo que haberla hecho, la columna «En espera de comprobación» se convierte en una segunda lista de pendientes — y para eso ya estaba Obsidian.
**Cambio:** `entregar` exige `--evidencia` (archivos tocados, comando y salida de pruebas, commit), y cada operación se anexa a un `bitacora.jsonl`. Rechazar guarda el motivo.

### 6. `estado.json` no dice qué versión de esquema es · Cuidado del contrato
Ya hay dos consumidores (el widget QML y, pronto, el agente) y ninguno puede detectar que el formato cambió. Agregar claves es barato; renombrarlas rompe en silencio a quien no puedes ver.
**Cambio:** `"esquema": 1`, y dejar escrito que las claves se agregan pero no se renombran.

### 7. Fallos que no dejan rastro · Errores accionables
`_leer()` devuelve `[]` ante un `UnicodeDecodeError`: una nota ilegible desaparece del board sin avisar. `estado.escribir()` se traga los `OSError`: con el disco lleno, el widget muestra datos viejos para siempre.
**Cambio:** contar lo que no se pudo leer y exponerlo en `--estado` como `avisos`. No hace falta un sistema de logs; hace falta que el silencio se vea.

### 8. El único código que escribe en las notas no tenía pruebas ni control de versiones · Producción
`_reescribir()` modifica las notas del vault y es el punto de mayor consecuencia del proyecto. El 2026-09-17 se hizo `git init`; faltan las pruebas.
**Cambio:** tests de `vault.py` con un vault de mentira: línea cambiada por fuera, tarea dentro de un bloque de código, tags en cualquier orden, sangría, `\r\n`, tarea sin texto, marcar dos veces seguidas.

## ✅ Lo que ya está bien (no romperlo al refactorizar)

- **La escritura verificada y atómica.** Guardar la línea original, compararla antes de escribir, temporal + `os.replace`. Es el corazón y está bien resuelto.
- **`TareaCambiada` dice qué hacer**, no solo qué pasó, y la interfaz recarga sola.
- **El estado de interfaz vive fuera del vault** (`board.json`, `expandidos.json`). Por eso se pudo rehacer CotejoBoard entero —ListBox, cotejo, arrastre— sin tocar un solo tag.
- **`estado.py` no importa GTK.** Los 32 ms salen de ahí, y hay que defenderlo: la tentación de reutilizar algo de `app.py` se los lleva puestos.
- **La transición humana está reservada**, y marcar `[x]` limpia el tag de estado.
- **El ciclo se ensaya a mano antes de programarlo.** El MCP va al final: si los verbos de la CLI están bien puestos, el servidor es un envoltorio de una tarde.

## 🚦 El orden, y por qué

1. **Hallazgos 1 y 2 juntos** — son el mismo comando. Con eso el ciclo pasa de «ensayable a mano» a «corrible por un agente», y es lo que más contexto ahorra por hora invertida.
2. **Hallazgo 4, ID estable** — inmediatamente después y antes de que ningún agente guarde identificadores. Cambiarlo más tarde invalida todo lo escrito.
3. **Hallazgo 8, pruebas** — antes de abrirle la escritura a un agente, no después: la frecuencia de escritura está a punto de multiplicarse.
4. **Hallazgo 3, la capa `Fuente`** — el cambio grande, cuando los verbos ya estén probados contra Obsidian. Abstraer antes de saber qué verbos aguantan es abstraer la forma equivocada.

## 🔗 Enlaces

- Proyecto: [[proyecto|Cotejo]]
- Idea que la origina: Apps para agentes
- Skill que produjo la revisión: `/ax` (`~/.claude/skills/ax`)
