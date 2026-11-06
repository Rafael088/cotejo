---
id: ref-rvpe
temas: [arquitectura, importar, preparar]
resumen: pendiente
---
# Arquitectura · Importador, vista de revisión y preparación en segundo plano

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

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
mover). Antes del merge se guardan en un commit solo las fichas de `.cotejo/`, incluidas las
nuevas y borradas, respetando los ignorados; así una ficha duplicada en la rama ya no provoca
«would be overwritten» (cotejo-7kmlvw). Si ese guardado falla, no se intenta integrar. Si hay
cambios incompatibles, se aborta el merge conservando el commit de fichas y la rama de la
tarea para resolverlo, sin elegir una versión a ciegas. Lo que ve la persona sale de
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
