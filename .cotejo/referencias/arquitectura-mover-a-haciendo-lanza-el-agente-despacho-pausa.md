---
id: ref-l5zo
temas: [arquitectura, board, despacho]
resumen: pendiente
---
# Arquitectura · Mover a Haciendo lanza el agente: despacho, pausa, fin y rechazo

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

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
