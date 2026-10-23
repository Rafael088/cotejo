# Cotejo — para quien trabaje aquí

Lee el `README.md` para saber qué es y cómo funciona. Esto es lo que además conviene saber
antes de tocar nada.

## Antes de empezar

```sh
python3 -m unittest discover pruebas   # 918, deben estar todas en verde
tareas-obsidian evaluar | head -3      # 85,7 % y 0 abaratados
git log --oneline | head -3
git status --short                     # si no está limpio, averigua por qué antes de seguir
```

**El Cotejo instalado es la versión publicada, no este repo.** Desde el 2026-10-10 el dueño
usa Cotejo como un usuario más (el paquete del release) y aquí no se corre `./install.sh`: un
`master` a medias no puede dejarle sin sus tareas. El código del repo se prueba con
`cotejo-dev` (`herramientas/cotejo_dev.py`), que corre el código del checkout donde estés —el
repo o un worktree— con su propia config, estado y worktrees en `~/.local/state/cotejo-dev`,
sobre un vault de prueba (Faro y Horizonte) que crea la primera vez, y abre el board con otro
APP_ID, al lado del publicado. `COTEJO_VAULT=/ruta cotejo-dev …` apunta a otro vault en una sola
invocación. Lo que arreglas aquí llega al Cotejo de todos los días cuando sale en un release
(skill `cotejo-release`). El comando instalado se llama `cotejo`, y `foco` y `tareas-obsidian`
son el mismo programa con sus nombres de antes.

**El producto se llamó Foco hasta el 2026-09-26.** Lo que quedó de entonces sigue valiendo, a
propósito: los ids `foco-…` (las marcas del vault se migraron a `cotejo-…`, pero una evidencia,
un despacho o la bitácora los siguen nombrando así: `modelo.id_actual()` los traduce en
`buscar`, en `bitacora.ultimas()` y en `revisar`), las variables `FOCO_*` (`tareas/__init__.py`
las copia a `COTEJO_*` si faltan), la carpeta `~/.config/foco` si es la única
(`configuracion.carpeta()`), los comandos `foco` y `foco-notion`, y las skills y marcas `foco`
que `skill.py` limpia al instalar.

## Cómo está repartido

`modelo.py` dice qué es una tarea; `fuente.py` es la interfaz con el segundo cerebro y decide
cuál se usa; `fuentes/obsidian.py` es la única que sabe de notas, tags y marcas de bloque;
`cli.py` (verbos para agentes), `app/` (el board) y `estado.py` (el resumen de la
barra) hablan con la interfaz y con el modelo, nunca con Obsidian. Si escribes `#en-curso` o
`.md` fuera de `fuentes/`, es que algo se salió de su sitio.

`fuentes/repo.py` es la fuente para quien no tiene vault: un repo de git es un proyecto y sus
tareas van en `<repo>/.cotejo/tareas.md`, con la misma línea que en Obsidian. Hereda de
`Obsidian` el parser y la escritura verificada, y solo cambia dónde cae cada archivo
(`_archivo`); los repos salen de `repos` (lista) y/o `raiz` (carpeta) en su config.

`fuentes/compuesta.py` es la migración gradual de la 1.2 (A3, decisión E1): Obsidian con
`migrados` (`{"Cotejo": "/ruta/al/repo"}`) en su config. `fuente.abrir` la devuelve en vez de
`Obsidian` solo si hay marca; cada proyecto marcado se lee de su repo con el nombre del vault y
**deja de leerse del vault** (gana el repo, la nota no se toca) y cada escritura va a la fuente
dueña según `donde`. Solo Obsidian + repo: nada de N fuentes ni externas. Quitar la marca la
deshace sin escribir nada.

`fuentes/externa.py` es la fuente que vive en otro programa: le habla por subproceso y en JSON
a un **adaptador** (`extras/notion/cotejo_notion.py`, `extras/plantilla/cotejo_plantilla.py`), y no
sabe nada de ninguna app. `configuracion.py` es el único que sabe dónde está el archivo de
config y cómo era el formato viejo; `conexion.py` tiene los verbos de la instalación (`init`,
`doctor`, `fuentes`, `config init|validar`).

`cotejo init` es el arranque para quien no tiene vault (y deja un commit inicial con `.cotejo/` si el repo no tenía ninguno, porque `despachar` rechaza antes de tomar un repo sin commits): dentro de un repo git (o con `--repo`),
crea `<repo>/.cotejo/tareas.md` si no existe y añade el repo a `repos` en la config de la
fuente `repo` —sin activarla, eso es de `fuentes usar repo`—. Es idempotente: ni duplica el
repo en `repos` si ya estaba (a mano o porque ya lo cubre `raiz`), ni rehace el archivo si ya
existe. Como lo normal después de `init` es seguir con otra fuente activa, `doctor` mira el
repo donde se para (`_pista_repo_actual`) y, sin tocar `ok`, avisa en «avisos» y en «salida»
si ya está registrado pero toca `fuentes usar repo`, o si tiene `.cotejo/tareas.md` sin
registrar y toca `cotejo init`.

`tareas/worktrees.py` es el aislamiento de la 1.1 (B3): si la tarea es de un repo de git
(`enrutador.proyectos` o, en la fuente repo, `Fuente.carpeta_de`), `despachar` le crea un
worktree con rama `cotejo/<id>` **fuera del repo y del vault** (por defecto en
`rutas.estado()/wt`; `enrutador.worktrees.carpeta` o `COTEJO_WORKTREES` lo mueven, y una carpeta
dentro de cualquiera de los dos se rechaza antes de tomar la tarea). Se registra en
`rutas.estado()/worktrees/<id>.json`, de donde lo leen `entregar`, `comprobar`, `revisar` y el
board, que lo retira al aprobar o devolver a Pendiente. Retirar nunca borra la rama ni lo que
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

`tareas/resumen_inicio.py` es lo que enseña la pestaña **Inicio** del board (v1.3.0), sin GTK:
saludo, titular («Tienes 3 proyectos y 2 entregas por comprobar») y una tarjeta por proyecto con
su versión en curso y el avance en **piezas hechas** de la arquitectura (por
`conocimiento.piezas_del_repo`); sin piezas dice «sin arquitectura todavía», nunca inventa un
avance con las tareas. La pinta `tareas/app/pestana_inicio.py`, que abre antes que el tablero
(salvo sin fuente configurada o rota: ahí va al tablero, con el vacío del primer arranque) y
pone encima la **constelación** (7wc9hb): cada proyecto un núcleo con sus piezas alrededor,
por estado y con el verde solo para lo que espera comprobación. Su geometría y su dibujo con
cairo son puros (`tareas/constelacion.py`, como `dot_dibujo.py`) y el widget
(`tareas/app/constelacion.py`) solo pide fotogramas mapeado y con `gtk-enable-animations`
encendido. `nuevo_proyecto()` abre la entrevista (kf94so) y `abrir_proyecto(nombre, carpeta=None)`
el mapa del proyecto, que es lo que hacen tocar una tarjeta y tocar un núcleo. El dot entra al
verse el tablero, no antes.

`tareas/mapa.py` es el **mapa del proyecto** (v1.3.0, cotejo-p86sa9), sin GTK: las piezas de
`conocimiento.piezas_del_repo` repartidas en las cuatro capas (qué ve la gente, qué hace, qué
guarda, con qué se conecta) y la ficha de cada una (frase en llano, sus tareas con su columna y
«Si programas: …» la tecnología), con los estados y nombres de la constelación. Lo pinta
`tareas/app/mapa.py`, una página más de la pila (`"mapa"`): llegan ahí la tarjeta y el núcleo del
Inicio y, desde «Revisar el plan», «Ver el mapa del proyecto» y «Empezar la 0.1.0», que pasan la
carpeta porque un proyecto recién preparado vive en la fuente repo y no en la activa (sus tareas
se leen entonces con `revisar_plan.fuente_del_proyecto`). Del mapa, «Ver el tablero»
(`abrir_tablero`) lleva al tablero con ese proyecto elegido, y «Inicio» vuelve.

`tareas/importar_obsidian.py` es el importador de la 1.2 (D1): `planear()` devuelve un `Plan` —las
entradas que se crearían con su `origen` estable (`nota#sección:hash`)— sin escribir nada, y
`importar obsidian` lo enseña (`enrutador/verbos.py`). Es mecánico sobre la plantilla del
vault; lo que no encaja va a `referencias/` con el tema `sin-clasificar`, nunca se adivina ni se
pierde. Solo importa los adjuntos que las notas **enlazan**: lo suelto en la carpeta del proyecto
suele ser código y se cuenta en `no_enlazados`. `aplicar()` (D2, `--aplicar`) escribe ese mismo
plan: comprueba antes de la primera escritura todo lo que puede negarse (unas `tareas.md` con
otras tareas), decide los nombres de archivo antes de escribir para reescribir los enlaces
(`Almacen.crear(nombre=…)`), salta lo que ya tiene su `origen`, escribe la tarea de revisión
por `fuentes/repo.py` y marca `migrados`. Nunca commitea ni toca el vault.

`tareas/revision.py` es la vista de revisión de la 1.1 (B4), sin GTK: qué enseña la carta de
*Para comprobar* a partir de la evidencia (`resumen`), el diff partido por archivo
(`partir_diff`, `diff`, entre los dos commits que anotó la entrega y no contra la rama de
ahora), volver a comprobar (`recomprobar`, la misma función que `cotejo comprobar`), `git
difftool` con la herramienta de la persona y lo que hace **Aprobar**: `plan_integracion` se
calcula antes de marcar —marcar retira el worktree, y con él el registro de qué repo es— y el
board solo **ofrece** integrar; `integrar` (un `merge --no-ff`, que se aborta entero si choca y
nunca borra la rama) corre únicamente si la persona dice que sí. La CLI no gana verbos con
esto. El diff se pinta solo con GTK4 + Adwaita (sin GtkSourceView): una etiqueta por línea,
con los colores de siempre (verde lo que entra, ámbar lo que sale) y recortado a
`LINEAS_MAX` por archivo; lo grande, en la herramienta.

`tareas/preparacion.py` y `enrutador/preparar.py` son el inicio en segundo plano de la 1.3.0:
con las respuestas de la entrevista, `preparar.lanzar` arma el prompt (`tareas/inicio.py`) y
lanza el cliente elegido sin interfaz (`motores/fondo.py`, con la tabla de `clientes.py` y los
ajustes de `motores.headless`), anotado con pid como un despacho en
`rutas.estado()/preparaciones/<id>.json`; un hilo del proceso que lo lanzó (en el board, el de
`--fondo`) anota el código al volver y reescribe `estado.json`, que lleva `preparaciones` para
la barra. Estados: `preparando`, `colgado` (vivo pero nada se movió en `.cotejo/` ni en su
salida durante `enrutador.preparar.minutos_sin_actividad`, 10 por defecto), `fallo` (código
≠ 0, o 0 sin tareas, o muerto sin volver y sin tareas) y `listo`; los dos primeros malos traen
`reintentar` y `abrir_en_terminal`. El agente corre con `inicio.ENTORNO`
(`COTEJO_FUENTE=repo`): `init` registra la carpeta sin activar la fuente repo, y así `crear` y
`asignar` la encuentran aunque la persona use Obsidian, sin tocarle la config.

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

## Lo que no se cambia sin decisión consciente

- **La CLI no tiene verbo para finalizar una tarea, y es a propósito.** Si el agente puede
  marcar hecha la suya, «hecha» deja de significar «alguien la revisó». Marcar `[x]` es de una
  persona, en CotejoBoard. Hay una prueba cuyo único trabajo es ponerse roja si alguien lo añade:
  `test_no_hay_ningun_verbo_para_finalizar_una_tarea`. Sí tiene `crear`, y la diferencia no es
  arbitraria: apuntar trabajo no afirma que esté hecho. Crear un **proyecto** tampoco está, y
  por otra razón: es una nota nueva en el segundo cerebro, no una tarea. Ni se crea en una
  carpeta suelta (Inbox, Diario): no tiene nota principal y habría que inventarse dónde cae.
  El inicio del board (dec-hgq7, aceptada el 2026-10-22) tampoco añade un verbo: crea el
  proyecto llamando a `init`, con un formulario sin IA y el agente lanzado por detrás.
- **Todo lo que escriba en el vault pasa por `fuentes/obsidian.py`.** Verifica que la línea siga
  igual que cuando se leyó y reemplaza el archivo de forma atómica. Editar el Markdown con `sed`
  o con la herramienta de edición se salta esa protección, y la forma de fallar es pisar trabajo
  ajeno en silencio.
- **Ninguna suposición sobre Obsidian fuera de su fuente.** `pruebas/test_fuente.py` corre los
  verbos contra una fuente en memoria: si alguien vuelve a colar una nota o un tag en `cli.py`,
  `estado.py` o el modelo, esa prueba se pone roja.
- **`estado.json` es un contrato** con el widget QML de la barra y con quien lo lea desde fuera.
  Lleva `"esquema"`: las claves se agregan, nunca se renombran ni se quitan.
- **El texto libre vive en la bitácora, no en la línea de la tarea.** En la línea cabe el
  estado —y ahí se queda, porque es lo que hace que el vault sea la única fuente—; la evidencia
  de una entrega y el motivo de un rechazo van a `bitacora.jsonl`, que solo se agrega. Meter ese
  texto en el `- [ ]` deja la nota ilegible en Obsidian, que es justo lo que Cotejo evita.
- **Entregar exige evidencia; devolver y bloquear exigen motivo.** Las tres son obligatorias
  por la misma razón: si revisar cuesta lo mismo que hacer, la columna «Para comprobar»
  no sirve; y una tarea que vuelve a Pendiente sin explicación la toma el
  siguiente para estrellarse contra lo mismo. El board no deja confirmar una devolución con el
  motivo vacío, y `bloquear` sin `--motivo` no llega ni a ejecutarse.
- **El medidor de ahorro mide, no estima.** Las dos mitades salen de datos que ya existen —lo
  que la CLI devolvió y lo que pesaban las notas que la fuente leyó para contestar—, y el
  supuesto que las une viaja en la clave `supuesto`, a la vista. Si alguien lo hace contar
  llamadas que no son de un agente (`estado`), o abrir una nota para medir, deja de medir el
  ahorro y empieza a comérselo: `pruebas/test_ahorro.py` vigila las dos cosas. En el board va
  en plata, nunca en verde: el verde es para lo que espera comprobación. Enseña lo de **hoy**
  (la fecha local), no el total ni la sesión: Cotejo no sabe desde qué sesión lo llaman.
- **El núcleo no importa GTK: solo el paquete `tareas/app/` lo hace, y solo `tareas/board.py`
  importa `tareas.app`.** La única otra pieza de interfaz es el widget del dot
  (`tareas/dot_widget.py`), que solo importa `tareas/app/capa_dot.py`; su geometría y su
  dibujo (`dot.py`, `dot_dibujo.py`) no nombran `gi`. **El dot** vive así: `dot.py` (pose y
  pistas), `dot_dibujo.py` (cairo), `dot_widget.py` (`Dot`), `presencia.py` (qué estado y qué
  ancla tocan en el board, sin GTK) y en `tareas/app/capa_dot.py` solo el overlay
  (`montar_dot`); la referencia es `docs/dot/` y manda el planning del dot.
  De ahí salen los 32 ms de `--estado`, y es lo que deja empaquetar la CLI sola. Dos puntos de
  entrada: `cotejo` → `tareas.cli:main` (núcleo) y `cotejoboard` → `tareas.board:main` (interfaz);
  `python -m tareas` sirve para los dos y solo va a la ventana sin argumentos o con `--board`,
  `--fondo` (`board.es_del_board`) —todo lo demás es de la CLI, así que un verbo nuevo no hay
  que apuntarlo en ninguna lista—. `pruebas/test_nucleo_sin_gtk.py` corre cada verbo en un
  Python que no puede importar `gi` y se pone roja si alguno lo intenta, aunque sea dentro de
  un `try`; un verbo o una acción nuevos sin fila en su `INVOCACIONES` también la ponen roja.
- **Ninguna ruta de config o de estado se escribe a mano.** Salen de `tareas/rutas.py`, que
  sabe dónde van en Linux, macOS y Windows; en Linux no cambió ninguna (el widget lee de ahí).
  `pruebas/test_rutas.py` se pone roja con un `".config"` o `".local"` literal fuera de su sitio.
- **El CSS del board no lleva colores.** Todo color es un `var(--k-…)` que pone el tema
  (`tareas/temas.py`, `data/temas/`). Un color nuevo es un token nuevo en `TOKENS` y en
  **todos** los temas de fábrica, y si es texto, un par en `CONTRASTES`.
  `pruebas/test_temas.py` se pone roja con un literal en el CSS o un token que falte o sobre.
  En la interfaz un tema solo se elige; crearlo y comprobarlo es de la CLI (`cotejo temas`).
- **Ningún módulo pasa de 800 líneas.** `tareas/app.py` llegó a 3.721 en tres semanas porque
  todo lo nuevo del board caía en `Board`; se partió en el paquete `tareas/app/` (su
  `__init__.py` dice qué va en cada módulo). `Board` (`ventana.py`) junta mezclas, una por
  parte —banda, columnas, cartas, detalle, revisión, teclado, movimientos, maestro, pie, dot—:
  lo nuevo va en la parte a la que pertenece o en una mezcla nueva, nunca en `ventana.py` por
  comodidad. `board.json` se lee y escribe como `comun.guardar_board(...)` para que una prueba
  lo cambie en un sitio; y una prueba que reemplaza una función importada por nombre
  (`etiquetar`, `animaciones_activas`) la reemplaza en el módulo que la **usa**.
  `pruebas/test_tamano_de_modulos.py` se pone roja si un módulo de `tareas/` o `enrutador/`
  pasa del tope; los que ya lo pasaban (`verbos.py`, `dot.py`, `importar_obsidian.py`) están
  congelados en su tamaño: pueden bajar, no subir. Si se pone roja, se parte el módulo.
- **El estado de interfaz vive fuera del vault** (`board.json`, `expandidos.json`). Gracias a eso
  el board se puede rehacer entero sin renegociar nada con el agente.

- **Un adaptador externo implementa primitivas, no verbos de trabajo.** `estado`, `agente`,
  `marcar`, `crear` —como `Fuente`—, y nunca `entregar` ni `bloquear`: las reglas (evidencia,
  motivo, qué transición vale) y la bitácora son de `cli.py`. Si cada adaptador tuviera su
  `entregar`, la evidencia acabaría en Notion y cada uno validaría distinto.
- **Toda escritura de un adaptador lleva `--esperado`**, y el adaptador contesta `cambiada` sin
  escribir si la tarea ya no está así. Es la misma garantía que Obsidian da comparando la línea.
- **La config no guarda secretos.** Se guarda el nombre de la variable de entorno (`token_env`);
  `fuentes agregar` y `config validar` se niegan con cualquier clave que parezca un token.
- **Un solo archivo de config vivo.** `~/.config/cotejo/config.json` —o `~/.config/foco/` si es
  la única carpeta que hay, sin copiarla: `install.sh` la mueve y deja el enlace—; el viejo
  (`~/.config/tareas-obsidian/`) solo se lee si no existe el nuevo, y `config init` lo aparta al
  migrar. Cotejo y el enrutador lo encuentran por la misma función, `configuracion.ruta()`.
- **Cambiar de fuente no exige reiniciar.** `tareas/app/aplicacion.py` vigila la carpeta de la
  config y reabre la fuente cuando cambia (`cambiar_de_fuente`); si la nueva no abre, se queda la
  de antes.
- **Una fuente externa que no contesta es un `problema`, no una lista vacía.** Cero proyectos
  por un fallo se vería como «todo al día»; `test_la_barra_ve_el_problema_en_vez_de_todo_al_dia`
  lo vigila.

- **Ningún verbo etiqueta ni publica.** Etiquetar y publicar son decisiones de una persona, no de
  quien reparte o ejecuta trabajo. El verbo `release` devuelve un comando `git tag` para la persona,
  pero nunca lo ejecuta. Ni etiquetado automático ni publicación: `test_contrato_publicar.py` vigila
  que no exista ningún verbo de la CLI que se llame tag, publicar, push ni similares, y que ningún
  módulo de `tareas/` o `enrutador/` ejecute `git tag`, `git push` o `gh release`.

## Lo que no se cambia sin decisión consciente, en el enrutador

- **El enrutador no entrega ni finaliza tareas.** Reparte trabajo; quien lo hizo dice qué hizo
  con `entregar`, y quien lo comprueba es una persona.
  `test_ningun_verbo_del_enrutador_entrega_ni_finaliza_tareas` se pone roja si alguien lo añade.
- **Una tarea del nivel humano no se despacha, y no hay bandera para forzarlo.** `--modelo` sí
  la saca, porque eso es una persona pidiéndolo explícitamente y a la vista; lo que no puede
  existir es un `--forzar` que salte el veto «porque sí».
- **El motor por defecto es `agente`, que no lanza nada.** El trabajo lo hace un agente vivo.
  `headless` (`claude -p`) existe para lo desatendido y hay que pedirlo: que el defecto mande
  trabajo a un proceso que nadie ve es justo lo que no se quería.
- **La única excepción es preparar un proyecto** (dec-hgq7, decisión del inicio en la app, v1.3.0):
  `enrutador/preparar.py` lanza el agente sin interfaz solo para eso, con el progreso a la vista
  en el board y aviso por la barra al terminar; si se cuelga o falla, se ofrece reintentar o
  abrirlo en una terminal que se ve. Nada más usa `motores/fondo.py`.
- **El maestro se abre en una terminal que se ve, y solo reparte lo asignado.** `maestro` (y el
  botón del board) abre un cliente con una instrucción que despacha las tareas con
  `#agente/<modelo>` puestas por una persona; ni `--auto` ni `--modelo`. Abrirlo en segundo
  plano sería el «proceso que nadie ve» de arriba. `enrutador/maestro.py` arma la instrucción
  sin E/S; lo que abre la terminal está en `motores/terminal.py`.
- **Cada modelo se lanza con su cliente** (`enrutador/clientes.py`), no siempre con `claude`. Un
  motor que no puede lanzar un encargo lo dice en `comprobar()`, que `despachar` llama **antes**
  de tomar la tarea.
- **Si el modelo no lo dijo una persona, se pregunta.** Ni las reglas ni la etiqueta de
  dificultad autorizan a gastar: proponen. `despachar` sale con código 6 y enseña la propuesta.
- **Ante la duda se escala, nunca se abarata**, y **ninguna regla nueva puede abaratar**. Toca
  una regla, corre `tareas-obsidian evaluar` y mira `abaratados`: tiene que seguir en 0. Es el
  único tipo de fallo que arruina la tarea en vez de costar unos centavos.
- **Toda decisión de `despachar` deja línea, también las negativas.** Un rechazo es una
  decisión tanto como un despacho, y `rechazos.veto` es la cifra que justifica el proyecto.
  Si añades una salida nueva a `cmd_despachar`, sale por `rechazar()` o no sale.
- **El enrutador escribe en el vault por donde escribe todo el mundo**, `cli.tomar_para`. Dos
  implementaciones de «tomar» discreparían justo en la tarea que ya tiene dueño.
- **El protocolo del agente se escribe una sola vez**, en `skills/cotejo/SKILL.md`, y de ahí lo
  reparte `tareas/skill.py`. `test_el_protocolo_nombra_solo_verbos_que_existen` se pone roja si
  nombra un verbo que ya no está. `SKILL.md` es el núcleo (≤ 1.500 tokens, lo exige una prueba) y
  el detalle vive en `skills/cotejo/referencias/*.md`, que `skill.py` copia al lado y
  `cotejo protocolo --completo` imprime; otra prueba exige que también nombren solo verbos reales.
- **El set de evaluación son 42 tareas reales** (`enrutador/datos/evaluacion.json`). Las de
  origen `tag` llevan el nivel que una persona escribió en la nota: **esas etiquetas no se editan
  para que salga mejor el número**. Si una regla falla contra una de ellas, la que se discute
  es la regla.

## Lo que cambió al mudar el enrutador aquí dentro

Vivía en su propio repositorio (`../focorouter`, hoy archivado) y hablaba con Cotejo por su CLI,
en un subproceso. Al ser el mismo comando, eso dejó de tener sentido —un programa no se llama a
sí mismo para preguntarse algo que sabe— y con ello cayeron dos reglas que aquel repo defendía:

- **Ya no se le habla a Cotejo por subproceso**, sino importando `tareas.cli`. La costura sigue
  en `enrutador/cotejo.py`: decidir, planear y despachar hablan con ese objeto y no con la
  fuente. Lo que se ganó: `plan` escanea el vault una vez en vez de una por tarea.
- **La bitácora de despachos usa `ARCHIVO` de módulo**, como la de Cotejo, en vez de resolver la
  ruta en cada llamada. Es lo que deja que las pruebas la redirijan con el mismo `mock.patch`
  que todo lo demás, y no se pierde nada: XDG se lee igual al importar que al llamar.
- **La config es una clave (`enrutador`) del config de Cotejo**, no un archivo aparte.

## Si trabajan dos agentes a la vez

Pasó el 2026-09-17 y salió mal: un `git add -A` en el árbol compartido se llevó el trabajo sin
commitear del otro agente, firmado con el nombre equivocado y en la rama equivocada.

- Rama propia cada uno (`git switch -c <lo-suyo>`) o worktrees separados.
- Mira `git status` y `git branch` **antes** de commitear.
- Los dos prueban con `cotejo-dev` desde su worktree; nadie corre `./install.sh` sobre el
  Cotejo publicado.

## Bugs conocidos

Cada uno lleva cómo reconocerlo y cómo se resuelve. **Si uno vuelve a pasar**, añade la fecha a
su línea «Veces», márcalo **recurrente** y, en vez de repetir el arreglo, busca por qué volvió
(una prueba que lo vigile, o la regla que faltaba aquí arriba). Apúntalo también en el vault,
`01-Proyectos/Cotejo.md` · Problemas y soluciones.

### El menú de los 3 puntos de una carta no abre

- **Veces:** 2026-09-26.
- **Síntoma:** clic en los 3 puntos (o tecla Menú) y no aparece nada, sin error.
- **Causa:** un `Gtk.Popover` que no cabe en la ventana GTK no lo muestra. La lista «ASIGNAR A»
  crece con cada modelo del catálogo (`agentes_disponibles()`, 34 ese día); si las opciones
  salen de su `Gtk.ScrolledWindow` en `menu()` de `tareas/app/cartas.py`, el popover se hace
  más alto que la ventana.
- **Arreglo:** las opciones van en la caja `agentes`, dentro del `ScrolledWindow` con
  `max_content_height` (commit `6f522f0`). Vale para cualquier lista del board que crezca con
  datos del usuario. `pruebas/test_menu_carta.py` lo vigila: construye el menú con 40 y con 200
  modelos y se pone roja si el alto cambia o pasa de 720 px (necesita pantalla; sin ella se salta).
- **Y el board publicado no lo verá hasta el siguiente release**, que es la mitad que engañó la
  primera vez: vive en segundo plano (`--fondo`) y cerrar la ventana no recarga el código.
  Para verlo antes, `cotejo-dev --board` desde el checkout con el arreglo. Después de instalar
  un release, el proceso de fondo se reinicia por su pid (`pkill -f` con el patrón en la línea
  de comandos se lleva por delante la propia shell que lo lanza):

```sh
ps -eo pid,lstart,args | grep '[t]areas --fondo'   # si arrancó antes del release, es el viejo
kill <pid>; setsid cotejo --fondo >/dev/null 2>&1 < /dev/null &
```

## Dónde continuar

En el vault, `01-Proyectos/Cotejo.md`, sección **⏭️ Siguiente paso**: ahí está el estado del día,
el orden de lo que queda y por qué. El informe con los ocho hallazgos y sus costos medidos está
en `01-Proyectos/Revisión AX de Cotejo.md`.

Las tareas del proyecto se leen, se reparten y se mueven con la propia app, que para eso existe:

```sh
tareas-obsidian tareas --proyecto Cotejo --estado pendiente
tareas-obsidian tomar <id> --agente <quien>
tareas-obsidian entregar <id> --evidencia "qué se hizo y cómo se comprueba"
tareas-obsidian bloquear <id> --motivo "qué lo impide"   # si te atascas, esto y no dejarla a medias
tareas-obsidian plan --proyecto Cotejo                     # y a quién le toca cada una
```

`tareas` y `tomar` devuelven `motivo` si la tarea venía rechazada: léelo antes de rehacerla.
