# ¿Alcanzan las reglas, o hace falta el clasificador Haiku?

Medición del 2026-10-01 (tarea `cotejo-lbmv7e`). Se repite con:

```sh
tareas-obsidian evaluar      # tasa, abaratados, confusion, por_escalon, por_origen y fallos
```

## Decisión

**Las reglas alcanzan: no se añade el clasificador por ahora.** Fallan, pero siempre hacia
arriba (cuestan centavos, nunca arruinan una tarea), y hoy ninguna tarea real se reparte por lo
que dicen las reglas: las 19 que se han despachado de verdad se despacharon porque una persona
había asignado el modelo. Un clasificador mejoraría una propuesta que nadie usa sin revisarla, y
añadiría la única clase de fallo que el enrutador no tiene hoy: abaratar.

## Lo que se midió

42 tareas reales (`enrutador/datos/evaluacion.json`): 22 con el nivel que una persona escribió en
la nota (`#facil`/`#medio`/`#dificil`, origen `tag`) y 20 revisadas a mano (origen `revisado`).

| | |
|---|---|
| Aciertos | 36 / 42 (85,7 %) |
| Abaratados | **0** |
| Solo las etiquetas de fuera (`tag`) | 16 / 22 (72,7 %) — la cifra honesta: nadie las escribió mirando las reglas |
| Las revisadas | 20 / 20 |
| Decididas por defecto (n2) | 11, de las que 8 aciertan |

Confusión (esperado → decidido):

| esperado \ decidido | n0 | n1 | n2 | n3 |
|---|---|---|---|---|
| n0 (persona) | **14** | | | |
| n1 (Haiku) | | **2** | 5 | |
| n2 (Sonnet) | | | **16** | 1 |
| n3 (Opus) | | | | **4** |

Por escalón: los vetos humanos aciertan 14 de 14 (credenciales, trámites, criterio propio,
compras, físico); `diseno` 3/3, `mecanico` 2/2, `codigo` 8/10, `enunciado_largo` 1/2 y el
defecto 8/11.

## Dónde fallan

Los seis fallos van hacia arriba, y cinco son lo mismo: **una tarea de Haiku que se queda en
Sonnet** (las reglas eligen n1 en 2 de 7 casos). Tres caen al defecto (n2) porque ninguna regla
las reconoce como mecánicas; dos los sube la regla `codigo` porque nombran un archivo o una
skill. El sexto es una n2 que `enunciado_largo` sube a n3.

## Cuánto cuesta equivocarse, y cuánto costaría el clasificador

Con los precios del catálogo de Cotejo (`cotejo modelos`: Haiku 1/5 USD por millón de tokens de
entrada/salida, Sonnet 2/10) y **suponiendo** una tarea típica de agente de 300 000 tokens de
entrada y 15 000 de salida:

- mandar a Sonnet una tarea de Haiku cuesta unos **0,38 USD de más** (0,75 en vez de 0,38);
- clasificar una tarea con Haiku (≈600 tokens de entrada, 20 de salida) cuesta ≈ **0,0007 USD**.

El clasificador saldría a cuenta si arreglara al menos una de cada ~500 decisiones, **pero solo
si se usara su decisión**, y hoy no se usa: `despachar` exige que una persona asigne el modelo
(o `--auto`), y en la bitácora de despachos las 19 tomadas son `por: asignacion`. El ahorro
realizado hoy sería cero. Y el riesgo no lo es: un clasificador que abarate una sola n2 a Haiku
produce una entrega mala que hay que revisar, devolver y rehacer, que cuesta más que todos los
centavos ahorrados.

Además, con 7 casos de n1 no se puede medir si un clasificador acierta más que las reglas: la
diferencia entre 2/7 y 5/7 cabe en el ruido de una muestra tan chica.

## Cuándo volver a mirarlo

- Si en `despachos.jsonl` empiezan a aparecer despachos con `por` distinto de `asignacion`
  (`--auto`, o un `maestro` que reparta propuestas): entonces la propuesta sí gasta dinero.
- Si el set crece hasta tener al menos ~20 tareas n1 etiquetadas por una persona: entonces se
  puede medir un clasificador contra las reglas sin que el ruido lo decida.
- Antes de un clasificador, lo barato: una regla nueva para lo mecánico que hoy cae al defecto,
  con `evaluar` diciendo que `abaratados` sigue en 0 (la regla de CLAUDE.md).
