---
id: ref-h6ka
temas: [arquitectura, enrutador]
resumen: pendiente
---
# Arquitectura · Enrutador, clientes de agentes, modelos y MCP

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

Al lado, `enrutador/` decide **quién atiende cada tarea**: `niveles.py` es el catálogo;
`reglas.py`, las expresiones regulares; `decision.py`, el orden en que se decide —y no hace
entrada/salida, que es lo que lo deja probar entero sin vault y sin gastar—; `cotejo.py` es su
única puerta a las tareas; `motores/` es lo único que lanza procesos; `verbos.py` cuelga sus
verbos del analizador de `cli.py`. La dependencia va en un solo sentido —el enrutador importa
`tareas`, y `tareas` solo lo importa dentro de `analizador()`, que es lo que evita el ciclo—.

`tareas/mcp.py` (`cotejo mcp`) es la misma CLI por MCP: saca las tools de `cli.analizador()` y
corre cada una por `cli.main(argv)`. No se le añaden tools a mano ni flags propias: lo que no
sea un verbo de la CLI no es una tool. Su única bandera, `--perfil nucleo|completo` (por defecto
`nucleo`), solo filtra: un verbo es del núcleo si su definición lo marca con `cli.nucleo()`.

**Antigravity CLI** (`agy`, cotejo-r4yg0n) es el quinto cliente de `enrutador/clientes.py`
(`antigravity`), con las banderas de https://antigravity.google/docs/cli/reference y
…/docs/cli/headless, ninguna inventada: sin interfaz `agy --print-timeout 0 [--model <slug>] …
-p <prompt>` (`0` espera al final del turno: el tope lo pone Cotejo), en terminal `-i`, sus
carpetas con `--add-dir` y sus comandos aprobados con `--dangerously-skip-permissions` (al
preparar y en la terminal libre), porque sus reglas `allow`/`deny` solo viven en la
`~/.gemini/antigravity-cli/settings.json` de la persona, que Cotejo no toca: sus prohibidos son
las guardas del PATH. Su `--sandbox` no va por defecto (en Linux esconde lo que no monta, como
el lanzador de `cotejo`); se pide en `lanzar.argumentos_extra.antigravity`. De fábrica, el
modelo que tenga elegido (`niveles.DE_FABRICA`, sin `--model`); `agy models` es su lista.

**Los modelos de todos los agentes** (v1.3.0, cotejo-qixs4j). `enrutador/modelos_vivos.py` dice
qué agentes están **listos** (instalados y con sesión: solo mira sus credenciales en disco o su
variable de entorno, nunca lanza el CLI) y qué modelos ofrece cada uno: `opencode models`,
`codex debug models` y su `~/.codex/models_cache.json` (que se lee antes, sin lanzar nada) se
preguntan (caché en `<estado>/modelos/`, tope de segundos, y si fallan lo guardado o el respaldo);
Claude y Gemini no listan y su lista son sus alias. Nada de eso gasta tokens.
`niveles.DE_FABRICA` trae los de fábrica de los otros agentes (`gemini-pro|flash|flash-lite` por
alias; `opencode` = «el modelo que tenga por defecto», sin `-m`; Codex con su nombre exacto,
`gpt-5.6-luna|terra|sol` y de n3 `gpt-5.6-sol-alto`, que es sol con `-c
model_reasoning_effort=high`; astra no viene de fábrica), que un registrado con la misma clave
tapa; los nombres viejos de Codex (`codex`, `codex-rapido`, `codex-fuerte`) siguen resolviendo
por alias a luna/sol/sol-alto (`niveles.ALIAS_DE_ANTES`). Lo que se ofrece (`niveles._ofrecidos`,
en «Asignar a», `modelos_de` y `del_cliente`) quita los de fábrica que repiten un registrado
(mismo agente, id y argumentos) y los de Codex que su `models_cache.json` no lista; `por_nombre`
los sigue resolviendo todos. `niveles.grupos` arma «Asignar a» por agente y `niveles.del_cliente`
traduce un tamaño al agente del proyecto sin abaratar. El agente del proyecto es `agente:` en
`.cotejo/proyecto.md` (`origen.agente_de`), que pone `init` con `COTEJO_AGENTE` (lo añade
`preparar.lanzar`); con él, lo que el enrutador decide por tamaño se propone con ese agente
(`decision.decidir(cliente=…)`, en `plan`, `decidir`, `despachar`, el board y «Empezar la 0.1.0»).
El board (`tareas/app/modelos.py`) agrupa, pone el del proyecto primero y tiene «Añadir modelo…»
(en «Asignar a» y en el menú de la cabecera), que registra como `cotejo modelos agregar`;
`cotejo modelos vivos` es lo mismo por la CLI.
