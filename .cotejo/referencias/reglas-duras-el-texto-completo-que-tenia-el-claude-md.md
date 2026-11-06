---
id: ref-62y4
temas: [reglas, cotejo]
resumen: pendiente
---
# Reglas duras: el texto completo que tenía el CLAUDE.md

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol). El CLAUDE.md las deja en una línea con su dec-id; aquí está el texto entero, con las pruebas que vigila cada una.

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

## Si trabajan dos agentes a la vez

Pasó el 2026-09-17 y salió mal: un `git add -A` en el árbol compartido se llevó el trabajo sin
commitear del otro agente, firmado con el nombre equivocado y en la rama equivocada.

- Rama propia cada uno (`git switch -c <lo-suyo>`) o worktrees separados.
- Mira `git status` y `git branch` **antes** de commitear.
- Los dos prueban con `cotejo-dev` desde su worktree; nadie corre `./install.sh` sobre el
  Cotejo publicado.
