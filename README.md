# Cotejo

> **Tus agentes entregan. Tú compruebas.** Cotejo se llamó Foco hasta septiembre de 2026: el comando `foco`, las variables `FOCO_*`, la carpeta `~/.config/foco` y las tareas con marca `^foco-…` siguen funcionando.

**Cotejo es el tablero de control para hacer vibe coding profesional.** Tus agentes escriben el código; Cotejo organiza el proyecto y verifica lo que entregan. No escribe código por ti: lleva el proyecto y comprueba lo que se hizo.

Sirve para que cualquier persona, programe o no, construya software con IA de forma estructurada y que pueda crecer:

- Cada proyecto guarda su contexto, sus decisiones y su arquitectura en una carpeta `.cotejo/` dentro de su propio repo, que cualquier agente consulta barato.
- Cada tarea va al modelo adecuado: el [enrutador](#quién-atiende-cada-tarea) decide a quién le toca y por qué.
- Nada se da por hecho sin evidencia y sin tu revisión: el agente entrega con pruebas, y marcar una tarea como hecha es siempre cosa tuya, en CotejoBoard.

Se usa con cualquier agente de terminal (Claude Code, Codex, Antigravity CLI, Gemini CLI, opencode) o con cualquier agente que hable MCP. Es gratis, en Windows y Linux.

> [!WARNING]
> **Cotejo 1.2 es software en fase beta.** Todavía puede tener fallos o comportarse de forma
> inesperada. Se ofrece «tal cual», sin garantías de ningún tipo, como dice su licencia
> ([`LICENSE`](LICENSE), cláusula 8). Si algo falla, cuéntalo en un [issue](../../issues).

**Descargar:** la [última versión](../../releases/latest) trae el instalador de Windows, el paquete
de Arch y el `.tar.gz` para otras distribuciones de Linux, con sus `SHA256SUMS`. O instala con una
línea, como en el paso 1 de abajo.

**El código está a la vista, pero no es open source.** Cotejo es software propietario de uso
gratuito: puedes leer, revisar y auditar este código, y reportar fallos, pero no copiarlo,
modificarlo ni redistribuirlo (ver [`LICENSE`](LICENSE), cláusulas 2.4 y 3).

## Empezar en un repo

Cuatro pasos, de la instalación a la primera tarea comprobada.

**1. Instala Cotejo.** Una línea, sin clonar nada (el detalle, las opciones y el paquete de Arch están en [«Instalar»](#instalar)):

```sh
curl -fsSL https://cotejo.dev/install.sh | sh
```

**2. Corre `cotejo init` en la carpeta del proyecto.** Crea el `.cotejo/` del repo —`tareas.md`, `proyecto.md` y una carpeta por cada tipo de conocimiento: decisiones, arquitectura, problemas, aprendizajes, bitácora, referencias y recursos—, deja el proyecto en la versión 0.1.0 y lo registra en la fuente `repo`. Si no tenías ninguna fuente que funcione (lo normal en una instalación nueva), la deja activa; si ya usas Obsidian o Notion y funcionan, no te la cambia, y `cotejo fuentes usar repo` lo hace cuando quieras. Es idempotente: repetirlo no pisa nada.

```sh
cd /ruta/al/proyecto
cotejo init                    # dentro de un repo git
cotejo init --repo ~/mi-app    # también sirve para una carpeta nueva o sin git: la crea y le hace git init
```

**3. Pídele a tu agente que arranque el proyecto.** Dile «empiezo un proyecto» o «prepara este repo para trabajar con Cotejo». La skill `cotejo` (`skills/cotejo/referencias/inicio.md`, se instala con Cotejo) lo entrevista en un solo mensaje de cinco preguntas con valores por defecto y deja escrito el objetivo, el stack y el siguiente paso en `proyecto.md`, las decisiones que condicionan lo demás **como propuestas**, una arquitectura inicial y entre 3 y 8 tareas para la 0.1.0. Si el proyecto ya existe en Obsidian o Notion, ver [«Traer un proyecto que ya existe»](#traer-un-proyecto-que-ya-existe-desde-obsidian-o-notion).

**4. Trabaja las tareas y compruébalas en el board.** El agente reparte la 0.1.0 (`cotejo plan`), toma cada tarea, la hace y la entrega con evidencia: commits, diff y pruebas que Cotejo puede volver a correr. En [CotejoBoard](#cotejoboard) aceptas las decisiones propuestas, compruebas lo que se entregó y apruebas. `cotejo doctor` dice si algo no funciona y qué hacer.

```sh
cotejo plan --proyecto mi-app    # qué modelo recibiría cada pendiente
cotejo version --proyecto mi-app # en qué versión van y cuántas tareas quedan
cotejo                           # abre o cierra CotejoBoard
```

Tus agentes entregan. Tú compruebas.

## Para agentes

Cotejo tiene una cara sin interfaz, pensada para que un agente trabaje contra el segundo cerebro sin pagar el arranque de GTK y sin editar el Markdown a mano. Sale todo en JSON por la salida estándar. El comando se llama `cotejo`; `tareas-obsidian` es el mismo programa con su nombre de antes, y sigue funcionando.

```sh
cotejo tareas --proyecto Cotejo                      # cuáles faltan (por defecto excluye hechas)
cotejo tareas --proyecto Cotejo --todas              # todas, incluyendo hechas
cotejo tareas --proyecto Cotejo --estado hecha       # solo hechas
cotejo crear "..." --proyecto Cotejo                 # anotar trabajo nuevo
cotejo tomar <id> --agente opus                    # pendiente → haciéndola
cotejo entregar <id> --evidencia "..."             # haciéndola → para comprobar
    [--prueba "pytest -q"]... [--repo <carpeta>]             # + rama, commits, diff y pruebas
cotejo comprobar <id>                              # vuelve a correr esas pruebas; no escribe nada
cotejo bloquear <id> --motivo "..."                # haciéndola → pendiente, sin dueño
cotejo asignar <id> sonnet                         # cambiar de dueño
cotejo estado                                      # los conteos de siempre
cotejo ahorro                                      # qué costó enterarse por aquí
```

Y, para lo otro que necesita saber un agente —**a quién le toca cada tarea**—, los verbos del enrutador:

```sh
cotejo plan --proyecto Cotejo --solo-despachables    # qué modelo recibiría cada pendiente
cotejo decidir --tarea <id>                        # a quién le toca esa, y por qué
cotejo despachar <id>                              # tomarla a nombre de ese modelo
cotejo modelos                                     # el catálogo de niveles y modelos registrados
cotejo revisar                                     # qué pasó con lo que se repartió
cotejo protocolo                                   # el trato entero, para leerlo
cotejo maestro --proyecto Cotejo --cliente claude    # abrir un agente que reparte las asignadas
cotejo importar plan plan.md --proyecto Cotejo       # qué tareas sacaría; ensayo por defecto
cotejo importar obsidian Cotejo --detalle            # qué entradas de .cotejo/ saldrían de la nota; ensayo
cotejo importar notion Cotejo --destino <carpeta>    # igual, desde una base de Notion
    [--aplicar]                                              # y con esto, las crean de verdad
```

Y, para el conocimiento del repo que no son tareas —decisiones, arquitectura, problemas,
aprendizajes, bitácora y referencias, cada uno en `.cotejo/` (ver [«El almacén»](#el-almacén-el-conocimiento-del-repo) más abajo)—:

```sh
cotejo contexto                                             # objetivo, tareas, decisiones y problemas vigentes, temas
cotejo buscar --tipo decision --temas auth                  # una línea por entrada; barato
cotejo leer dec-x7k2                                        # la entrada completa, con su `version`
cotejo proponer decision --titulo "..." --temas auth --texto "..."   # propuesta; la acepta una persona
cotejo anotar problema --titulo "..." --temas ci --texto "..."
cotejo bitacora "qué se hizo hoy"
cotejo editar arq-9f1a --version <hash> --texto "..."       # arquitectura, referencia o proyecto.md
cotejo resolver pro-9f3a --solucion "..."
```

`entregar` guarda además **evidencia que se puede volver a comprobar**: si se corre dentro de un repo git (o con `--repo <carpeta>`), la rama, los commits desde la rama base y el resumen del diff (archivos con sus +/-); y cada `--prueba "<comando>"` la corre Cotejo mismo, sin shell y con tiempo límite, y anota su `argv`, el final de su salida y su código de salida. Todo va a `bitacora.jsonl` junto al texto de `--evidencia`, en claves que se agregan (`git`, `pruebas`, `evidencia_esquema`). Una prueba en rojo no frena la entrega —puede venir roja de antes—, pero se avisa y queda anotada con su código.

Si la tarea es de un repo de git, `despachar` le crea por defecto **su propio worktree**, fuera del repo y del vault, con una rama `cotejo/<id>`: es donde trabaja y commitea el agente, y de donde `entregar` saca la evidencia sin que dos tareas del mismo repo se pisen. `--sin-aislar` (o `enrutador.worktrees.aislar: false` en la config) vuelve al comportamiento de antes, para una tarea que no toca código o un repo donde no conviene. `cotejo worktrees` lista dónde quedó cada uno —con `--limpiar`, retira los que ya sobran (la tarea se aprobó, se devolvió a Pendiente o ya no existe)—; nunca borra una rama ni algo sin commitear. El board retira el de una tarea sola al aprobarla o devolverla.

`comprobar <id>` lee, no escribe: vuelve a correr —en ese mismo worktree, si lo tiene— las pruebas que anotó la última entrega, con su mismo `argv` y su mismo tiempo límite, y dice si el resultado sigue igual. Es lo que usa también el botón **Comprobar** de CotejoBoard; aprobar la tarea sigue siendo de una persona.

`importar plan` convierte un `plan.md` en tareas: lee sus casillas `- [ ]` o, si no hay ninguna, sus encabezados de paso (`## Paso N`, `### Tarea N`), y para cada una propone la dificultad y el modelo igual que `decidir`. Es un **ensayo por defecto** —nunca toca el vault sin `--aplicar`—, y repetirlo no duplica: una tarea que ya existe en el proyecto con el mismo texto sale con `"creada": false`.

`importar obsidian <proyecto>` es el ensayo de traer un proyecto del vault a su `.cotejo/` (1.2): localiza la nota, sus subnotas (las de su carpeta y las que dicen `proyecto: "[[X]]"`) y los adjuntos que enlazan; resuelve el repo (`repo:` local, un `.git` dentro de la carpeta del proyecto, o `--destino`) y reparte cada sección de la plantilla a su tipo: decisiones y problemas por fila de tabla, aprendizajes por viñeta, la bitácora por `### fecha`, las tareas a `tareas.md` y Objetivo, Stack, Enlaces y Siguiente paso a `proyecto.md`. Lo que no encaja sale en `sin_clasificar` con su motivo, y los archivos sueltos que nadie enlaza se cuentan en `no_enlazados` sin importarse. **No escribe nada**, ni en el vault ni en el repo.

Con `--aplicar` escribe ese mismo plan en el `.cotejo/` del repo (y le hace `git init` si `--destino` no era un repo): las decisiones como `aceptada` con `autor: importado`, los adjuntos copiados a `recursos/` con su ficha, y los enlaces reescritos —a la nota del proyecto van a `[[proyecto]]`, a una subnota a su referencia y a otra nota del vault quedan como texto con su origen—. Crea la tarea «Revisar lo importado: resúmenes, temas y fichas» y apunta el proyecto en `migrados` de la fuente obsidian, que desde entonces lo lee del repo. **No hace commit** y no toca la nota del vault: quitar el proyecto de `migrados` lo deshace. Repetirlo no duplica nada (cada entrada guarda su `origen`), y se niega sin escribir si el repo ya tiene otras tareas.

Marcar un proyecto como migrado no apaga el resto del vault: con la fuente `obsidian` activa, los proyectos de `migrados` se leen de su repo y todos los demás siguen leyéndose de las notas, los dos a la vez y bajo el mismo `--proyecto` de siempre (es la fuente `obsidian` envuelta en `tareas/fuentes/compuesta.py`, transparente para quien la usa). Mientras dure una migración gradual puede haber tareas en los dos sitios; lo resuelve justamente que cada proyecto cuenta una sola vez, del lado que diga `migrados`.

`importar notion <proyecto>` es la misma idea para una base de Notion (1.2 · D3), y más modesta: trae las tareas por el adaptador que ya tengas registrado (mismo formato, a `tareas.md`) y cada página de la base como una referencia con `resumen: pendiente`, también con `--destino`/`--aplicar`/`--detalle` y ensayo por defecto. **No marca el proyecto como migrado de la fuente Notion** —Notion sigue leyéndose igual, sin la fuente compuesta que sí tiene Obsidian—, así que mientras no cambies de fuente puede haber el mismo proyecto en Notion y en su `.cotejo/`; `--destino` solo hace falta la primera vez, porque Cotejo recuerda el repo para la siguiente corrida.

`bloquear` es la salida honesta: la tarea no se puede terminar, vuelve a *Pendiente* sin dueño y con el motivo a la vista. Sin ese verbo, un agente atascado solo tenía dos salidas y las dos son peores: dejarla en *Haciéndola* ocupando la columna sin que nadie sepa por qué, o entregarla a medias, que mete en *Para comprobar* algo que no hay nada que comprobar. El motivo es obligatorio por la misma razón que la evidencia: una tarea que vuelve a *Pendiente* sin explicación la toma el siguiente agente para estrellarse contra lo mismo.

`crear` es la contraparte de poder leer lo que falta: sin él, un agente que encuentra trabajo sin anotar solo puede decírselo a quien le esté leyendo, y eso se pierde al cerrar la sesión. La tarea cae con las demás de la nota principal del proyecto —no al final del archivo, donde viven las decisiones—, nace pendiente, sin dueño y con su marca de bloque puesta, porque quien la crea va a querer nombrarla en la llamada siguiente. Repetirlo es seguro: si el proyecto ya tiene una tarea sin terminar que dice exactamente lo mismo, devuelve esa con `"cambio": false`. `--proyecto` prefiere el nombre exacto («Cotejo» no es ambiguo aunque exista «Cotejo - Planning para Producción»). No se crea en las carpetas sueltas (Inbox, Diario): no tienen nota principal, y elegir en cuál cae la tarea sería inventarse dónde vive. Crear un **proyecto** tampoco está: es una nota nueva en el segundo cerebro, y la escribe una persona.

**No hay verbo para finalizar, y esa ausencia es el diseño.** Si el agente puede marcar hecha su propia tarea, «hecha» deja de significar «alguien la revisó» y pasa a significar «el agente cree que terminó». Marcar `[x]` se hace en CotejoBoard, con la mano.

Por qué existe esta CLI y no basta con que el agente edite las notas: `vault.py` comprueba que la línea siga exactamente igual que cuando se leyó antes de escribir, y reemplaza el archivo de forma atómica. Editar por fuera se salta esa verificación, y la forma de fallar es pisar trabajo ajeno en silencio.

Enterarse por aquí es entre 5 y 10 veces más barato que leer las notas: las pendientes de un proyecto son ~480 tokens contra ~4.700 de la nota entera, y las 101 tareas del vault son ~7.300 contra ~36.600. Hay tres tamaños para pedir, y conviene usar el más chico que sirva: `estado` (~80 tokens) → `tareas` con filtros → la nota entera, solo si de verdad hace falta el contexto. Ese número ya no hay que creérselo: `cotejo ahorro` lo mide sobre las llamadas que de verdad se hicieron (ver más abajo).

Cada escritura devuelve la tarea como quedó, para no tener que volver a preguntar, y trae `"cambio": false` cuando no hizo falta tocar nada — repetir una operación es seguro. Los errores traen `salida`, que dice qué hacer, y `reintentable`, que dice si vale la pena repetir:

```json
{"error": "La nota Cotejo.md cambió desde que leíste la tarea",
 "salida": "Vuelve a pedir `tareas` y repite la operación con el id nuevo. No se escribió nada.",
 "reintentable": true}
```

El `id` de una tarea sale de `tareas` y **no se construye a mano**. Es la marca de bloque de su línea (`cotejo-a1b2`), que viaja con la tarea aunque alguien edite la nota por arriba o la mueva de sitio; se acepta con `^` delante, que es como se ve en la nota. Una tarea gana su marca la primera vez que se le escribe, así que las que nadie ha tocado todavía se nombran por su nota y su número de línea, y ese sí se mueve: si el id deja de resolver, el error lo dice y la salida es volver a listar.

Si un id llegara a responder a dos tareas, la operación se niega y las nombra en vez de escribir en la primera que encuentre: pisar la tarea equivocada en silencio es la peor forma de fallar.

`tareas` y `tomar` traen además `evidencia` o `motivo` cuando la tarea tiene una: lo último que se dijo de ella. En una tarea devuelta eso es el motivo del rechazo, y es lo que hay que leer **antes** de rehacerla.

Cada operación se anexa a `~/.local/state/tareas-obsidian/bitacora.jsonl`, una línea de JSON por cambio (ver más abajo).

Si alguna nota no se pudo leer, la respuesta trae `avisos` con cuál y por qué. Importa: las tareas de esa nota no están en la lista, y sin el aviso eso se ve igual que una nota sin tareas.

`COTEJO_VAULT` y `COTEJO_CARPETA_PROYECTOS` apuntan a otro vault en una sola invocación, sin tocar la config; `COTEJO_CARPETAS_SUELTAS` (separadas por comas, vacía para apagarlas) hace lo mismo con las carpetas sueltas.

### El almacén: el conocimiento del repo

Además de `tareas.md`, un repo puede llevar en `.cotejo/` el resto de lo que no es código pero
informa el desarrollo —decisiones, arquitectura, problemas, aprendizajes, bitácora y
referencias— (1.2 · A1/A2), cada entrada en su propio archivo de Markdown con un frontmatter
mínimo y un `id` estable (`dec-x7k2`, `pro-9f3a`, `arq-4m1p`…) que no cambia aunque el archivo
se renombre. `cotejo init` crea el esqueleto entero; qué carpeta le toca a cada tipo está en
«[La fuente repo](#la-fuente-repo)», más abajo.

**Para enterarse, de menos a más** (B1/B2):

| Verbo | Qué devuelve |
| --- | --- |
| `cotejo contexto [--tope N]` | Objetivo, stack y siguiente paso de `proyecto.md`; tareas por estado; las `--tope` decisiones y problemas vigentes más recientes (10 por defecto, con el total real); y los temas que existen. Pensado para costar menos de 1k tokens |
| `cotejo buscar [--tipo] [--temas] [--estado] [--desde] [--texto] [--limite]` | Una línea por entrada (id, tipo, título, resumen): el camino barato para decidir qué vale la pena leer entero |
| `cotejo leer <id>` | La entrada completa, con su cuerpo y su `version` (hash); de un recurso, la ruta de su archivo y si existe, nunca el contenido |

Los tres aceptan `--repo <carpeta>`; por defecto es la raíz git desde donde se llama.

**Para escribir** (C1-C3):

| Verbo | Qué hace |
| --- | --- |
| `cotejo proponer decision --titulo --temas --texto [--reemplaza <dec-id>] [--autor]` | Crea una decisión en `propuesta`. Con `--reemplaza`, al crearla deja la vieja en `reemplazada` |
| `cotejo anotar <problema\|aprendizaje\|referencia\|arquitectura> --titulo --temas --texto` | Una entrada nueva de ese tipo, con su id |
| `cotejo anotar arquitectura --titulo --pieza "capa\|nombre\|frase\|tecnología\|tareas"` | La arquitectura dibujable: una pieza por `--pieza`, en las capas `ve`, `hace`, `guarda` o `conecta`; `leer` le pone a cada una su estado según sus tareas |
| `cotejo bitacora "texto"` | Añade al final del archivo del día; nunca reescribe |
| `cotejo editar <id> --version <hash> --texto` | Cambia el texto de una arquitectura, una referencia o `proyecto.md`. Se niega si `--version` no coincide con la que tiene ahora, igual que `TareaCambiada` con las tareas |
| `cotejo resolver <pro-id> --solucion "..."` | Problema `abierto` → `resuelto`, con la solución que lo cerró |

Toda escritura devuelve la entrada que dejó (`id`, `ruta`, `version`), para no tener que
releerla. **Las decisiones no se editan nunca**: su texto es fijo y una que ya no aplica se
reemplaza con `proponer decision --reemplaza <dec-id>`; `editar` sobre una decisión se niega y
dice eso.

**Lo que ningún verbo hace, a propósito: aceptar una decisión** (C5). `proponer decision` la
deja `propuesta`; pasarla a `aceptada` es de la persona, y solo desde CotejoBoard —sale como
carta propia en *Para comprobar*, con la misma vista de revisión que una entrega: su texto y,
si reemplaza otra, la vieja al lado, con el único botón de **Aceptar**—. Revisar o aprobar una
tarea que propuso una decisión solo avisa que lo hizo, sin aceptarla ahí: aprobar la entrega y
aceptar la decisión son dos firmas distintas, y la misma prueba que vigila que no haya verbo
para finalizar (`test_no_hay_ningun_verbo_para_finalizar_una_tarea`) vigila que tampoco lo haya
para aceptar.

### Con cualquier agente

Cotejo también habla MCP: `cotejo mcp` sirve los mismos verbos como tools del [Model Context Protocol](https://modelcontextprotocol.io), por stdio y sin dependencias. Gratis en Windows y Linux.

**Para Claude Code, Codex, Gemini CLI u opencode,** el instalador lo configura automático. Si lo usas desde otro cliente MCP:

```json
{"mcpServers": {"cotejo": {"command": "cotejo", "args": ["mcp"]}}}
```

Por defecto sirve el **núcleo** de verbos —`contexto`, `tareas`, `buscar`, `leer`, `crear`, `tomar`, `entregar`, `bloquear`, `anotar_*` y `bitacora`—; `"args": ["mcp", "--perfil", "completo"]` sirve todos. Qué verbo es del núcleo lo dice su definición en el analizador (`cli.nucleo()`), no una lista en `mcp.py`.

### Por MCP

El protocolo es lo mismo: el catálogo sale del analizador de la CLI —un verbo con acciones da una tool por acción, `fuentes_info`, `temas_usar`, `importar_plan`, `importar_obsidian`, `importar_notion`, `proponer_decision`, `anotar_problema`, `anotar_aprendizaje`, `anotar_referencia`, `anotar_arquitectura`—, cada llamada corre el verbo de verdad y devuelve su mismo JSON (en `content` y en `structuredContent`), y un error del verbo vuelve como resultado con `isError`. Una bandera nueva en la CLI aparece sola como parámetro. Y la ausencia también se hereda: **no hay tool para finalizar una tarea ni para aceptar una decisión**; `test_no_hay_ningun_verbo_para_finalizar_una_tarea` vigila los verbos y las tools de las dos cosas.

Claude Code (`.mcp.json` del proyecto, o `claude mcp add cotejo -- cotejo mcp`):

```json
{"mcpServers": {"cotejo": {"command": "cotejo", "args": ["mcp"]}}}
```

Cursor (`.cursor/mcp.json`) usa la misma forma. OpenCode (`opencode.json`):

```json
{"mcp": {"cotejo": {"type": "local", "command": ["cotejo", "mcp"]}}}
```

Para probarlo sin tocar el vault de verdad, se le pasan `COTEJO_VAULT`, `COTEJO_CONFIG` y `XDG_STATE_HOME` en el `env` (`environment` en OpenCode) del servidor. `entregar --repo` y `init --repo` toman por defecto la carpeta donde el cliente arrancó el servidor; desde MCP conviene pasarlos.

## El medidor de ahorro

La frase de arriba —«entre 5 y 10 veces más barato»— era una estimación, y una app que se justifica con un ahorro debería poder enseñarlo medido. Las dos mitades del número se pueden medir, y por eso se miden:

- **lo que costó** es el tamaño de lo que la CLI devolvió, que es exactamente lo que el agente se lleva al contexto;
- **lo que habría costado** es el tamaño de las notas que la fuente tuvo que leer para contestar, que ya las leyó y las tiene en la mano.

Lo único que no se mide es el supuesto de en medio —que sin Cotejo el agente habría leído esas notas enteras—, así que viaja dentro del dato, en la clave `supuesto`, y sale escrito debajo del número en el board. Un ahorro que esconde su supuesto detrás de un total redondo es una medalla, no una medida.

```sh
cotejo ahorro
{"esquema": 1, "lecturas": 4, "devuelto": 37098, "leido": 730071, "desde": 1789750039,
 "razon": 19.7, "tokens_devueltos": 10305, "tokens_ahorrados": 192492,
 "caracteres_por_token": 3.6, "supuesto": "Lo medido son los caracteres que devolvió la CLI…"}
```

Se cuenta en caracteres, que es lo que hay sin volver a tocar nada; los tokens salen de dividir por una constante declarada, que viaja en la respuesta (`caracteres_por_token`). La `razon` no depende de ese divisor y es la cifra más defendible; en el board se enseña el total de tokens porque es lo que la gente quiere saber.

En CotejoBoard sale bajo el tablero: dos líneas en mono y plata, como el conteo de cada chip, sin el verde de la pastilla de al lado —el verde es para lo que espera que lo compruebes, y esto no espera nada— y sin parada de `Tab`.

```
(192.492) Tokens ahorrados
frente a leer las notas enteras
```

La segunda línea no es un subtítulo: es el supuesto, y por eso no se va. Fuera de la barra, por la misma decisión que hace que el botón no lleve el total de pendientes: un número permanente y a la vista es FOMO. Sin ninguna lectura contada, el pie no sale.

Lo que lo mantiene honesto:

- **Vive en su propio archivo** (`~/.local/state/tareas-obsidian/ahorro.json`), con los totales acumulados y los de los últimos 30 días, y reemplazo atómico, no en `bitacora.jsonl`: una línea por lectura llenaría la bitácora de ruido y encarecería justo el camino que el medidor dice abaratar.
- **Contar no cuesta.** Nada del medidor abre una nota: se le pregunta a la fuente cuánto pesaba lo que ya leyó (`Fuente.leido()`), y la nota principal —que se lee dos veces, para el frontmatter y para las tareas— se cuenta una sola.
- **Puede dar menos de uno.** Con notas chicas, el JSON que las describe pesa más que ellas, y entonces el board dice «(43) Tokens de más hoy». Un medidor que solo sabe felicitar es un cartel.
- **Solo cuenta `tareas`**, el camino por el que un agente se entera. `estado` no, porque lo llama el widget de la barra cada pocos minutos sin nadie detrás.

Lo que todavía no es exacto: `escanear` lee el vault entero aunque se pida `--proyecto`, así que con ese filtro la mitad cara cuenta notas que la respuesta no necesitaba, y el número sale inflado. Está anotado como tarea (cotejo-mbzjoj).

## Quién atiende cada tarea

Cotejo resuelve *qué* hay que hacer. El enrutador (`enrutador/`) resuelve *quién lo hace*: los modelos configurados y una persona. Vivía en su propio repositorio y se mudó aquí dentro, porque las dos preguntas son de la misma tarea y separarlas costaba un subproceso por pregunta.

| Nivel | Quién | Para qué | USD / Mtok (entrada · salida) |
| --- | --- | --- | --- |
| n0 | **una persona** | Comprar, firmar, llamar a alguien, abrir una cuenta, tocar algo físico, decidir por gusto | — |
| n1 | `claude-haiku-5-5` | Trabajo mecánico y acotado | 0,10 · 0,50 |
| n2 | `claude-sonnet-5-5` | El trabajo normal de código. **El defecto** | 2 · 10 |
| n3 | `claude-opus-5-5` | Arquitectura, contratos, lo que cruza varios archivos | 4 · 20 |

Al medir las 105 tareas reales del vault apareció lo que acabó siendo lo más útil del enrutador, y que ningún diseño previo contemplaba:

> **24 de las 65 tareas pendientes no son para ningún modelo.** «Comprar el dominio miempresa.co», «Que un abogado revise los textos», «Sacar la API key en console.anthropic.com», «Comprar 3 tarjetas de muestra y verificar que el chip NFC lea».

Un enrutador que solo elige entre haiku, sonnet y opus manda todas esas a un modelo. Y el modelo las toma, las intenta y las entrega a medias: una entrega falsa que alguien tiene que revisar y devolver, que es exactamente lo que la columna *Para comprobar* existe para evitar. Por eso `humano` es un destino de primera clase, con su veto, y **no hay bandera para forzarlo**.

Cómo decide, de lo más explícito a lo más adivinado, y cada escalón dice por qué ganó:

```
1. --modelo          una persona lo está pidiendo ahora mismo          confianza alta
2. asignación        ya estaba escrito en la nota (#agente/opus)       confianza alta
3. veto humano       nadie lo asignó y el texto dice que no es para un modelo
4. dificultad        una persona etiquetó el tamaño (#facil/#medio/#dificil)
5. reglas            regex sobre el texto, gratis
6. defecto           sonnet
```

Dos decisiones sostienen ese orden. **El veto va antes que la dificultad**: `#facil` no dice «que lo haga un modelo», dice «es corto», y «Comprar 3 tarjetas de muestra #facil» ruteado a Haiku es un modelo intentando comprar tarjetas. Y **ante la duda se escala, nunca se abarata**: un ruteo caro equivocado cuesta unos centavos; uno barato equivocado arruina la tarea y hay que rehacerla.

Las reglas **proponen, no autorizan**: si nadie asignó el modelo, `despachar` se niega con código `6` y enseña la propuesta para que puedas preguntarla, y la respuesta se escribe en la nota con `asignar`. `--auto` es la excepción explícita.

`cotejo evaluar` mide las reglas contra 42 tareas reales del vault etiquetadas a mano: hoy, **85,7 % de acierto y 0 abaratadas**. Ese número es el que decide si algún día hace falta un clasificador; mientras siga así, pagarle a un modelo para decidir a qué modelo mandar las cosas es gastar por gusto.

**El trabajo lo hace un agente vivo, no la API.** El motor por defecto (`agente`) no lanza nada: toma la tarea y te devuelve el encargo para que lo hagas tú o se lo pases a un subagente con ese modelo. `--motor sesion` abre una instancia de verdad (`claude --bg --model`), que se dirige con `claude attach`. `--motor headless` existe para lo desatendido y hay que pedirlo: lanza **el cliente que ejecuta el modelo** según el catálogo —`claude -p` para los de Claude, `opencode run -m opencode-go/kimi-k2.7-code` para una tarea de `#agente/kimi-k2.7-code`, `codex exec`, `gemini -p`, `agy -p` (Antigravity CLI)—. `sesion` solo sabe abrir Claude Code y lo dice antes de tomar nada; y si el cliente no está instalado, `despachar` se niega **sin tomar la tarea**, en vez de dejarla en *Haciéndola* a nombre de un modelo que nunca empezó.

### El maestro

Con un proyecto elegido en CotejoBoard, la barra del Maestro del pie lo abre. En la barra se puede escribir una indicación opcional («solo las de la v1.2.4», «primero las de la web») que el maestro lee al abrirse; acota qué reparte y en qué orden, pero no le deja saltarse ninguna regla. **Abrir maestro** (o Enter; con texto el botón dice **Enviar al maestro**) usa el último cliente con que se abrió, y la flecha del mismo botón despliega todos los instalados —Claude Code, OpenCode, Codex, Gemini CLI, Antigravity CLI— para elegir otro. Al abrir el maestro se abre **en una terminal nueva que se ve** con una primera instrucción: ser el maestro de ese proyecto. Lo mismo desde la CLI:

```sh
cotejo maestro --proyecto Cotejo --cliente opencode [--modelo opencode-go/kimi-k3] [--indicacion "..."] [--simular]
cotejo maestro --clientes            # cuáles sabe abrir y cuáles están instalados
```

El maestro reparte **solo las tareas pendientes que una persona asignó a un modelo** (`#agente/<modelo>`, lo mismo que `plan --solo-asignadas`): cada una con `despachar --motor headless`, que lanza el cliente de ese modelo. Después comprueba que cada modelo entregó; si uno no pudo —se quedó sin permisos, se cortó—, mira qué hizo y entrega con evidencia o bloquea con el motivo. No usa `--auto` ni `--modelo`, y tampoco finaliza: `[x]` sigue siendo tuyo. Sin tareas asignadas no se abre nada, y el aviso dice cómo asignarlas.

Se abre en una terminal y no en segundo plano por la misma razón por la que el motor por defecto no lanza nada: el trabajo que nadie ve es el que no se quería. Si el proyecto no tiene carpeta en `enrutador.proyectos`, la instrucción le pide al maestro que te pregunte dónde trabajar antes de despachar.

Para que un modelo que trabaja sin interfaz pueda editar archivos y correr `cotejo entregar`, su cliente tiene que tener permisos: `motores.headless.argumentos_extra` para Claude (por ejemplo `["--permission-mode", "acceptEdits", "--allowedTools", "Bash(cotejo:*)"]`) y `motores.headless.clientes.<cliente>.argumentos_extra` para los demás. Cotejo no pone ninguno por su cuenta: qué puede tocar un modelo sin que lo mires lo decides tú.

### Si el reparto sirvió

Antes de repartir varias en paralelo, **`capacidad` dice cuántas caben ahora** en la máquina donde corre, para no llevarla al OOM:

```sh
cotejo capacidad --proyecto Cotejo   # caben, qué lo limita, y cuáles ahora y cuáles esperar
```

Mide al preguntar —memoria disponible, la parte del swap libre que cuenta, CPUs y carga, y los agentes que ya están en marcha con el árbol de procesos de cada uno— y divide lo que queda, menos una reserva, entre lo que cuesta un agente. Ese costo es un supuesto (1500 MB) que los agentes en marcha solo pueden subir: uno en reposo ocupa menos que trabajando, así que medirlo nunca reparte de más. Los supuestos se cambian en `enrutador.capacidad` de la config (`mb_por_agente`, `reserva_mb`, `fraccion_swap`, `cpu_por_agente`, `maximo`). No escribe nada, y la respuesta no se guarda: cambia con cada agente que arranca.

`plan` contesta qué hay por repartir; **`revisar` contesta si repartirlo sirvió**, que es la única pregunta que decide si el enrutador se queda. Cruza la bitácora de despachos con dónde está hoy cada tarea:

```sh
cotejo revisar --dias 3        # lo que lleva 3 días tomado y nadie movió
```

- **`colgada`**: se tomó, nadie la entregó ni la devolvió, y ya lleva días. Es lo que hay que mirar, y no se ve en ningún otro sitio: en CotejoBoard una tarea colgada y una que alguien está haciendo ahora mismo son la misma carta.
- **`devuelta`**: volvió a Pendiente, y viene con el motivo. Ese motivo es el dato que dice si el ruteo se equivocó.
- **`perdida`**: el id dejó de resolver porque alguien editó la nota por encima, o —con `por_que` diciéndolo— la tarea sigue en curso pero el proceso headless que la hacía ya no existe (un OOM, un reinicio). `despachar --motor headless` anota el despacho al lanzarlo, con el `pid` y la máquina, y no solo al terminar; `revisar` mira si ese proceso sigue vivo (solo en la misma máquina). Nadie la está haciendo: bloquéala o devuélvela.
  En Linux con systemd de usuario, ese proceso corre aislado en su propio *scope* (`systemd-run --user --scope`, con `MemoryMax` y `OOMPolicy=continue`, ver `enrutador/aislamiento.py`): si se desboca en memoria, el OOM se lo lleva a él y no al maestro ni a otro headless que esté corriendo a la vez. El `pid` que queda anotado es el del **cliente**, no el de `systemd-run` —`--scope` hace que systemd-run se reemplace a sí mismo por el cliente (`execve`), así que es el mismo pid de principio a fin—, que es justo lo que deja a `procesos.vivo` seguir comparando contra lo de siempre. En otra plataforma, o sin esa sesión de systemd, se lanza como antes.
- **`en_curso_sin_despacho`**: tareas que alguien puso en curso sin pasar por aquí. No es un error —una persona puede tomar una tarea— pero es la diferencia entre «el enrutador reparte el trabajo» y «reparte parte del trabajo».

Y en el resumen, **`rechazos`**: cuántas veces el enrutador se negó a repartir, por veto humano o por falta de modelo. `rechazos.veto` es la cifra que justifica el proyecto entero —cuántas entregas falsas se evitaron— y hasta que los rechazos se anotaron no se podía contar ni a posteriori, porque la negativa no dejaba rastro en ninguna parte.

Lo que el enrutador **no** hace: entregar. Reparte trabajo; quien lo hizo dice qué hizo con `entregar`, y quien lo comprueba es una persona. Si el que reparte pudiera entregar, la evidencia dejaría de significar «esto se hizo».


## CotejoBoard

Es la ventana de seguimiento (GTK4 + libadwaita), y la otra cara de Cotejo: la de la persona que comprueba. Diseño propio: neutros del negro al blanco, Verde Hecho como único acento —el verde es lo que espera que lo compruebes—, y Sora / Inter / IBM Plex Mono.

- Se abre y se cierra desde el botón de la barra de Omarchy (widget `cotejo.barra`, en `barra/`). `Esc`, la X o `Ctrl+W` lo ocultan y `Ctrl+Q` cierra la app del todo.
- El botón muestra solo el símbolo: a propósito no lleva el total de pendientes, porque un número permanente es el FOMO que la app evita. Aparece un número, en Verde Hecho, cuando hay tareas `#por-validar` esperándote. Para ver el total, pasa el mouse por encima.

### Qué lee y cómo escribe

Las reglas que siguen son las de la nota de tareas, la del repo (`.cotejo/tareas.md`) igual que la de un vault de Obsidian:

- Agrupa por proyecto: cada nota o carpeta directa de `01-Proyectos/` (las sub-notas de una carpeta cuentan para su proyecto).
- Toma `estado` y `prioridad` del frontmatter de la nota principal para ordenar; oculta `terminado` y `descartado`, y las notas con otro `tipo` (p. ej. `Léeme.md`).
- Pasar una tarea a *Finalizada* escribe `[x]` en la nota (con Deshacer). Si la línea cambió por fuera, no escribe nada y recarga.
- Clic en una tarea la abre en Obsidian. Se actualiza sola al editar el vault: quien vigila es la app, incluso con la ventana cerrada, y en cada cambio reescribe `~/.local/state/tareas-obsidian/estado.json`, que es lo que lee la barra.
- Las tareas admiten tags al final de la línea que la app lee y no muestra en el texto: `#en-curso` y `#por-validar` (estado), `#agente/opus` (quién la tiene) y `#facil` / `#medio` / `#dificil` (dificultad, del [[Enrutador]]).
- Al escribir en una tarea por primera vez se le deja una marca de bloque al final (`^cotejo-a1b2`), que es la de toda la vida de Obsidian: sirve para enlazar la línea desde otra nota y es el identificador estable con el que la nombran los agentes. Tampoco se muestra.

La banda de proyectos elige proyecto y el board muestra solo ese: 67 tareas de una no se leen. La opción *Todos los proyectos* muestra todo, agrupado por proyecto dentro de cada columna. El proyecto elegido se recuerda en `~/.local/state/tareas-obsidian/board.json`.

La banda es una franja al 60 % del ancho, centrada bajo la cabecera, con un chip por proyecto (*Nombre · pendientes*, el elegido resaltado y *Todos los proyectos* primero). No rota sola: se arrastra con el mouse para buscar y se elige con clic, o con el teclado (`←` / `→` entre chips, `Enter`).

En la banda, cada chip lleva su número de pendientes y, si tiene tareas esperando comprobación, una pastilla verde con cuántas: filtrar por proyecto no debe esconder lo que está esperándote.

Las cuatro columnas:

| Columna | En el Markdown | Quién la mueve |
| --- | --- | --- |
| Pendiente | `- [ ]` sin tag | — |
| Haciéndola | `#en-curso` | el agente |
| Para comprobar | `#por-validar` | el agente, cuando entrega |
| Finalizada | `- [x]` | **solo tú** |

Cada carta muestra el agente asignado, la dificultad y la sub-nota si no es la principal; el nombre del proyecto solo aparece cuando estás viendo todos, porque repetirlo en cada carta de una columna filtrada es ruido. El menú `⋮` mueve la tarea de columna, asigna un modelo registrado (o `persona`) o abre la nota. Todo se escribe en el Markdown con la misma verificación y reemplazo atómico que el `[x]`.

Las cartas de *Para comprobar* traen **la evidencia con la que el agente las entregó**, recortada a tres líneas; el menú `⋮` la abre entera y seleccionable, para copiar de ahí un commit o un comando. Sin eso, revisar una entrega cuesta lo mismo que haberla hecho y la columna no sirve de nada.

Si la entrega trae evidencia de git, esa misma carta suma tres acciones para revisarla sin salir del board: **Comprobar** vuelve a correr, en el worktree de la tarea, las pruebas que anotó la entrega —lo mismo que `cotejo comprobar <id>`— y dice si el resultado sigue igual; no toca el estado de la tarea. **Revisar** abre el diff entre los dos commits que anotó esa entrega (no contra la rama de ahora), partido por archivo y plegable, con color por línea; para un cambio grande, **Abrir en herramienta** lanza `git difftool` con la que tengas configurada en vez de pintarlo dentro del board. **Aprobar** marca `[x]` y, si la tarea tenía worktree, además *ofrece* integrar su rama (`merge --no-ff`, que se aborta entero si choca y nunca borra la rama); decir que no deja la tarea igual de hecha, solo sin fusionar. El único acento verde del board sigue estando en la columna que espera algo de ti.

Una decisión que un agente propuso con `cotejo proponer decision` (ver [«El almacén»](#el-almacén-el-conocimiento-del-repo)) sale **como su propia carta** en *Para comprobar*, aparte de las tareas: se abre con la misma vista de revisión —su texto y, si reemplaza otra, la vieja al lado— y el único botón es **Aceptar**. Es el único sitio donde una decisión pasa de `propuesta` a `aceptada`; revisar o aprobar la tarea que la propuso solo avisa que lo hizo, sin aceptarla ahí.

Una carta parada lleva su nota en ámbar: **DEVUELTA** si la paró quien iba a comprobarla, **BLOQUEADA** si la paró quien la estaba haciendo. Se ven igual porque piden lo mismo —que alguien mire—, pero no dicen lo mismo.

**Devolver una tarea pide un motivo.** Sacarla de *Para comprobar* sin marcarla —por cualquiera de las tres vías— abre un diálogo que no deja seguir hasta que escribas qué falta, y el motivo se queda con la tarea: se ve en su carta, en ámbar, hasta que se vuelva a entregar, y le llega al agente en el JSON de `tareas` y de `tomar`. Es la misma regla que hace obligatoria la evidencia al entregar: un rechazo mudo devuelve al agente al punto de partida, y vuelve a entregar lo mismo. `Escape` cancela y no escribe nada.

Una tarea se mueve de columna de tres maneras, y las tres terminan en la misma escritura del Markdown: **arrastrando la carta** con el mouse hasta otra columna (la columna destino se ilumina y la carta que sueltas se queda marcada como el hueco que dejó), con **`Ctrl+←` / `Ctrl+→`** sobre la carta enfocada, o desde el menú `⋮`. Soltar una carta en su propia columna no hace nada: el orden dentro de una columna es el de la nota, no algo que el board guarde aparte.

El board se recorre entero con el teclado. `Tab` y `Shift+Tab` saltan de columna en columna —no de carta en carta, porque con 60 pendientes tabular una a una no lleva a ningún lado— en el orden visual: buscar, recargar, la banda de proyectos y después las cuatro columnas, saltándose solas las que estén vacías. Dentro de una columna, `↑` y `↓` van de carta en carta y `←` / `→` cambian de columna. `Enter` abre la nota en Obsidian igual que el clic, y la tecla `Menú` (o `Shift+F10`) abre el `⋮` de la carta enfocada, que no tiene parada propia de `Tab` justamente para que tabular signifique cambiar de columna. La carta enfocada se ve con el mismo borde verde que al pasar el mouse, más un contorno. Al mover una tarea el foco la sigue hasta su columna nueva, así que se pueden encadenar movimientos sin volver a buscarla.

Las columnas vacías dicen qué las llena, no se quedan en blanco. Lo único que se anima es la entrada del tablero al cambiar de proyecto, y solo si el sistema tiene las animaciones activadas (`gtk-enable-animations`).

### Temas

El botón ◐ a la izquierda de recargar abre el selector: cada tema con una miniatura del board pintada con sus colores, y el que está en uso marcado. Se elige y se ve al momento; queda apuntado como `"tema"` en la config, así que la próxima vez arranca igual. De fábrica vienen **Oscuro** (el de siempre) y **Claro**.

En la interfaz un tema **solo se elige**: no se edita ni se crea. Un tema es un archivo JSON de tokens de color —`nombre`, `descripcion`, `esquema` (`oscuro` o `claro`, para lo que pinta Adwaita) y `colores`, con exactamente los 22 tokens que pide el CSS—, y lo crea y lo comprueba un agente por la CLI:

| Verbo | Qué hace |
| --- | --- |
| `cotejo temas` | Los que hay, cuál está elegido, si se pueden usar y en qué carpeta van los nuevos |
| `cotejo temas nuevo <id> [--desde claro] [--nombre "…"]` | Copia uno en `~/.config/cotejo/temas/<id>.json` para editarlo, con la explicación de cada token. No pisa ninguno |
| `cotejo temas comprobar <id\|archivo.json>` | Valida las claves y los colores y **mide el contraste** (WCAG) de cada par que tiene que leerse, con la cifra y el mínimo |
| `cotejo temas usar <id>` | Lo elige. Se niega si `comprobar` no pasa; con el board abierto, cambia solo |

Los colores solo se aceptan como `#RGB`, `#RRGGBB`, `#RRGGBBAA`, `rgb()` o `rgba()`: acaban pegados dentro del CSS, y un formato cerrado es lo que impide que un tema cuele una regla donde iba un color. Un tema propio que se llame como uno de fábrica no lo tapa. Si el elegido deja de pasar la comprobación, el board se ve con Oscuro, y `config validar` lo avisa.

En el CSS del board (`tareas/app/estilo.py`) no queda ningún color escrito: todo es `var(--k-…)`, con nombres que dicen el papel (`fondo`, `superficie`, `texto`, `tenue`, `senal`…) y no el color, porque en el tema claro el fondo es claro. `pruebas/test_temas.py` se pone roja si vuelve a aparecer un literal: un `#FFFFFF` suelto se ve bien en el oscuro y deja algo invisible en el claro.

Atajos: `Ctrl+F` buscar, `Ctrl+R`/`F5` recargar, `Esc`/`Ctrl+W` ocultar, `Ctrl+Q` salir.

`cotejo` abre o cierra CotejoBoard (es lo que hace el botón de la barra); `--board` solo lo abre; `--fondo` deja el proceso listo sin abrir nada, y `--estado` imprime el resumen en JSON sin cargar GTK. Los subcomandos para agentes (`tareas`, `tomar`, `entregar`, `asignar`) están en [«Para agentes»](#para-agentes), y tampoco cargan GTK.


## De dónde salen las tareas

Todo lo que Cotejo hace con una tarea pasa por una **fuente** (`tareas/fuente.py`): listarla, tomarla, entregarla, marcarla. La que se usa si no dices otra cosa es el repo (`.cotejo/tareas.md`, ver «La fuente repo»); quien ya usaba Obsidian sigue en Obsidian al actualizar, y Notion y las demás apps se conectan con un adaptador.

```json
{ "fuente": "obsidian", "fuentes": { "obsidian": { "vault": "/ruta/al/vault", "carpeta_proyectos": "01-Proyectos" } } }
```

La capa existe porque el contrato con el agente colgaba de un detalle de Obsidian. Mientras «la tarea está en curso» significara «hay un `#en-curso` en su línea», Cotejo solo servía para un vault con `01-Proyectos/`, y **cada segundo cerebro nuevo era un contrato nuevo y un agente que reprogramar**. Ahora el agente habla con Cotejo, y los tags son cosa de la fuente Obsidian.

Cómo queda repartido:

| Pieza | Qué sabe |
| --- | --- |
| `tareas/modelo.py` | Qué es una tarea y un proyecto, y las cuatro columnas. Ni Markdown ni rutas |
| `tareas/fuente.py` | La interfaz que cumple toda fuente, y cuál se usa según la config |
| `tareas/fuentes/obsidian.py` | Notas, tags, marcas de bloque, escritura verificada y atómica |
| `tareas/fuentes/repo.py` | Para quien no tiene vault: un repo de git es un proyecto, hereda de Obsidian el parser y la escritura |
| `tareas/fuentes/externa.py` | Cómo hablarle a un adaptador de otro programa por subproceso. Nada de ninguna app |
| `tareas/configuracion.py`, `tareas/conexion.py` | El archivo de config, y los verbos `init`, `doctor`, `fuentes` y `config init\|validar` |
| `tareas/cli.py`, `tareas/app/`, `estado.py` | Los verbos, el board y el resumen: hablan con la interfaz |

**Para añadir un segundo cerebro** (Logseq, una carpeta de Markdown pelada, Todoist) hay que escribir cuatro métodos —`escanear`, `marcar`, `poner_estado`, `poner_agente`— y registrarlo en `FUENTES`. `crear` y `leido()` son opcionales. Una fuente que no sepa crear sigue sirviendo para todo lo demás, y la CLI lo dice con su nombre en vez de reventar: hay segundos cerebros donde anotar no es cosa de quien lee. `leido()` devuelve 0 por defecto: una fuente que no vive en archivos no cuenta para el medidor de ahorro, que es más honesto que comparar contra cero y anunciar un ahorro infinito. Lo demás tiene valores por defecto razonables: una fuente que no vive en archivos no tiene nada que vigilar y no pierde más que la recarga automática. El ejemplo más corto de cómo se ve una está en `pruebas/test_fuente.py`, que corre los verbos de la CLI contra una fuente en memoria — sin una sola nota detrás. Esa prueba es la que impide que las suposiciones sobre Obsidian vuelvan a colarse en el resto del código.

Lo que una fuente **tiene** que garantizar: comprobar que la tarea siga como cuando se leyó antes de escribir (si no, levantar `TareaCambiada` en vez de pisar), dar identificadores estables entre una llamada del agente y la siguiente, y devolver la tarea como quedó.

### La fuente repo

Es la entrada por defecto: una instalación nueva no tiene vault. Sin adaptador ni dependencias, un repo de git es un proyecto, y sus tareas viven en `<repo>/.cotejo/tareas.md` con exactamente la misma línea que en una nota de Obsidian (`- [ ] texto #medio #agente/x ^cotejo-id`), así que reutiliza el mismo parser y la misma escritura verificada y atómica.

```sh
cd /ruta/al/repo
cotejo init               # crea el esqueleto .cotejo/ completo y registra el repo en «repos»
cotejo fuentes usar repo  # la activa, si init no lo hizo porque tu fuente de antes funciona
```

`init` activa «repo» si la fuente activa no funciona, y deja en paz la que sí (por eso existe `fuentes usar repo`). Es idempotente: repetirlo sin haber tocado nada no vuelve a escribir los archivos ni a duplicar el repo en la config. Crea:

- `.cotejo/tareas.md`: el archivo de tareas de la fuente «repo»
- `.cotejo/proyecto.md`: la entrada del almacén con los datos del proyecto y su versión (0.1.0 en uno nuevo; `cotejo init --repo <carpeta>` sobre una carpeta sin git o inexistente le hace `git init`)
- Carpetas vacías para cada tipo (decisiones, arquitectura, problemas, aprendizajes, bitácora, referencias, recursos), con `.gitkeep`

Si ya corriste `init` pero sigues en otra fuente, o hay un `.cotejo/tareas.md` sin registrar, `cotejo doctor` lo dice en `avisos` y en `salida` —sin tocar `ok`— sin que tengas que acordarte.

Qué repos cuentan lo dice la config de la fuente `repo`: una lista (`repos`) o una carpeta (`raiz`) cuyos hijos directos tengan `.cotejo/tareas.md`; las dos se pueden combinar.

```json
{ "fuente": "repo", "fuentes": { "repo": { "repos": ["/ruta/a/uno", "/ruta/a/otro"], "raiz": "/ruta/con/varios" } } }
```

Cuando se despacha una tarea de esta fuente, `despachar` le crea por defecto su propio worktree (ver «Para agentes», arriba), así que el agente trabaja y commitea fuera del repo principal sin pisar a otra tarea del mismo repo. Funciona igual en Linux y en Windows.

### Traer un proyecto que ya existe (desde Obsidian o Notion)

Obsidian y Notion ya no son el sitio donde se trabaja a diario: son la puerta de entrada. `cotejo importar obsidian <proyecto>` y `cotejo importar notion <proyecto>` traen un proyecto de otra app a su `.cotejo/` (ensayo por defecto; `--aplicar` escribe), y desde ahí se trabaja con el repo. Lo que hace cada uno, qué reparte y qué deja sin importar está en [«Para agentes»](#para-agentes) (`importar obsidian` / `importar notion`). Después del import, la skill `cotejo` (`referencias/inicio.md`, «Proyecto importado») lleva a la persona por decisiones, arquitectura y tareas.

### Conectar Cotejo a otra app

Las fuentes que no son el repo son tres: **Obsidian** viene incluida (con `carpeta_proyectos` y `migrados`, ver más arriba), **Notion** es el primer adaptador, y cualquier otra app se conecta con uno propio. Una app que no es Obsidian se conecta **sin tocar Cotejo**: con un adaptador, que es un programa aparte al que Cotejo le habla por subproceso y en JSON. Se puede escribir en cualquier lenguaje, sus dependencias no se le cobran a quien no lo usa, y funciona igual en Linux que en Windows. La primera es **Notion** (`extras/notion/`, se instala como `cotejo-notion`):

```sh
export NOTION_TOKEN=secret_...                   # el de una integración interna, en notion.so/my-integrations
cotejo fuentes info notion                         # qué parámetros pide, dicho por el adaptador
cotejo fuentes agregar notion --comando cotejo-notion --param database_id=<los 32 caracteres de la URL de la base>
cotejo fuentes probar notion                       # la conecta y la lee; no escribe ni la activa
cotejo fuentes usar notion                         # la activa, solo si `probar` pasa
cotejo doctor                                      # y desde aquí, todo Cotejo lee de Notion
```

En Notion, **cada página de la base es una tarea**; el proyecto sale de una propiedad «Proyecto» (select, texto o relación a otra base) o, sin ella, es la base entera; el estado, de «Estado» (status o select), casando sin mirar mayúsculas ni tildes y entendiendo también los de fábrica de Notion (*Not started*, *In progress*, *Done*); «Agente», «Dificultad» y el checkbox «Done» si existen, y el id es la propiedad *ID único* si la hay (`TAR-12` → `tar-12`). Si tus propiedades se llaman de otra forma, `propiedades` y `estados` en su config lo dicen. `cotejo doctor` avisa de lo que falta —por ejemplo, un estado sin opción «Por validar»— antes de que un agente se estrelle contra ello. La base hay que **compartirla con la integración** (… → Conexiones), o Notion contesta que no existe.

El token **nunca va en la config**. Se lee de la variable que diga `token_env` (por defecto `NOTION_TOKEN`) o, si no está, de `~/.config/cotejo/notion.token` (un archivo solo con el token, con permisos 600). El archivo es lo que ven el board y la barra, que los arrancan Hyprland y Quickshell y no una shell, así que no heredan las variables de fish ni del `.bashrc`. `fuentes agregar` y `config validar` se niegan a guardar en la config algo que parezca un secreto.

**Cambiar de fuente es un comando**: `cotejo fuentes usar obsidian` (o `notion`). La app vigila la config y reabre la fuente sola, así que el board y la barra cambian sin reiniciar nada. Con Notion el board no se recarga solo cuando editas en Notion —no hay archivos que vigilar—: `Ctrl+R`, y la barra por su cuenta cada pocos minutos. Para los agentes, la skill `cotejo-fuentes` (en `skills/`, se instala junto a la de Cotejo) cubre cambiar de fuente y conectar una app nueva sin cargar el protocolo entero.

| Verbo | Qué hace |
| --- | --- |
| `cotejo init [--repo <carpeta>]` | Dentro de un repo git: crea el esqueleto `.cotejo/` completo (tareas.md, proyecto.md, carpetas de tipos) y registra el repo en `repos` de la fuente `repo`, sin activarla. Idempotente |
| `cotejo doctor` | ¿Funciona?, y si no, qué hacer: la config y la fuente activa, en una llamada |
| `cotejo fuentes` | Las que hay, cuál está activa y qué les falta, sin conectarse a nada |
| `cotejo fuentes info <nombre>` | Qué parámetros pide y cómo se registra (a un `cotejo-<nombre>` instalado se le pregunta antes de registrarlo) |
| `cotejo fuentes probar <nombre>` | La conecta y la lee. No escribe nada, ni en ella ni en la config |
| `cotejo fuentes usar <nombre>` | La activa. Se niega si `probar` no pasa: una fuente rota deja al board sin tareas |
| `cotejo fuentes agregar <nombre> --comando <cmd> --param k=v` | Registra un adaptador. No lo activa |
| `cotejo fuentes quitar <nombre>` | Lo desregistra. No borra nada en la app de fuera, y no quita la activa |
| `cotejo config init` / `validar` | Crea el archivo (o migra el viejo), o dice qué tiene mal sin tocarlo |

**Para escribir un adaptador** para otra app, se copia `extras/plantilla/cotejo_plantilla.py` —el contrato entero en 200 líneas, con un archivo JSON haciendo de app— y se cambian sus lecturas y escrituras por llamadas a la API. El contrato, con todo en JSON y `"esquema": 1`, y los parámetros de la fuente en la variable `COTEJO_FUENTE_CONFIG`:

| Subcomando | Contesta |
| --- | --- |
| `doctor` | `{"ok": true, "mensaje": "..."}` — también con `ok: false` y `salida` cuando algo falla |
| `protocolo` | Qué sabe hacer y qué parámetros pide: `{"nombre", "verbos", "parametros", "ejemplo"}` |
| `escanear [--hechas]` | `{"proyectos": [{"nombre", "tareas": [{"id", "texto", "estado", "agente", "dificultad", "hecha", "url"}]}], "avisos", "leido"}` |
| `estado <ref> <nuevo> --esperado JSON` | `{"cambio": bool, "tarea": {...}}` |
| `agente <ref> <quien> --esperado JSON` | Igual; `quien` vacío la deja sin dueño |
| `marcar <ref> --hecha\|--pendiente --esperado JSON` | Igual. Solo lo usa el board: finalizar es de una persona |
| `crear --proyecto N --texto T [--dificultad D]` | La tarea nueva. Opcional: contestar `no-implementado` es válido |

Los errores salen con código distinto de 0 y `{"error", "tipo", "salida", "reintentable"}`; `tipo: "cambiada"` es la que importa: la tarea ya no está como dice `--esperado`, así que **no se escribe**. Es la misma garantía que da Obsidian, y la razón de que exista `--esperado`.

Al adaptador se le piden **primitivas** —poner un estado, poner un agente— y no los verbos de trabajo. Que entregar exija evidencia y bloquear exija motivo, y que ese texto vaya a la bitácora y no a la app de fuera, sigue siendo de Cotejo: si cada adaptador implementara su propio `entregar`, cada uno lo haría un poco distinto.

**Obsidian como visor.** La carpeta `.cotejo/` de un repo son notas Markdown con frontmatter, así que se puede abrir como vault de Obsidian para recorrerla, enlazarla y ver su grafo. Es un visor opcional: Cotejo no lo necesita, y sigue leyendo y escribiendo los mismos archivos.

## Instalar

Linux. La CLI necesita solo `python3`; CotejoBoard, además, `python-gobject`, `python-cairo`, `gtk4` y `libadwaita`.

Sin clonar nada, desde la última release (comprueba su SHA-256 antes de instalar; repetirlo actualiza; sin las dependencias del board instala solo la CLI y dice qué falta):

```sh
curl -fsSL https://cotejo.dev/install.sh | sh
```

Ese script es `web/public/install.sh` y lo sube a GitHub Pages `web/publicar.sh`. Desde el repo:

```sh
./install.sh     # copia a ~/.local/share/tareas-obsidian, crea los comandos en ~/.local/bin y la
                 # entrada del menú, escribe el protocolo en tus agentes y, si hay Omarchy,
                 # instala el widget en ~/.config/omarchy/plugins y lo agrega a la barra
./uninstall.sh   # quita todo eso (también el widget de shell.json); la config se queda
```

| Opción de `install.sh` | Para qué |
| --- | --- |
| `--sin-board` | Solo la CLI (un servidor, una máquina sin escritorio): no pide PyGObject ni instala menú, fuentes ni widget |
| `--sin-widget` / `--widget` | No tocar la barra de Omarchy / instalar el widget aunque la barra aún no esté configurada |
| `--sin-agentes` | No escribir el protocolo en Claude Code, Codex, Gemini CLI ni opencode |
| `--prefijo /usr/local` | Para todo el sistema (con `sudo`). No toca ningún `$HOME`; desinstala `./uninstall.sh --prefijo /usr/local` |
| `--prefijo /usr --destdir DIR` | Para empaquetar: escribe bajo `DIR` como si fuera la raíz |

Comandos que deja: `cotejo` (y sus nombres de antes, `tareas-obsidian` y `foco`), `cotejoboard` (la ventana) y `cotejo-notion`. Son Python y ponen la instalación delante en `sys.path`, así que se llaman desde cualquier carpeta sin que un `tareas/` local los suplante.

En una instalación del sistema (el paquete de pacman) lo que vive en el `$HOME` —el widget de Omarchy, el protocolo de los agentes— lo pone `usuario.sh`, y no hace falta correrlo a mano: el board lo corre solo, en segundo plano, la primera vez que esa persona abre Cotejo y después de cada actualización (`usuario.sh` deja anotado en `<estado>/usuario.json` qué versión puso y con qué opciones, que se repiten). `cotejo doctor` dice si falta o si el widget no está en la barra. A mano: `sh /usr/share/tareas-obsidian/linux/usuario.sh` (y `--quitar` para deshacerlo, que no vuelve a ponerse solo). Es el mismo script que corre `install.sh` en la de usuario.

Para publicar, `sh empaquetado/linux/construir.sh [--arch]` arma `dist/cotejo-<versión>-linux.tar.gz` desde `HEAD` (no desde el árbol de trabajo), que se instala con su `./install.sh`; con `--arch` construye además el paquete de pacman para Arch y Omarchy (`dist/arch/`, con `empaquetado/linux/PKGBUILD`). No instala nada: eso es `sudo pacman -U dist/arch/cotejo-*.pkg.tar.zst`.

Un release no se arma a mano: `git tag v<versión> && git push origin v<versión>` corre `.github/workflows/release.yml`, que comprueba que la etiqueta coincide con `tareas.__version__`, corre `linux.yml` (pruebas, los dos paquetes de Linux armados en un contenedor de Arch, el `.pkg` instalado en un Arch limpio y el tar.gz en un Ubuntu limpio, con board y solo la CLI) y `windows.yml` (el instalador, instalado en un Windows limpio), y solo si todo pasa junta los cuatro archivos con su `SHA256SUMS`. Con el secreto `RELEASES_TOKEN` los sube al release de Rafael088/cotejo **como borrador**; publicarlo es a mano. Los paquetes pasan de un job a otro por la caché de Actions, no como artefactos, para no gastar la cuota de almacenamiento de la cuenta. Para rehacer el release de una etiqueta con los workflows de `master`: `gh workflow run release.yml --ref master -f etiqueta=v<versión>` (construye el código de la etiqueta). La prueba de instalación limpia de Linux es `empaquetado/linux/probar_instalado.py`: instala en el sistema, así que es para un contenedor, no para tu máquina.

Para desarrollar, `python3 herramientas/cotejo_dev.py` (o `cotejo-dev`, si lo enlazas en tu `PATH`) corre el código del repo con su propia config, estado y vault de prueba, en `~/.local/state/cotejo-dev`, y abre el board con otro APP_ID: no toca el Cotejo que tengas instalado. Tras cambiar el código de una instalación hecha con `./install.sh`, vuelve a correrlo y reinicia el proceso de fondo. Para probar el instalador sin tocar el tuyo: `HOME=$(mktemp -d) ./install.sh` (quita antes `XDG_DATA_HOME` y `XDG_CONFIG_HOME` si los tienes puestos).

El widget se registra una sola vez en `~/.config/omarchy/shell.json` (con copia en `shell.json.bak`); de ahí en adelante respeta dónde lo hayas puesto. El shell recarga los plugins al guardarlos, sin reiniciar. Al copiarlo, el instalador le escribe la ruta de su lanzador y la de `estado.json` según `tareas/rutas.py`, así que la barra lee de donde la app escribe aunque la instalación esté en `/usr` o tengas un `XDG_STATE_HOME` propio.

En Hyprland (fuera de este repo, en `~/.config/hypr/autostart.lua`) va el arranque con `--fondo` y la regla de la ventana: `CotejoBoard` va tileado, como una app normal, para que entre al layout y no tape otras ventanas. Tras cambiar una regla hay que reiniciar el proceso: Hyprland las aplica al crear la ventana, y la app las reutiliza ocultándolas.

## Pruebas

```sh
python3 -m unittest discover pruebas
```

Sin dependencias: `unittest` de la biblioteca estándar, como todo lo demás. Son 348 y tardan medio segundo.

Cubren la fuente Obsidian —el único código del proyecto que modifica las notas del vault—, la CLI de agentes, la bitácora, las dos funciones del board (`tareas/app/comun.py`) que deciden qué anotación enseña cada carta, la capa `Fuente` con una fuente de mentira que no toca ningún archivo, los temas (que el CSS no tenga colores propios, que un tema roto o ilegible no se pueda elegir), y el enrutador entero: el orden de decisión, las reglas medidas contra el set de evaluación, los motores y los verbos que reparten. Cada prueba arma su propio vault de mentira en un directorio temporal y lo borra al terminar; `estado.json` y `bitacora.jsonl` se redirigen ahí también, así que correrlas no toca ni el vault real ni lo que lee el widget de la barra.

Lo que más se comprueba no es que escriba bien, sino que **no escriba cuando no debe**: si la línea cambió por fuera, si el id no existe, si un id responde a dos tareas, si falla el reemplazo a mitad. En todos esos casos la nota tiene que quedar byte a byte como estaba.

Ninguna prueba puede llamar a un modelo: `COTEJO_MOTOR=agente` va puesto en el andamiaje de todas las del enrutador. Está ahí desde que una de ellas lanzó Claude de verdad —88 segundos y tokens gastados—, porque una prueba que cuesta dinero se acaba desactivando.

Hay tres que existen solo para vigilar una decisión, y las tres vigilan una ausencia: `test_no_hay_ningun_verbo_para_finalizar_una_tarea` se pone roja si alguien le añade a la CLI la capacidad de marcar `[x]`; `test_ningun_verbo_del_enrutador_entrega_ni_finaliza_tareas`, si el que reparte aprende a entregar; y `test_despachar_no_tiene_ninguna_bandera_para_forzar_una_tarea_humana`, si aparece una bandera que salte el veto. No son descuidos que falten; son el diseño, y conviene que romperlo cueste un renglón rojo.

## La bitácora

`~/.local/state/tareas-obsidian/bitacora.jsonl` es el registro de lo que pasó con cada tarea: una línea de JSON por operación, solo se agrega, nunca se reescribe. Se lee con `tail`.

La frontera con el Markdown es deliberada: **en la línea de la tarea vive su estado; en la bitácora, lo que pasó para que llegara ahí.** El estado se queda en la nota porque es lo que hace que el vault sea la única fuente y que todo se vea igual desde Obsidian. El texto libre no cabe ahí: una evidencia son comandos, salidas de pruebas y hashes de commit, y eso dentro de un `- [ ]` deja la nota ilegible en Obsidian y en el board, que es justo lo que Cotejo existe para evitar. Y tampoco es estado: no dice dónde está la tarea, dice qué ocurrió en una transición.

Por eso borrar este archivo no pierde ninguna tarea ni ninguna columna —solo la memoria de por qué—, y por eso un fallo al escribirlo no tumba la operación que ya se escribió en la nota.

De cada tarea, CotejoBoard y la CLI leen **la última anotación que trae texto libre** (`evidencia` o `motivo`): tomar o mover una tarea queda registrado, pero no tapa el motivo por el que se la devolvieron. Se lee solo la cola del archivo, porque solo crece y esto se consulta en cada repintado.

Al lado vive `despachos.jsonl`, que es lo mismo para el reparto: a qué modelo fue cada tarea, por qué regla, con qué motor y cómo salió — **y también las que no se repartieron**, con la clave `rechazo` diciendo por qué. Están aparte porque cuentan cosas distintas —una, qué pasó con la tarea; la otra, qué pasó con la decisión— y porque el board no tiene por qué saber qué es un modelo. Se lee con `cotejo despachos`.

## Configuración

Todo va en **un solo archivo**, `~/.config/cotejo/config.json`: qué fuente se usa, los parámetros de cada una y los ajustes del enrutador. `cotejo config init` lo crea (o lo migra, ver abajo), `cotejo config validar` dice qué tiene mal sin tocarlo, y `COTEJO_CONFIG=/ruta` apunta a otro en una sola invocación. Por defecto se lee el vault abierto en Obsidian (`~/.config/obsidian/obsidian.json`); para fijar otro:

```json
{ "fuente": "obsidian", "fuentes": { "obsidian": { "vault": "/ruta/al/vault", "carpeta_proyectos": "01-Proyectos" } } }
```

Las rutas de este README son las de Linux. En otros sistemas las pone `tareas/rutas.py`, y ninguna lleva un nombre de usuario escrito a mano:

| | config (`cotejo/config.json`, temas, token de Notion) | estado (`estado.json`, bitácoras, `ahorro.json`, `board.json`) |
|---|---|---|
| Linux | `$XDG_CONFIG_HOME` o `~/.config` | `$XDG_STATE_HOME` o `~/.local/state`, en `tareas-obsidian/` |
| macOS | `~/Library/Application Support` | `~/Library/Application Support/cotejo/estado` |
| Windows | `%APPDATA%` | `%LOCALAPPDATA%\cotejo\estado` |

`COTEJO_ESTADO=/ruta` apunta la carpeta de estado a otra en una sola invocación, como `COTEJO_CONFIG` con la config. En Linux la carpeta de estado sigue llamándose `tareas-obsidian` porque de ahí lee el widget de la barra.

**El archivo de antes** (`~/.config/tareas-obsidian/config.json`, con `vault` y compañía sueltos en la raíz) se sigue leyendo mientras no exista el nuevo, y sus claves sueltas cuentan como parámetros de `obsidian`. `cotejo config init` lo pasa al formato nuevo y lo renombra a `config.json.migrado` en vez de borrarlo: lo que no puede pasar es que queden dos archivos vivos y cada skill escriba en uno.

### El dot

`"dot": true` en la raíz de la config enciende el dot del board; sin la clave, o con `false`, está apagado y el board no crea nada de él. El board vigila la config: cambiarla lo crea o lo destruye sin reiniciar ni reinstalar.

### Inbox y diario

Las tareas sueltas de carpetas que no son proyectos —`00-Inbox`, `06-Diario`— se leen si se piden, en los parámetros de `obsidian`:

```json
{ "fuentes": { "obsidian": { "carpetas_sueltas": ["00-Inbox", "06-Diario"] } } }
```

Cada carpeta sale como **un proyecto más**, llamado como ella sin el número de delante («Inbox», «Diario»), y cada nota como una sub-nota: en el board la tarea lleva al lado el nombre de su nota, que en el diario es la fecha. Uno por carpeta y no uno por nota, porque el diario gana una nota al día. Van detrás de los proyectos de verdad (no tienen estado ni prioridad), una carpeta sin tareas no sale, y para el board, la CLI y `estado.json` son proyectos como cualquier otro: se toman, se entregan y se marcan igual.

**Viene apagado** (`[]`), porque encenderlo cambia lo que ve todo el mundo: el diario acumula un «⏭️ Mañana» por día, y cada `- [ ]` que no se cerró en su día pasa a ser una tarea pendiente para siempre. Conviene encenderlo cuando se quiera eso, no descubrirlo.

Los ajustes del enrutador van en ese mismo archivo, bajo la clave `enrutador` — un solo archivo para un solo comando:

```json
{
  "enrutador": {
    "motor": "agente",
    "proyectos": { "Cotejo": "~/Documentos/ClaudeCode/cotejo" },
    "modelos": [],
    "reglas_extra": [],
    "reglas_apagadas": []
  }
}
```

- `proyectos`: en qué carpeta trabaja el agente para cada proyecto. Sin entrada, corre donde estés.
- `modelos`: catálogo de modelos añadidos por clientes de IA. Cada entrada tiene `clave`, `modelo_id`, `cliente` y `nivel`; se gestiona con `cotejo modelos agregar` y `modelos quitar`.
- `reglas_extra` y `reglas_apagadas`: las reglas propias ganan a las de fábrica, y cualquiera de fábrica se apaga por su nombre (`cotejo config` las lista).
- `maestro`: `terminal` es con qué se abre. Sin entrada, sale de la plataforma: `["xdg-terminal-exec"]` en Linux, `["cmd", "/c", "start", ""]` en Windows; con otra, por ejemplo `["alacritty", "-e"]`. `modelos` es el modelo con que se abre cada cliente (`{"claude": "opus"}`; sin entrada, el que ese cliente tenga por defecto).
- `motores.headless.clientes.<cliente>`: `comando` y `argumentos_extra` para lanzar un cliente que no es Claude.
- `motores.headless.aislar` (`true` por defecto) y `motores.headless.memoria_max` (`"50%"` por defecto): el scope de systemd en que corre cada headless y su tope de memoria. `memoria_max` admite el porcentaje que entiende systemd —de la RAM física del equipo, para no tener que adivinar cuánta tiene quien instale Cotejo— o un valor absoluto (`"2G"`, `"512M"`). `aislar: false` lo apaga sin tocar nada más.
- `COTEJO_MOTOR` fija el motor en una sola invocación, y es lo que impide que las pruebas llamen a un modelo por descuido.

El widget se ajusta desde `~/.config/omarchy/shell.json`, en su entrada de la barra:

```json
{ "id": "cotejo.barra", "mostrarPendientes": false, "intervaloSeg": 300, "colorAviso": "#16C98D" }
```

- `mostrarPendientes`: ponlo en `true` si prefieres ver siempre el total.
- `intervaloSeg`: cada cuánto recalcula por su cuenta. Es solo la red de seguridad para cuando la app no está corriendo; con la app viva el conteo se actualiza al instante.

## El archivo de estado

`~/.local/state/tareas-obsidian/estado.json` es lo que la app reescribe en cada cambio del vault y lo que lee el widget de la barra. Lleva `"esquema": 1`, y es un contrato con gente que no se puede ver —el widget, un script, un agente—: **las claves se agregan, nunca se renombran ni se quitan**. Romperlo no da error en ninguna parte, simplemente deja de funcionar en silencio; por eso el número, para que quien lo lea pueda darse cuenta.

Si Cotejo no pudo leer alguna nota, el resumen trae `avisos` con la nota y el motivo, el board lo dice en una banda ámbar bajo el encabezado, y el widget lo suma a su tooltip. Una nota ilegible no tiene tareas, y en el board eso se ve exactamente igual que una nota que nunca las tuvo: el aviso es la diferencia entre «no hay nada» y «no pude mirar».

Contacto: soporte@cotejo.dev

## Si te sirve

Puedes invitar al autor a un café: **[☕ Donar con Mercado Pago](https://link.mercadopago.com.co/cotejo)**

## Licencia

Cotejo es software propietario de uso gratuito y con el código a la vista: su licencia está en
[`LICENSE`](LICENSE) y dentro de cada paquete. Los componentes de terceros que incluye (Python,
GTK, libadwaita, etc.) conservan sus propias licencias: ver
[`THIRD-PARTY-NOTICES`](THIRD-PARTY-NOTICES). Para dudas o problemas, abre un
[issue](../../issues).
