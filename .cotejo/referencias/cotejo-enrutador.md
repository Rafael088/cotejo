---
id: ref-vqak
temas: [cotejo, enrutador]
resumen: "Enrutador que decide y despacha qué modelo (Haiku, Sonnet u Opus, o una persona) atiende cada tarea de Cotejo; nació como proyecto aparte (FocoRouter) y hoy vive en enrutador/ dentro de este repo."
---
# Cotejo - Enrutador

# Cotejo — Enrutador

> [!info] Parte de [[proyecto|Cotejo]]
> Nació como proyecto suelto (FocoRouter, repo propio) y se mudó dentro de Cotejo: el código vive en `cotejo/enrutador/` y se usa con los verbos de la CLI de Cotejo. El repo original quedó archivado en `05-Archivo/focorouter`. Lo de abajo es la historia del diseño; donde hable de `focorouter <verbo>` o de su repo, hoy es Cotejo.

> [!abstract] En una frase
> **FocoRouter**: decide qué modelo atiende cada tarea de [[proyecto|Cotejo]] y se la manda — lo trivial a Haiku, el trabajo normal a Sonnet, lo grande a Opus, y lo que no es para ningún modelo se queda donde estaba.

## 🎯 Objetivo
- **Problema:** [[proyecto|Cotejo]] resolvió *qué* hay que hacer, pero no *quién* lo hace: hoy lo hace siempre el modelo que tengas abierto, así que "anota esto en el inbox" y "subir el contrato del agente a la CLI" cuestan lo mismo. Y algo peor, que no se vio hasta medir: **24 de las 68 tareas pendientes no son para ningún modelo** (comprar el dominio, que un abogado revise los textos, sacar la API key), y mandárselas produce una entrega falsa que hay que revisar y devolver.
- **Solución construida:** un enrutador con cuatro destinos —tres modelos y una persona— que decide por lo explícito antes que por lo adivinado, y que toma la tarea en [[proyecto|Cotejo]] a nombre del modelo elegido antes de lanzarla. Se le habla por CLI y en JSON, así que lo opera cualquier agente.
- **Criterio de éxito:** lo pendiente se reparte sin que yo elija modelo tarea por tarea, ninguna tarea mía termina en un modelo que no podía hacerla, y ninguna tarea grande termina en un modelo barato.

## 🧱 Stack y arquitectura
| Capa | Tecnología | Notas |
| --- | --- | --- |
| Enrutador | Python 3.9+, sin dependencias | Repo `focorouter`. CLI de 8 verbos, todo entra y sale en JSON. No importa GTK |
| Decisión | Reglas deterministas (regex) | `decision.py` no hace entrada/salida: entra texto, sale una decisión con su porqué |
| Datos de la tarea | La CLI de [[proyecto|Cotejo]], nunca sus módulos | `#agente/opus` y `#facil`/`#medio`/`#dificil` llegan ya parseados en el JSON de `cotejo tareas` |
| Ejecución | Un agente vivo, **no la API** | `agente` (defecto, no lanza nada: devuelve el encargo) · `sesion` (`claude --bg --model`, instancias abribles) · `headless` (`claude -p`, hay que pedirlo) · `simulado` |
| Evidencia | `despachos.jsonl` | Qué se despachó, a quién, por qué regla y cómo salió. Solo se agrega |
| Protocolo | `skills/focorouter/SKILL.md` | Una sola fuente; `install.sh` la reparte a los agentes que ya estén en la máquina |

**Los cuatro destinos**

| Nivel | Quién | Para qué |
| --- | --- | --- |
| n0 | **una persona** | Comprar, firmar, llamar a alguien, abrir una cuenta, tocar algo físico, decidir por gusto |
| n1 | `claude-haiku-4-5` | Trabajo mecánico y acotado |
| n2 | `claude-sonnet-5` | El trabajo normal de código. **El defecto** |
| n3 | `claude-opus-5` | Arquitectura, contratos, lo que cruza varios archivos |

**El orden de decisión** — de lo más explícito a lo más adivinado, y cada escalón dice por qué ganó

```
1. --modelo          una persona lo está pidiendo ahora mismo         confianza alta
2. asignación        ya estaba escrito en la nota (#agente/opus)      confianza alta
3. veto humano       nadie lo asignó y el texto dice que no es para un modelo
4. dificultad        una persona etiquetó el tamaño (#facil/#medio/#dificil)
5. reglas            regex sobre el texto, gratis
6. defecto           sonnet — ante la duda se escala, nunca se abarata
```

**Las dos formas de usarlo, y ninguna necesita la API**

**A. «Ponte con las tareas del proyecto X»** — lo hace el agente con el que estás hablando. Para cada tarea: si el modelo asignado es el suyo, la toma y la hace; si no, se la pasa a un subagente con ese modelo. Una sesión **no puede cambiarse de modelo a sí misma** (`/model` lo escribe una persona), así que ahí la salida honesta es delegar o devolvértela.

**B. «Hazme dos tareas del proyecto X»** — una instancia maestra reparte y varias trabajan a la vez:

```sh
focorouter plan --proyecto X --solo-despachables --limite 2
focorouter despachar <id> --motor sesion    # claude --bg --model <el que toque>, en su carpeta
```

Devuelve el id de cada instancia; se abren con `claude attach <id>`. No hace falta mirarles los logs: el canal es [[proyecto|Cotejo]], y aparecen solas en «En espera de comprobación» con su evidencia.

**Si nadie le asignó modelo, se para y pregunta** (código 6), con la propuesta de las reglas dentro del mensaje. La respuesta se escribe en la nota con `cotejo asignar <id> <modelo>`, así que se pregunta una vez en la vida de la tarea. `--auto` acepta la propuesta sin preguntar.

No entrega tareas ni las marca hechas, y no despacha una tarea del nivel humano ni con bandera. Las dos ausencias están vigiladas por pruebas, porque nadie revisa lo que no está.

**Qué tan bien decide, medido** (`focorouter evaluar`, sobre 42 tareas reales del vault)

| | |
| --- | --- |
| Acierto | **85,7 %** (36 de 42) |
| **Abaratadas** (a un modelo más barato del que les tocaba) | **0** |

Los seis fallos yerran todos hacia arriba, que es la asimetría que se diseñó. Ese número es también la respuesta a si hace falta el clasificador: mientras aguante, pagarle a un modelo para decidir a qué modelo mandar las cosas es gastar por gusto.

- Código: `cotejo/enrutador/` dentro del repo de [[proyecto|Cotejo]] (el `focorouter` original, archivado, está en `05-Archivo/focorouter`)
- Config: `~/.config/focorouter/config.json` — ahí se dice en qué carpeta trabaja el agente de cada proyecto. Variables sueltas: `COTEJO_CMD`, `FOCOROUTER_MOTOR`, `FOCOROUTER_CONFIG`, `FOCOROUTER_ESTADO`
- Protocolo para cualquier agente en `skills/focorouter/SKILL.md`, repartido al instalar a los agentes que ya estén en la máquina
- **Pensado para cuando [[proyecto|Cotejo]] se compile:** se le habla por su CLI y ninguna ruta se calcula al importar, así que el día del binario todo el cambio es `COTEJO_CMD=cotejo`. Hay una prueba que lo comprueba
- El informe `/ax` que guio el diseño está en el repo, en `REVISION-AX.md`

## ✅ Tareas
- [x] Escribir el set de ~30 frases reales con el nivel esperado, antes de programar las reglas #medio #agente/sonnet ^cotejo-7ikdqm
- [x] Crear el repo `enrutador` con las reglas, los niveles y el CLI #medio #agente/sonnet ^cotejo-kot6i9
- [x] Partir `preguntar()` de Eco en decidir + ejecutar, con una sesión por nivel #dificil #agente/opus ^cotejo-4u9ut2
- [x] Medir con el set de evaluación si las reglas solas alcanzan, antes de agregar el clasificador Haiku #medio #agente/opus — 2026-10-01 ^cotejo-lbmv7e
- [x] Parsear `#facil` / `#medio` / `#dificil` en `tareas/vault.py` y mostrarlas como chip en Cotejo #medio #agente/opus — 2026-10-01 ^cotejo-mzmhcw

## 🧠 Decisiones técnicas
> Una línea por decisión: **qué** se decidió, **por qué**, y qué se descartó.

| Fecha | Decisión | Motivo | Alternativas descartadas |
| --- | --- | --- | --- |
| 2026-09-17 | El enrutador es una bifurcación *antes* de invocar a Claude, no un parámetro de la llamada | Claude Code solo habla con la API de Anthropic: no se le puede pasar un modelo ajeno por `--model`. La decisión tiene que tomarse en un proceso propio que después elige a quién llamar | Resolverlo con un `--model` variable dentro del mismo comando de siempre |
| 2026-09-17 | Sin modelo local: descartado MiniCPM5-2B y cualquier LLM en la máquina | Un modelo de 2 B no corre el bucle agéntico (herramientas, editar archivos), así que su único papel posible era clasificar — y eso las reglas deterministas lo hacen gratis y sin latencia. Además, el equipo no tiene memoria de sobra para un modelo local.| MiniCPM5-2B por ollama (Q4_K_M, 1,56 GB); instalar llama.cpp para el mismo fin |
| 2026-09-17 | Reglas deterministas antes que cualquier modelo; el clasificador solo ve lo ambiguo | "Guarda esto en el segundo cerebro" se resuelve con un regex en microsegundos y a costo cero. Pagar un LLM para decidir cada trivialidad se come el ahorro que justifica el proyecto | Clasificar todos los mensajes con un LLM |
| 2026-09-17 | Ante la duda se escala, nunca se abarata: el default de cualquier fallo o timeout es Sonnet | Un ruteo barato equivocado arruina la tarea; uno caro equivocado cuesta unos centavos. La asimetría no está en el medio | Default a Haiku por ahorro; fallar y avisar sin responder |
| 2026-09-17 | Una sesión de Claude por nivel (`sesion.json` pasa de un id a `{haiku, sonnet, opus}`) | Cada mensaje headless recarga el contexto de la sesión. Con una sola sesión, Opus terminaría reabriendo un contexto lleno de "anota esto en el inbox" y pagando el recargo | Sesión única compartida entre los tres niveles |
| 2026-09-17 | El nivel es pegajoso dentro de una conversación: si ya subió, no vuelve a bajar hasta `SUPER+ALT+N` | El "sí, hazlo" que sigue a una propuesta de Sonnet es una frase corta y trivial vista sola: reclasificarla la mandaría a Haiku sin contexto | Reclasificar cada mensaje de forma independiente |
| 2026-09-17 | Repo propio `enrutador`, no un módulo dentro de claude-voz | [[proyecto|Cotejo]] tiene que poder decidir sin que el servicio de Eco esté vivo, y un hook o un script van a querer lo mismo | `claude_voz/enrutador.py` con Cotejo llamando al CLI de Eco |
| 2026-09-17 | Dificultad como tags nativos `#facil` / `#medio` / `#dificil` al final de la línea de la tarea | Son tags de Obsidian: se buscan y se filtran desde el vault, son greppables y no rompen el `- [ ]` | Campos Dataview (`[modelo:: opus]`), que se ven mal en modo lectura; archivo aparte con el mapa de dificultades |
| 2026-09-17 | [[proyecto|Cotejo]] solo etiqueta; encargarle la tarea a Claude queda fuera de alcance | Encargar es exactamente el diseño de Apps para agentes (estados, evidencia, validación humana) y merece el suyo, no colarse en el enrutador | Botón "Encargar a Claude" en esta misma fase |
| 2026-09-18 | Hay un cuarto destino, «humano», y no es un caso raro sino un nivel de primera clase | Al medir las 105 tareas reales del vault, 24 de las 68 pendientes no son para ningún modelo: comprar el dominio, que un abogado revise los textos, sacar la API key, verificar que el chip NFC lea a través del acrílico. Un enrutador de tres niveles las manda igual, y el modelo las toma, las intenta y las entrega a medias. El costo no son los tokens: es una entrega falsa que hay que revisar y devolver, justo lo que la columna En espera de comprobación existe para evitar | Elegir solo entre haiku, sonnet y opus, como estaba diseñado; dejar las tareas humanas fuera del enrutador y confiar en no despacharlas a mano |
| 2026-09-18 | El veto humano va antes que la etiqueta de dificultad, y después que la asignación #agente/x | Si Rafael escribió #agente/opus en «comprar el dominio», sabrá por qué: su decisión explícita gana. Pero #facil no dice «que lo haga un modelo», dice «es corto», y «Comprar 3 tarjetas de muestra #facil» ruteado a Haiku es un modelo intentando comprar tarjetas | Que el veto ganara también a la asignación, que quitaría a Rafael la última palabra sobre sus propias tareas; ponerlo al final, después de las reglas de nivel |
| 2026-09-18 | FocoRouter le habla a [[proyecto|Cotejo]] por su CLI y nunca importa sus módulos, aunque sería una línea | Cotejo se va a compilar para instalarse en otros dispositivos: ese día sus módulos quedan dentro de un binario y su CLI sigue estando, así que un «from tareas import fuente» sería una reescritura. Además la CLI ya es el contrato con esquema versionado, e importar los módulos es volver a atarse a los detalles que ese trabajo deshizo. Reapuntarlo el día del binario es COTEJO_CMD=cotejo y nada más | Importar tareas.fuente directamente, que cuesta 50 ms menos por llamada; copiar el escaneo del vault dentro del enrutador |
| 2026-09-18 | El defecto no llama a la API ni a `claude -p`: el trabajo lo hace un agente vivo (motor `agente`) | El caso real no es mandar trabajo a un proceso que nadie ve, es decirle a un agente que ya está abierto qué tarea le toca. El motor `agente` no lanza nada: toma la tarea en Cotejo y devuelve el encargo. `headless` (`claude -p`) sigue existiendo para lo desatendido —un hook, algo de madrugada— pero hay que pedirlo, y una prueba vigila que no vuelva a ser el defecto | `claude -p` como defecto, que era el diseño de la nota original; llamar a la API de Anthropic directamente |
| 2026-09-18 | Una instancia maestra reparte tareas abriendo instancias de verdad con `claude --bg --model <el que toque>` (motor `sesion`), no subprocesos ciegos | Son sesiones completas, con sus herramientas y permisos, que se abren con `claude attach <id>` y siguen vivas aunque cierres la maestra. Y el resultado no se lee de sus logs —`claude logs` devuelve el volcado del terminal con códigos de color, que no es formato para leer con un programa—: **el canal es Cotejo**, y cuando terminan aparecen en «En espera de comprobación» con su evidencia. Por eso no hay nada que parsear | `claude -p` y parsear su stdout; leer `claude logs` para saber cómo va cada instancia |
| 2026-09-18 | Una sesión no puede cambiarse de modelo a sí misma, y el protocolo lo dice en vez de fingir que sí | No existe herramienta para ello: `/model` lo escribe una persona. Así que cuando el modelo de la tarea no es el del agente que la mira, el protocolo le da dos salidas honestas —delegar en un subagente con ese modelo, o devolverla diciendo «esta es de Opus, escribe /model opus»— en vez de una instrucción que no se puede cumplir | Hacer que el agente intente cambiarse de modelo; asumir que siempre puede hacer cualquier tarea |
| 2026-09-18 | Si el modelo no lo dijo una persona, `despachar` se para y pregunta (código 6). Las reglas proponen, no autorizan | Ni las reglas ni la etiqueta de dificultad dicen «que lo haga un modelo»: proponen un tamaño. Quien decide gastar es una persona. El error trae la propuesta dentro justo para que se pueda preguntar con ella delante, y la respuesta se escribe en la nota con `tareas-obsidian asignar`, así que se pregunta una vez en la vida de la tarea y no una vez por despacho | Despachar con la propuesta de las reglas sin preguntar (queda como `--auto`, explícito); tratar la etiqueta de dificultad como si fuera una asignación de modelo |

## 📓 Bitácora
### 2026-09-18
- Arrancado el proyecto como **FocoRouter**, en su propio repo (hoy `05-Archivo/focorouter`): 9 módulos, CLI de 8 verbos, 72 pruebas en verde en 0,4 s y su propia skill repartida a Claude Code, Codex y opencode al instalar.
- Medidas las 105 tareas reales del vault a través de la CLI de [[proyecto|Cotejo]] antes de escribir una regla: 68 pendientes, de las que **24 (35 %) no son para ningún modelo**. Ese número cambió el diseño y añadió el nivel humano.
- Construido el set de evaluación con 42 tareas reales: 22 salen de las etiquetas `#facil`/`#medio`/`#dificil` que ya estaban escritas en las notas —la verdad de referencia es de Rafael, no inventada— y 20 revisadas a mano, casi todas del nivel humano, que no tenían tag porque el tag de dificultad no contempla ese caso.
- Reglas medidas y ajustadas con los fallos a la vista, en dos vueltas: 81 % con 3 abaratadas → **85,7 % con 0 abaratadas**. Se paró ahí a propósito: seguir afinando sobre 42 casos es memorizarlos.
- Fuera Eco del alcance. El enganche es [[proyecto|Cotejo]] y la entrada son sus tareas, no los mensajes de voz. Lo que quedó es una puerta abierta y no una dependencia: `focorouter decidir "<texto>"` rutea cualquier texto, así que Eco puede engancharse el día que toque sin que FocoRouter sepa que existe.
- Rediseñado el despacho alrededor de agentes vivos tras aclararlo Rafael: fuera la API y `claude -p` del camino normal. Motores nuevos `agente` (defecto, no lanza nada) y `sesion` (`claude --bg --model`, instancias abribles con `claude attach`); `headless` queda como opción que hay que pedir.
- Comprobado en la máquina que `claude --bg --model haiku` abre una sesión de verdad y devuelve su id corto, y que `claude agents --json` la lista. Sobre eso se construyó el motor `sesion`, no sobre suposiciones.
- **Primer uso real de punta a punta, de maestra.** Repartidas las 3 tareas de Enrutador con modelo asignado: dos a subagentes sonnet (verificar y entregar trabajo ya hecho) y una a una instancia opus abierta con `--motor sesion`. Las tres entregaron con evidencia y están en «En espera de comprobación». El enrutador no tuvo que adivinar en ninguna: las tres salieron por `asignacion`, confianza alta.

### 2026-09-17
- Diseñado el enrutador de punta a punta: niveles, orden de decisión, sesión por nivel y etiquetas en Cotejo.
- Verificado en el código que Eco arma hoy un solo comando con un modelo fijo y guarda una sola sesión.
- Evaluado y descartado MiniCPM5 tras confirmar que existe y que el dato del tamaño era correcto (2,5 B, 1,56 GB en Q4_K_M, disponible en ollama): el problema no era el tamaño sino que un 2 B no sirve para lo que hacía falta.

## 🪤 Problemas y soluciones
| Problema | Causa | Solución |
| --- | --- | --- |
| El motor `sesion` no encontraba el id de la instancia recién abierta, aunque `claude --bg` lo imprime | La salida lleva códigos de color y esos códigos tienen dígitos dentro (`ESC[36m`): la expresión regular enganchaba el «36» en vez del id | Quitar los códigos ANSI antes de buscar, en una función `identificador()` aparte, con una prueba que usa la salida literal capturada de `claude --bg` |
| La maestra no tenía dónde poner lo que sabe y la tarea no dice: despachar «crear el repo del enrutador» cuando el repo ya existía habría mandado a rehacer trabajo bueno | El encargo se armaba solo con el enunciado de la tarea y el estado que Cotejo conoce. El contexto de hoy —qué ya está hecho, qué no tocar, qué cambió— vive en la cabeza de quien reparte y no tenía camino hasta el encargo, así que la única salida era saltarse el enrutador y lanzar la instancia a mano | `focorouter despachar <id> --nota "..."`: viaja dentro del encargo, al final y anunciada, para que se lea como contexto y no como enunciado. Commit fa4402b, 80 pruebas |
| Las reglas del veto humano solo reconocen infinitivos: «comprar el dominio» da n0, pero «compra el dominio» cae en el defecto (sonnet) | Se escribieron midiendo las tareas del vault, que están todas en infinitivo. Por voz se habla en imperativo, así que en Eco el veto humano va a saltar poco. Lo encontró la instancia de opus al probar Eco de verdad, no una prueba | Pendiente. El arreglo no es solo añadir imperativos a los patrones: hace falta meter frases habladas en `datos/evaluacion.json` para poder medir si mejora o si empieza a vetar de más |

## 💡 Aprendizajes
- Un modelo local chico no se evalúa por su tamaño sino por el papel que puede cumplir: si lo único que sabe hacer es clasificar, compite contra un regex, no contra Haiku.
- En un sistema con costo por llamada, la asimetría de los errores decide el default: escalar de más cuesta centavos, abaratar de más cuesta la tarea.
- Si cada llamada recarga el contexto, mezclar niveles en una sola sesión traslada el historial barato al modelo caro. Las sesiones se separan por precio, no por tema.
- Un enrutador se diseña mirando el trabajo real, no los destinos que uno imagina. Los tres niveles (haiku, sonnet, opus) parecían agotar el problema hasta que medir el vault enseñó que una de cada tres tareas no es para ningún modelo. El destino que faltaba era el que no llevaba modelo.
- Cuando los errores son asimétricos, la tasa de acierto sola miente. Enrutar de más cuesta centavos; enrutar de menos arruina la tarea y hay que rehacerla. Por eso lo que se mide y lo que vigila una prueba no es el 85,7 %, es que las abaratadas sigan en cero.
- Un vault con tareas etiquetadas a mano es un set de evaluación ya escrito y gratis. Los `#facil`/`#medio`/`#dificil` que Rafael venía poniendo desde hacía días eran 22 casos con su respuesta correcta puesta por un humano; solo había que quitarles el tag y preguntarle a las reglas.
- Hablarle a un vecino por su CLI en vez de importar sus módulos cuesta 50 ms y compra que el vecino pueda compilarse sin avisar. La pregunta que lo decide no es cuál es más limpio hoy, sino cuál de los dos sobrevive al cambio que ya sabes que viene.
- Una prueba que llama a un modelo de verdad se acaba desactivando. Una de esta batería lo hizo sin querer —88 segundos y tokens gastados— y el arreglo no fue arreglar esa prueba, fue que ninguna pueda: `FOCOROUTER_MOTOR=imprimir` para todas, en el apoyo común.
- Cuando el trabajo lo va a hacer un agente y no un subproceso, el canal de resultados no es stdout: es el sitio donde ya vive el estado. Las instancias de `--motor sesion` no se vigilan por sus logs, se ven aparecer en la columna «En espera de comprobación» de CotejoBoard. Eso ahorró todo el parseo y, de paso, hace que el humano y el agente miren lo mismo.
- Un set de evaluación hereda el sesgo de dónde salió. Las 42 frases vienen de tareas escritas de Obsidian, todas en infinitivo, así que las reglas miden 85,7 % contra el registro para el que se escribieron y nadie se entera de que el hablado va peor. El hallazgo no salió de las pruebas: salió de usarlo por voz.
- Repartir una tarea empieza por mirar en qué estado está, no por despacharla. Dos de las tres tenían el trabajo ya hecho: mandarlas tal cual habría sido pedir que se rehiciera y se pisara. La maestra que no comprueba antes convierte el enrutador en una máquina de duplicar trabajo.

## 🔗 Enlaces
- Código: `cotejo/enrutador/` (ver `CLAUDE.md` y `README.md` de Cotejo) · repo original archivado: `05-Archivo/focorouter` (`REVISION-AX.md`)
- Demo: `focorouter plan` · `focorouter despachar <id> --simular`
- Relacionados: [[proyecto|Cotejo]] · [[revision-ax-de-cotejo|Revisión AX de Cotejo]] · Apps para agentes · Eco · Segundo Cerebro

## ⏭️ Siguiente paso
- **Usarlo unos días antes de automatizar nada.** Es la misma espera que pidió [[revision-ax-de-cotejo|Revisión AX de Cotejo]] y por lo mismo: lo que no se puede adivinar es si el reparto se aguanta en la práctica. El dato a mirar es `focorouter bitacora`, y la pregunta, si alguna decisión molestó.
- Marcar en CotejoBoard las tareas de este proyecto que ya están hechas: **esa transición es tuya** y ni el enrutador ni Cotejo tienen verbo para hacerla. Las que quedaron cubiertas son el set de evaluación, el repo con reglas/niveles/CLI, medir si las reglas alcanzan y sacar los precios de la skill `claude-api`.
- Las tres tareas de Eco que quedan en esta lista (partir `preguntar()`, override por voz, mostrar qué cerebro contestó) están **fuera del alcance de FocoRouter** y siguen siendo de Eco. Engancharlo el día que toque no le pide nada al enrutador: `focorouter decidir "<texto>"` ya rutea cualquier texto.
