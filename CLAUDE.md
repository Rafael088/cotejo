# Cotejo — para quien trabaje aquí

Lee el `README.md` para saber qué es y cómo funciona. Esto es lo que además conviene saber
antes de tocar nada.

## Antes de empezar

```sh
python3 -m unittest discover pruebas   # 2244, deben estar todas en verde
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

`tareas/resumen_inicio.py` es lo que enseña la pestaña **Inicio** del board (v1.3.0), sin GTK:
saludo, titular («Tienes 3 proyectos y 2 entregas por comprobar») y una tarjeta por proyecto con
su versión en curso y el avance en **piezas hechas** de la arquitectura (por
`conocimiento.piezas_del_repo`); sin piezas dice «sin arquitectura todavía», nunca inventa un
avance con las tareas. La pinta `tareas/app/pestana_inicio.py`, que abre antes que el tablero
(salvo con la fuente rota: ahí va al tablero; y sin fuente configurada, la primera vez, abre en
**revisar el equipo**, que reemplaza al viejo primer arranque: `tareas/equipo.py`, sin GTK, mira qué
agentes (`clientes.instalados()`) y git hay y la página oficial de cada uno —las direcciones viven
solo ahí—, con cada agente **no instalado**, **falta iniciar sesión** o **listo**
(`modelos_vivos.sesion`); `tareas/app/equipo.py` lo pinta, con «Instalar» y «Iniciar sesión»
(cotejo-2j6un7: `tareas/instalar_agentes.py`, sin GTK, corre **solo el instalador oficial**
documentado de Claude Code, Codex y OpenCode —descargado a `<estado>/agentes/`, ejecutado con
`bash`/`sh` sin shell ni terminal, en un hilo, con tope, cancelable, log y un `sudo` que se
niega— y el login oficial de cada CLI, en una terminal si lo pide; Antigravity CLI, que
reemplaza a Gemini CLI en cuentas personales, se instala igual y recibe tareas, pero guarda la
sesión en el llavero sin forma documentada de preguntarla —«Instalado», que cuenta como listo,
`modelos_vivos.SESION_INVISIBLE`—; Gemini CLI («solo con licencia de empresa») y git siguen
enlazando),
sondea la sesión en un hilo cada pocos segundos mientras se ve —`modelos_vivos.sesion` pregunta
a `codex login status` / `claude auth status` si la sesión vive en el llavero, solo con
`preguntar_cli`, nunca al pintar—, tiene «revisar otra vez» y «Seguir al Inicio»; después del
primer arranque se llega con «Agentes» en el Inicio o desde «Añadir modelo») y
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

**«Ver mi app» y «Abrir la carpeta»** (v1.3.0, cotejo-vn4qd2) van en cada tarjeta del Inicio
y en la barra del mapa (`tareas/app/ver_app.py`, mezcla `VerApp`), siempre sobre la carpeta
principal del proyecto (`fuente.carpeta_de`), nunca un worktree. Qué abrir lo dice
`tareas/como_se_abre.py`, puro: la sección `## Cómo se abre` de la arquitectura (`- comando:`,
`- url:` opcional, `- qué esperar:`, `- carpeta:` opcional; `FORMATO`), que pide el prompt de
preparar y que el encargo de cada agente (`enrutador/encargo.py`) pide mantener al día;
`anotar`/`editar` la validan (sin shell, sin `sudo`, sin salir de la carpeta) y volver a anotar
la arquitectura la conserva (`reintento.guardar`). Sin ella deduce (`package.json` con `dev`/
`start` → `npm run …`; `index.html` → el servidor estático de Cotejo, `http.server` en un puerto
libre de 127.0.0.1) y si no, `SIN_ANOTAR` en llano. `tareas/servidor_app.py` arranca sin shell
(`shlex.split`, grupo de procesos propio), un proceso por proyecto que se reutiliza, espera a
que el puerto responda (la dirección puede salir de lo que imprime la app) con tope y error en
llano, y lo para con «Parar», al cerrar la ventana o por `atexit`; el log va a
`<estado>/ver-app/<proyecto>.log`. El navegador y la carpeta los abre el board con
`Gio.AppInfo.launch_default_for_uri` (`VerApp.lanzar`), fuera de cualquier sandbox.

**Los modelos de todos los agentes** (v1.3.0, cotejo-qixs4j). `enrutador/modelos_vivos.py` dice
qué agentes están **listos** (instalados y con sesión: solo mira sus credenciales en disco o su
variable de entorno, nunca lanza el CLI) y qué modelos ofrece cada uno: `opencode models`,
`codex debug models` y su `~/.codex/models_cache.json` (que se lee antes, sin lanzar nada) se
preguntan (caché en `<estado>/modelos/`, tope de segundos, y si fallan lo guardado o el respaldo);
Claude y Gemini no listan y su lista son sus alias. Nada de eso gasta tokens.
`niveles.DE_FABRICA` trae los de fábrica de los otros agentes (`gemini-pro|flash|flash-lite` por
alias; `opencode` = «el modelo que tenga por defecto», sin `-m`; los cuatro modelos reales de
Codex, `gpt-5.6-luna|terra|sol` y `gpt-6-astra`, con su nombre exacto), que un registrado con la
misma clave tapa; los nombres viejos de Codex (`codex`, `codex-rapido`, `codex-fuerte`) siguen
resolviendo por alias a luna/sol/astra (`niveles.ALIAS_DE_ANTES`); `niveles.grupos` arma
«Asignar a» por agente y `niveles.del_cliente`
traduce un tamaño al agente del proyecto sin abaratar. El agente del proyecto es `agente:` en
`.cotejo/proyecto.md` (`origen.agente_de`), que pone `init` con `COTEJO_AGENTE` (lo añade
`preparar.lanzar`); con él, lo que el enrutador decide por tamaño se propone con ese agente
(`decision.decidir(cliente=…)`, en `plan`, `decidir`, `despachar`, el board y «Empezar la 0.1.0»).
El board (`tareas/app/modelos.py`) agrupa, pone el del proyecto primero y tiene «Añadir modelo…»
(en «Asignar a» y en el menú de la cabecera), que registra como `cotejo modelos agregar`;
`cotejo modelos vivos` es lo mismo por la CLI.

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
nunca borra la rama) corre únicamente si la persona dice que sí. **Salvo en un proyecto
creado desde el Inicio** (cotejo-00fwc2): lleva `origen: inicio` en `.cotejo/proyecto.md`
(`tareas/origen.py`), que pone `init` solo con `COTEJO_ORIGEN=inicio` en el entorno (va en
`inicio.ENTORNO`, el del agente que lo prepara), y ahí aprobar llama a `integrar_sola`: el mismo
merge sin preguntar y, si entra, `branch -d` de la rama (el worktree ya se retiró). Corre en
segundo plano (`Board.en_fondo`, un hilo que vuelve con `GLib.idle_add`; las pruebas lo
inyectan): mientras tanto la carta lleva «Integrando…» y esa tarea no se vuelve a aprobar. En
ningún proyecto `.cotejo/` cuenta como «sin commitear» al integrar (el board lo reescribe al
mover); si la rama lo pisaría, git se niega antes de empezar. Lo que ve la persona sale de
`aviso_inicio`, sin nombrar ramas: limpio, «Ya está en tu app»; choque, el merge se aborta y se
ofrece «Que lo resuelva un agente» (crea una tarea de juntar los dos trabajos con el modelo de la
aprobada, apunta qué rama junta en `<estado>/juntar/<id>.json` —`tareas/juntar.py`— y la mueve a
Haciendo por `mover`; al aprobarla e integrarla, `branch -d` también de la original, sin forzar);
cambios sin guardar, «Reintentar». El tooltip de Aprobar dice «La mete en tu app». Sin marca
—todos los de antes— sigue el diálogo de siempre. La CLI no gana verbos con esto. El diff se pinta solo con GTK4 + Adwaita (sin GtkSourceView): una etiqueta por línea,
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
`asignar` la encuentran aunque la persona use Obsidian, sin tocarle la config. Y con un PATH que lleva primero el
lanzador `cotejo` de `enrutador/mismo_cotejo.py` (en `<estado>/agente/bin`, reescrito en cada
lanzamiento): corre `sys.executable` con el paquete de este mismo proceso, así el agente usa el
Cotejo del board y no otro instalado (el publicado mientras se prueba con `cotejo-dev`). Si el
otro es de otra versión, queda en `otro_cotejo` del registro y Preparando lo dice en llano.
Sin nadie delante cada cliente se niega a escribir fuera de donde arrancó, así que el agente
recibe permiso solo para `preparar.carpetas_de_escritura` (la carpeta del proyecto —o la de
arriba si aún no existe— y su `.git`, la de la config de Cotejo y la de estado), cada uno a su
manera (`clientes.Cliente.permisos`, cotejo-p0fybl): Codex `exec --sandbox workspace-write
--skip-git-repo-check --add-dir …`; OpenCode `permission.external_directory` por
`OPENCODE_CONFIG_CONTENT`; Gemini `GEMINI_CLI_TRUST_WORKSPACE` y `--allowed-tools
run_shell_command(cotejo)`; Claude nada más que su `Bash(cotejo:*)`, con un `--` antes del prompt
porque `--allowedTools` se come lo que venga detrás.

`enrutador/despacho_board.py` y `tareas/lanzados.py` son **mover a Haciendo lanza el agente**
(v1.3.0, cotejo-7xsjb8). Pasar a mano una tarea de Pendiente a Haciendo —arrastrando, con el
menú, Ctrl+→ o desde la ficha: todo pasa por `Movimientos.mover`— llama a `lanzar_al_mover`
(`tareas/app/lanzar.py`), que llama a `despacho_board.lanzar`. Las reglas son las de `despachar`
y con sus piezas: n0 no se lanza (`EsDeUnaPersona`: se mueve como siempre); sin modelo puesto por
una persona se pregunta con la propuesta y su porqué (`FaltaModelo`; el board lo guarda con
«asignar», y «La hago yo» la asigna a la persona sin lanzar); si `capacidad` da 0 no se lanza y
queda **en espera** (`SinHueco`: sigue en Pendiente con un chip «En espera» y el motivo en su
ficha, anotada `en-espera` en el registro; nada la relanza sola, se vuelve a mover cuando haya
hueco); lo demás que impediría lanzar se dice antes de tomarla (`despacho.antes_de_tomar` con el
motor `headless`). Luego toma, crea su worktree, arma el encargo de siempre y lanza el cliente
sin interfaz (`motores/fondo.py`, con `PWD` igual al worktree: OpenCode trabaja donde dice
`PWD`) con el mismo `cotejo` en el PATH y **terminal libre en el worktree con prohibidos de
fábrica** (cotejo-7yfw1e, dec-kiik): `clientes.Cliente.terminal_libre` (Claude: `acceptEdits`,
`--allowedTools Bash` y `--disallowedTools` con `clientes.prohibidos`; Codex: su sandbox
con un **perfil de permisos** en vez de `--sandbox workspace-write` (cotejo-srkywv,
`clientes._codex_perfil`, por `-c default_permissions=… -c permissions.cotejo-tarea=…`, sin tocar
`~/.codex/config.toml`): con `--sandbox` el `.git` de cada carpeta y el `gitdir:` de un worktree
quedan en solo lectura sin remedio (`git commit` caía con `index.lock`), la carpeta de la tarea
no estaba (`entregar`/`bloquear` fallaban) y sin red su seccomp niega hasta los sockets locales
(ni Firefox ni un puerto). El perfil (https://developers.openai.com/codex/permissions, beta)
escribe donde el sandbox de Claude (`armado.sandbox_de` le da el `del_lanzamiento` sin token),
más el gitdir del worktree, y deja en `read` lo vedado (hooks, config del `.git`, los otros
worktrees, la config de Cotejo); su red es solo `localhost`/`127.0.0.1` por el proxy de Codex
(`--enable network_proxy`, experimental): no empuja, y Firefox y un servidor local sí van
(`curl --noproxy '*'`; Chromium no). `lanzar.sandbox: false` no se lo quita. En Windows, como
antes. `COTEJO_PRUEBA_CLIENTES=1 python3 -m unittest discover pruebas -p test_codex_perfil.py`
lo corre en `codex sandbox` de verdad, sin modelo; OpenCode: `permission.bash` todo `allow` y los prohibidos `deny`
al final; Gemini: `auto_edit` y `--policy` con las de la persona delante y `politica_gemini_toml`
detrás, porque `--policy` sustituye las suyas y hay que devolvérselas —lo suyo gana, y la de
Cotejo permite el shell en la prioridad 0 y niega los prohibidos en la 900—) y, debajo, las guardas del
PATH (`guardas.py`: un `git` que lee los argumentos y no deja `push` a la fuerza ni a `main`/la
rama por defecto —`worktrees.rama_por_defecto`—, y `sudo`/`su`/`doas`/`pkexec` que se niegan).
Los prohibidos son sudo/su, `git push --force`, empujar a `main` o a la rama por defecto y borrar
fuera del worktree (ruta absoluta, `~`, `$HOME` o `..`). Con Claude, además, su Bash va en
**el sandbox de Claude Code** (cotejo-amui0f, `enrutador/sandbox.py`, por `--settings`): escribe
solo en el worktree, el `.git` del repo (sin `hooks` ni `config`), la carpeta de estado de Cotejo,
la carpeta del archivo de la tarea (`Cotejo.carpeta_de_la_tarea`) y un remoto que sea carpeta; no
escribe en los demás worktrees; la red solo a los servidores de sus remotos (+`api.github.com`) y
`lanzar.sandbox.dominios`. **La config de Cotejo no la escribe ningún agente de tarea**
(cotejo-dgb7l2: `lanzar.sandbox: false` o un `argumentos_extra` le quitarían el sandbox a los
siguientes): su carpeta no está en `armado.carpetas_de_escritura` (para los cuatro clientes; en
macOS se da solo la de estado, que cuelga de ella), sus archivos (`configuracion.archivos()`) van
en `denyWrite` y en `--disallowedTools Edit(//…)`, y el entorno lleva `COTEJO_CONFIG_VEDADA=1`,
con la que `configuracion.guardar` y `guardar_modelos` se niegan (`ConfigVedada`, que `cli.main`
imprime como un error más). Preparar sí la escribe (`init` registra el repo) y no pasa por aquí.
`pruebas/test_config_vedada.py` lo prueba en bwrap. **Tampoco carga los ajustes del proyecto** (cotejo-0hgn6x): Claude va con `--setting-sources user` (`clientes.SOLO_AJUSTES_DE_LA_PERSONA`), así que un `.claude/settings.json` o `settings.local.json` del worktree —con un hook que correría fuera del sandbox— no se lee al retomar ni a media sesión; vedar `.claude` no bastaba (`denyWrite` no para un archivo que no existe, y Codex u OpenCode en el mismo worktree no pasan por el sandbox de Claude). El `CLAUDE.md` del repo y las skills de la persona siguen; las de `.claude/skills` del repo no. Con Claude de verdad: `COTEJO_PRUEBA_CLAUDE=1 python3 -m unittest discover pruebas -p test_ajustes_del_proyecto.py` (haiku). **Ni lo que el proyecto le haría arrancar a los demás** (cotejo-j42qfc, cotejo-lbwsq4): Codex va con el worktree sin confianza; OpenCode, con los servidores MCP del proyecto en `enabled: false` y, si el proyecto trae plugins o herramientas en JavaScript (`.opencode/plugin(s)`, `.opencode/tool(s)`, `plugin` en su `opencode.json`), con `OPENCODE_DISABLE_PROJECT_CONFIG` (se pierde su `AGENTS.md` en ese lanzamiento); Gemini CLI, que solo corre sin interfaz en un espacio de confianza y con ella lee el `.gemini/settings.json` del worktree, con `--allowed-mcp-server-names` y los servidores de la persona (`clientes_gemini._gemini_sin_lo_del_proyecto`), y si ese archivo trae hooks, `tools.discoveryCommand`/`callCommand` o rutas de políticas —nada los apaga sin llevarse los de la persona—, con `GEMINI_CLI_TRUST_WORKSPACE=false`: no arranca. Para que eso no se descubra con un log en inglés, `clientes_gemini.aviso_de_gemini` (cotejo-dzhzca) dice en llano qué archivo es y qué quitar, y `despacho.antes_de_tomar` lo devuelve como rechazo `gemini_sin_confianza` antes de tomar: lo ven igual `despachar` y el board (que reutiliza el mismo `antes_de_tomar`), y la comprobación se repite sobre el worktree ya creado por si lo de la rama difiere del repo. Con la confianza Gemini carga además el primer `.env` (o `.gemini/.env`) que encuentra subiendo desde el worktree y añade las variables que no existan (cotejo-4gvdy5): una `BASH_ENV` ahí corría un archivo del repo antes de cada `bash -c`, por debajo de los prohibidos y las guardas. `enrutador/gemini_env.py` define antes, vacías, las de `gemini_env.VEDADAS` (+ `VEDADAS_PREFIJOS`: shells, `LD_*`, `NODE_*`, `GIT_*`, `PYTHON*`, proxies…) que traiga un `.env` que no es de la casa de la persona; las demás (`GEMINI_API_KEY`, `DATABASE_URL`…) siguen. Codex solo lee `~/.codex/.env` y OpenCode va compilado con `autoloadDotenv: false`: no cargan el del proyecto. Preparar no lo mira (la carpeta es de la persona). `COTEJO_PRUEBA_CLIENTES=1 python3 -m unittest discover pruebas -p test_env_del_proyecto.py` lo prueba con los tres CLI, sin modelo. Con los clientes de verdad, sin modelo: `COTEJO_PRUEBA_CLIENTES=1 python3 -m unittest discover pruebas -p test_config_gemini_opencode.py` (la sesión de Gemini va sin red, con `unshare -rn`). Lleva `GH_TOKEN` (de `gh auth token`: el llavero no se alcanza desde
el sandbox) y `COTEJO_SANDBOX=1`, con el que la guarda de `git` quita el `-u` de un push. Sin
bwrap/socat (o sin espacio de nombres, o en Windows) no se pide y el registro guarda
`sandbox.activo: false` con el motivo; `lanzar.sandbox: false` lo apaga. Para ver lo que hace,
el agente tiene **Firefox sin interfaz** dentro del sandbox (`enrutador/navegador.py`,
cotejo-xrmr3h: `capturar()`, `python3 -m enrutador.navegador <archivo|url> <png>` y la línea
`COMO_CAPTURAR` que lleva `armado.NOTA_SANDBOX`); Chromium no arranca ahí (su ProcessSingleton
pide `socket(AF_UNIX)`, que el seccomp de Claude niega a propósito, y no se abre). Un servidor
en `localhost` vale si va en el mismo comando que el navegador. `pruebas/test_navegador_sandbox.py`
lo prueba en bwrap con esas reglas. No viven en la config:
`enrutador.lanzar.argumentos_extra.<cliente>` solo añade (Claude: `stream-json`). El agente de
`despachar --motor agente` no comparte este armado (no lanza nada) ni el de preparar (solo
`cotejo`). El armado entero (terminal libre, ramas protegidas, carpetas de escritura, sandbox,
guardas y entorno) vive en `enrutador/armado.py` y lo usan igual el board y
`despachar --motor headless` (`motores/claude_cli.py`, cotejo-6a7np9: el `Encargo` lleva
`origen` y `worktree`; sin `directorio` no hay terminal libre y el argv queda como antes).
Toda decisión deja línea en `despachos.jsonl` con `motor: "board"`. El
registro es uno por tarea en `<estado>/lanzados/<id>.json` (`pid`, `programa`, `host`, `log`,
`log_desde`, `cliente`, `modelo`, `worktree`, `directorio`, `comando`, `prompt`) con fases
`lanzado` / `terminado` / `en-espera` / `detenido`, y `lanzados.estado` da `trabajando`, `murio`,
`terminado`, `en-espera` o `detenido`. `despacho_board.detener(id)` para el proceso sin tocar la
tarea ni el worktree (lo usan pausar y retomar, y el fin y el rechazo). La ficha de una tarea en
Haciendo lanzada así enseña «Lo que hace el agente» (`lanzar.EnVivo`): `lanzados.Seguimiento` lee
solo lo nuevo del log y `lanzados.legible` pasa el `stream-json` a texto llano, con un
temporizador que existe solo mientras la ficha se ve (`do_map`/`do_unmap`).

**Pausar y retomar** (v1.3.0, cotejo-z7ma7r). Devolver a mano a Pendiente una tarea que lanzó el
board la pausa (`Lanzar.pausar_al_mover` → `despacho_board.pausar`): su agente se para y queda
`detenido`, y el worktree, la rama y el `#agente/<modelo>` se quedan (`retirar_worktree` no la
toca); su ficha en Pendiente dice «Pausada». Pasarla otra vez a Haciendo vuelve por `lanzar`, que
reutiliza el worktree y lanza un agente **nuevo** con el encargo de siempre más la nota de
retomar de `tareas/retomar.py`, armada sola y sin IA: commits de la rama desde su base (`base`
en el registro; `worktrees.crear` ya no mueve `desde` al reutilizar), `git status` del worktree
y las últimas líneas legibles del log del lanzamiento anterior. Nunca hay dos agentes vivos en
una tarea ni se resume el viejo. El registro guarda `encargo` (sin nota), `prompt` (con ella) y
`reanudacion` (`vez`, `anterior`, `commits`, `sin_commitear`, `nota`); «Lo que hace el agente»
dice «está retomándola» y «Es una reanudación (vez N)…». `retomar.nota(registro, motivo)` es
lo que reutiliza el fin y el rechazo (cotejo-o253bs). Una pausada que se mueve sin hueco queda
en espera sin perder lo del lanzamiento anterior.

**El fin y el rechazo** (v1.3.0, cotejo-o253bs). El proceso del agente se cierra solo al
terminar, y el hilo de `vigilar` le hace el fin (`despacho_board.fin`, **una vez por
lanzamiento**: `lanzados.reclamar_fin` y la clave `fin` del registro, con `como` =
`entrego` / `sin-entregar` / `otro`). Si entregó, la tarea ya está en Para comprobar y su
registro y su log se quedan: la ficha y la revisión enseñan sus mensajes (`seccion_en_vivo`
vale también en Para comprobar). Si sigue en Haciendo a su nombre, terminó **sin entregar**:
`cotejo.soltar` la devuelve a Pendiente con su modelo y el motivo en llano («El agente terminó
sin entregar…», con lo último que dijo) y el registro queda `detenido` con
`motivo: "el agente terminó sin entregar"`, así que sale «Pausada» y conserva el worktree. Si la
bloqueó o la movió alguien, no se toca. Los que murieron con el board cerrado los recoge
`despacho_board.recoger()`, que `App.refrescar` llama antes de leer (salta los pids que espera
un hilo de este proceso). Nada de esto relanza: lanzar es siempre de una persona. **Devolver de
Para comprobar a Haciendo con motivo** una tarea que lanzó el board (`Lanzar.relanzar_al_rechazar`,
desde `al_responder_motivo`) llama a `despacho_board.rechazar(id, motivo, mover)`: para al
anterior si sigue vivo y guarda `rechazo` en el registro (motivo, la entrega anterior en llano de
`retomar.rechazo` y `de_pid`, que impide que el fin del anterior la suelte) **antes** de que
`mover()` escriba la línea y el «rechazar» de siempre; luego lanza uno nuevo en el mismo worktree
sin volver a tomarla, con el encargo (sin repetir motivo ni evidencia), la nota de retomar y
«Lo que te pidieron cambiar» (`retomar.armar_rechazo`). Si no se puede lanzar (sin hueco…),
vuelve a Pendiente con el rechazo guardado y el siguiente lanzamiento lo lleva mientras no haya
una entrega más nueva (`retomar.rechazo_vigente`).

`enrutador/conversacion.py` es **el maestro como conversación** (v1.3.0, cotejo-9ybn1a). La
barra del pie (`tareas/app/maestro.py`) le manda lo que escribe la persona a
`verbos.hablar_maestro` → `apertura.hablar`, que arma el turno (`apertura.armar`: proyecto,
pendientes asignadas, carpeta de `fuente.carpeta_de`, instrucción con la conversación de
`maestro.instruccion`) y lo lanza sin interfaz por `motores/fondo.lanzar_aparte` (stdout y stderr
aparte: la respuesta de Codex es su stdout). La conversación de cada proyecto vive en
`<estado>/maestro/<proyecto>.json` y viaja entera, recortada (`TURNOS_DE_MEMORIA`), en cada turno:
no todos los clientes documentan cómo retomar su sesión sin interfaz. Un hilo espera el turno, lo
anota con lo que propuso repartir y el board repinta y refresca (lo apuntado sale en el tablero);
un turno con el proceso muerto se cierra al leer. Permisos por cliente en `conversacion.comando`:
Claude `--allowedTools Bash(cotejo:*)`, `Edit`/`Write` vedados y `--setting-sources user`; Codex
`workspace-write` con la carpeta de las tareas como directorio de trabajo y la de estado (el código
queda en solo lectura); OpenCode `edit: deny` y `bash` todo `deny` salvo `cotejo`, sin MCP ni
plugins del proyecto; Gemini `run_shell_command(cotejo)` y sin lo de su `.gemini/`; Antigravity en
la jaula de bwrap o no habla. Todos con la config vedada y el mismo `cotejo` del board. El panel
(`tareas/app/conversacion.py`, `PanelMaestro`) es un `Gtk.Revealer` sobre el pie; «Repartir» va
por `mover`. La CLI es la misma: `cotejo maestro --proyecto X --pedido "…"` espera la respuesta.
`pruebas/test_maestro_conversacion.py` (sin GTK) y `pruebas/test_barra_maestro.py` (board de
verdad) lo prueban de punta a punta con `cliente_falso.py`.

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
- **Las excepciones son tres, y las pide una persona en el board.** Preparar un proyecto
  (dec-hgq7, decisión del inicio en la app, v1.3.0): `enrutador/preparar.py` lanza el agente sin
  interfaz solo para eso, con el progreso a la vista en el board y aviso por la barra al
  terminar; si se cuelga o falla, se ofrece reintentar o abrirlo en una terminal que se ve. Y
  mover a mano una tarea de Pendiente a Haciendo (cotejo-7xsjb8): `enrutador/despacho_board.py`
  la lanza con su modelo asignado y lo que hace se ve en vivo en su ficha. Y cada mensaje al
  maestro (cotejo-9ybn1a): `enrutador/conversacion.py` lanza un turno que solo corre `cotejo`,
  con la conversación a la vista. Nada más usa `motores/fondo.py`, y ninguna de las tres lanza
  nada que la persona no haya pedido.
- **El maestro es una conversación dentro del board, nunca una terminal, y solo propone
  repartir lo asignado** (decisión del dueño del 2026-10-27, cotejo-9ybn1a; antes «se abre en
  una terminal que se ve»). Por qué cambió: la terminal era una ventana fuera de la app que
  quien no programa no sabe leer, interrumpir ni cerrar sin miedo, y lo que hacía ahí el board
  no lo veía; la regla vieja quería evitar el «proceso que nadie ve», y eso se cumple mejor con
  la conversación a la vista en el board —lo que dice, cada `cotejo` que corre y su respuesta—
  que con una terminal aparte. Cada mensaje es un turno sin interfaz que **solo lee y corre
  `cotejo`** (`conversacion.comando`, con los permisos de cada cliente; ninguno edita
  archivos), lo pide siempre una persona escribiendo, y el maestro **no lanza agentes**: para
  repartir termina con `REPARTIR: <ids>`, Cotejo filtra a las pendientes con `#agente/<modelo>`
  puestas por una persona (`maestro.pedidas`) y el board enseña un botón que las mueve a
  Haciendo por `Movimientos.mover`, con todas sus reglas. Ni `--auto` ni `--modelo`, ni
  despachar, ni entregar, ni finalizar. `enrutador/maestro.py` arma la instrucción sin E/S;
  `motores/terminal.py` ya solo lo usa preparar («abrir en una terminal» si se cuelga).
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
