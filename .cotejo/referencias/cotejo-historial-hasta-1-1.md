---
id: ref-r7qy
temas: [proyecto/cotejo, archivo]
resumen: "Bitácora y decisiones de Cotejo del 2026-09-16 al 2026-09-28, hasta cerrar la v1.1; se sacaron de la nota principal al limpiarla antes de empezar la v1.2."
---
# Cotejo - Historial hasta 1.1

# Cotejo — historial hasta la 1.1

Sacado de [[proyecto|Cotejo]] el 2026-10-03 al limpiar la nota antes de la 1.2. Nada de aquí es tarea: las tareas siguen en [[proyecto|Cotejo]].

## 📓 Bitácora (2026-09-16 → 2026-09-28)

### 2026-09-28
- Logo nuevo de Cotejo: la palabra «Cotejo» con la C del check como primera letra, y esa C sola como ícono, favicon y barra. CotejoBoard lo lleva en la cabecera («Cotejo» + «Board») con los colores del tema. Kit web y brand-showcase.html en docs/marca/, todo generado por docs/marca/generar.py. En master (e244abf, sin subir al remoto) e instalado con --sin-agentes. Ver [[cotejo-identidad-publica|Cotejo - Identidad pública]].

### 2026-09-25
- Temas de CotejoBoard (cotejo-h14yx5) hechos, fusionados en master (ffe2b3a, 777fc90) e instalados: oscuro y claro de fábrica, selector ◐ junto a recargar, verbos cotejo temas, CSS sin colores literales (se fueron el #FFFFFF de button.flat:hover, .vacio-titulo y tooltip). 447 pruebas en verde, evaluar sigue en 85,7 % y 0 abaratados. Prueba de AX: un subagente Haiku sin contexto creó el tema Neón Morado (#000000 + #CC00FF) a la primera; corregidos los dos huecos que dejó (la skill cotejo ahora nombra los temas; temas nuevo y comprobar piden la descripción).

### 2026-09-24
- Creado planning para conectar Cotejo a cualquier aplicativo vía fuentes externas por subprocess, con Notion como primera prueba. Ver [[cotejo-planning-de-fuentes-externas|Cotejo - Planning de fuentes externas]].
- Fuentes externas hechas e instaladas ([[cotejo-planning-de-fuentes-externas|Cotejo - Planning de fuentes externas]]): verbos doctor, fuentes y config init|validar; adaptador genérico por subproceso; cotejo-notion probado contra la base real «Cotejo — prueba» (leer, tomar, entregar, crear, bloquear). Eliminación de CotejoList commiteada (3fc52a2), rebase, fast-forward de master hasta cd2d839 e instalado. Config migrada a ~/.config/cotejo/config.json. Cambiar de fuente ya es un comando y la app lo sigue sin reiniciar; skill cotejo-fuentes. 418 pruebas. Fuente activa: Obsidian.

### 2026-09-23
- Implementado en CotejoBoard el rediseño de Claude Design, en la rama `diseno-tokens-escalas` (commits 174a876 y 07ab95a). Los seis cambios: el verde deja el chip de agente y queda solo para lo que espera comprobación; columnas proporcionales (256/232/238/196 px); dificultad con barras de señal; menú de carta con iconos y atajos visibles; búsqueda a la vista que filtra el board entero; y deshacer acumulado. Más 28 iconos propios generados. 283 pruebas en verde e instalado.
- Barras de desplazamiento del board adelgazadas (commit 3d0c567): en reposo son una línea de 3 px casi transparente y solo se ensanchan con el cursor encima. Las había dejado anchas y opacas al tematizarlas, y eso anulaba el indicador flotante de GTK.
- Loop de tareas (como maestro, de dos en dos sin cruzarse): 13 tareas entregadas a Opus, Sonnet y Haiku, cada una verificada antes de instalar, e instalado 187d5e4. Símbolo de Cotejo en la barra, fecha al marcar, Inbox/Diario opcional (carpetas_sueltas, apagado), cabecera única, iconos propios en CotejoList, nombres accesibles, transiciones que respetan las animaciones apagadas, columna «Para comprobar», breakpoint que pliega la lateral por debajo de 1202 px, estado vacío único, y el medidor de ahorro con su razón honesta al filtrar (4,7 en vez de 21,9). Queda solo Temas, aparcada a propósito.

### 2026-09-18
- Hallazgo 5 completo: las cartas de En espera de comprobación traen la evidencia con la que el agente entregó, recortada a tres líneas, y el menú ⋮ la abre entera y seleccionable para copiar un commit.
- Devolver una tarea pide motivo por las tres vías (arrastre, Ctrl+←/→ y menú), porque las tres pasan por Board.mover; el botón no se enciende con el motivo vacío y Escape no escribe nada. El motivo se queda en la carta, en ámbar, hasta que se vuelva a entregar.
- Nuevo tareas/bitacora.py: anotar() se mudó ahí desde cli.py y apareció ultimas(), que devuelve por tarea la última anotación con texto libre leyendo solo la cola del archivo. tareas y tomar ahora devuelven evidencia o motivo, así que el rechazo le llega al agente antes de rehacer la tarea.
- Los movimientos del board quedan anotados en la bitácora; comprobar y rechazar llevan nombre propio porque son las dos transiciones que solo hace una persona.
- 151 pruebas (23 nuevas: test_bitacora.py y test_anotacion.py, que se salta sola si no hay GTK). Commit 83b356c, instalado y proceso de fondo reiniciado.
- Verbo bloquear: el agente que se atasca devuelve la tarea a Pendiente, sin dueño y con el motivo obligatorio. Solo se bloquea lo que se está haciendo; reintentar es seguro y lo ya entregado manda a CotejoBoard, porque de ahí en adelante decide una persona.
- En el board una carta parada lo dice en ámbar con la palabra que corresponde: BLOQUEADA si la paró quien la hacía, DEVUELTA si la paró quien iba a comprobarla. Mismo color porque piden lo mismo, que alguien mire.
- 160 pruebas (9 nuevas). La prueba que vigila los verbos de la CLI sube a seis y sigue sin haber ninguno para finalizar. Commit cbd0215, instalado y proceso de fondo reiniciado.
- Hallazgo 3 hecho: vault.py se partió en modelo.py, fuente.py y fuentes/obsidian.py. La CLI, las dos ventanas y el resumen de la barra hablan con la interfaz; el único código que sabe de notas, tags y marcas de bloque es la fuente Obsidian, y sigue siendo el único que escribe en el vault.
- La prueba que impide que la capa sea decorativa: test_fuente.py corre tomar, entregar, bloquear y el resumen contra una fuente en memoria y comprueba que no se tocó ningún archivo. 172 pruebas. Commit c8fb0c1.
- Cierre del día: los ocho hallazgos de la revisión AX cerrados, 172 pruebas, tres commits (83b356c, cbd0215, c8fb0c1). El ciclo del agente quedó completo y el contrato dejó de ser el Markdown. Lo siguiente es usarlo unos días, no construir.
- Idea de Rafael, anotada como tarea: un medidor de tokens ahorrados gracias al diseño AX. Se guarda con la condición de que las dos mitades del número sean medidas y el supuesto (que sin Cotejo el agente habría leído la nota entera) se diga en voz alta.
- Rama worktree-skill-cotejo-agentes, cuatro commits y 236 pruebas en verde (eran 172). Se hizo el protocolo para agentes en skills/cotejo/SKILL.md, repartido por install.sh a Claude Code, Codex, Gemini CLI y opencode, más el verbo protocolo para cualquier agente con terminal. Se hizo el medidor de ahorro: mide 10,4x sobre este vault y sale al pie de la lateral de CotejoBoard como «(N) Tokens ahorrados / frente a leer las notas enteras», en plata y sin acento. Se añadió el verbo crear, que faltaba y salió al intentar anotar la tarea de los temas. Quedan sin mergear: falta correr install.sh y reiniciar el proceso de fondo.

### 2026-09-17
- El ícono flotante salió del escritorio y entró a la barra de Omarchy como widget QML propio (cotejo.barra): abre y cierra la ventana, y avisa en verde cuando hay tareas por validar.
- El escaneo del vault pasó de la ventana a la app, que ahora escribe estado.json en cada cambio; el widget lo vigila y puede recalcularlo solo con tareas-obsidian --estado.
- Símbolo nuevo (lista con dos checks en Verde Señal) en la cabecera de la app y en el ícono del menú; el pétalo de la marca anterior quedó fuera.
- vault.py ya entiende los estados #en-curso y #por-validar del flujo de Apps para agentes: los cuenta y los saca del texto de la tarea.
- La app pasó a llamarse Cotejo en el título, la cabecera y el menú; el application id se quedó igual para no romper las reglas de ventana ni la entrada del menú.
- Board nuevo: botón de cuadrícula junto a buscar y recargar, ventana de 1280x820 con las tareas de todos los proyectos en Pendiente, Haciéndola, En espera de comprobación y Finalizada, con el agente asignado y la dificultad en cada carta.
- vault.py aprendió a leer las tareas hechas, el tag #agente/x y la dificultad, y a escribir cambios de estado y de asignación con la misma verificación que el check.
- Las ventanas pasaron a llamarse CotejoList y CotejoBoard; abrir el board cierra la lista y cerrarlo la devuelve.
- CotejoBoard ganó barra lateral de proyectos con contador y aviso de lo que espera comprobación, agrupación por proyecto en el modo Todos, estados vacíos con guía y una animación de entrada que respeta la preferencia del sistema.
- CotejoBoard se recorre entero con el teclado: `Tab` salta de columna en columna en el orden visual, las flechas van de carta en carta, `Enter` abre la nota y la tecla Menú abre el `⋮` de la carta enfocada.
- Las cartas se arrastran con el mouse de una columna a otra (y `Ctrl+←` / `Ctrl+→` hacen lo mismo sin soltar el teclado); al mover una tarea el foco la sigue hasta su columna nueva.
- Instalada la skill ui-ux-pro-max (npx skills add) y usada para decidir estados vacíos, estado activo, foco de teclado y criterios de movimiento.
- Revisión AX con la skill /ax: medido que enterarse de los conteos cuesta ~80 tokens y saber cuáles son las tareas, entre 4.700 y 36.600 porque no hay camino barato. Ocho hallazgos priorizados en [[revision-ax-de-cotejo|Revisión AX de Cotejo]].
- git init y primer commit: hasta hoy el único código que escribe en las notas del vault no tenía control de versiones.
- CLI para agentes: tareas, tomar, entregar y asignar, en JSON y sin cargar GTK. Saber cuáles faltan en un proyecto pasa de ~4.700 tokens a ~480. Sin verbo para finalizar, a propósito.
- Identificador estable por tarea con marca de bloque de Obsidian, auditado y corregido: ids ambiguos rechazados en vez de escribir en la tarea equivocada, marcas de seis caracteres, y el foco del board sigue a la carta cuando la tarea cambia de id al escribir.
- 110 pruebas de vault.py y de la CLI con unittest, sin dependencias, cada una contra su propio vault de mentira. Salieron tres fallos silenciosos: tags con guion mal delimitados, saltos de línea reescritos en toda la nota, y asignar sin nombre reventando.
- Hallazgos 6 y 7: estado.json lleva esquema 1, y lo que Cotejo no puede leer o escribir sale como avisos en el resumen, en una banda ámbar en las dos ventanas y en el tooltip de la barra. 128 pruebas.
- Cierre del día: seis de los ocho hallazgos de la revisión AX hechos, 128 pruebas, cinco commits. Queda la evidencia en el board (mitad del 5, que desbloquea bloquear) y la capa Fuente (3). El punto de retome está en Siguiente paso.

### 2026-09-16
- Primera versión: lista por proyecto, marcar con Deshacer, abrir la nota en Obsidian con clic, recarga automática al editar el vault.
- Botón por proyecto para mostrar u ocultar sus tareas, con estado recordado y botón para ocultar todos.
- Diseño con una marca anterior, ícono flotante arriba a la derecha de la pantalla externa, ventana flotante y arranque con la sesión.


## ⏭️ Dónde retomar (versiones anteriores)

> [!tip] Dónde retomar — 2026-10-02
> **Terminar las tareas de la v1.1** (las que empiezan por `v1.1 ·`, en el orden de [[cotejo-planning-v1-1|Cotejo - Planning v1.1]], más `cotejo-enigzw`). Ya usan `.cotejo/tareas.md` e `importar plan`. **Cuando la 1.1 esté cerrada**, revisar [[cotejo-planning-v1-2|Cotejo - Planning v1.2]] con lo que haya salido y solo entonces escribir su plan de implementación y sus tareas. Lo de abajo es el punto de retomar anterior y queda como historia.

> [!tip] Dónde retomar — 2026-09-24
> **`master` está en `cd2d839` y es lo instalado.** Lleva la eliminación de CotejoList (`3fc52a2`), las fuentes externas con Notion ([[cotejo-planning-de-fuentes-externas|Cotejo - Planning de fuentes externas]]) y el cambio de fuente en caliente. El comando público es `cotejo` (`tareas-obsidian` sigue siendo el mismo). La config vive en `~/.config/cotejo/config.json`; la vieja quedó como `config.json.migrado`. Fuente activa: **Obsidian**; Notion está registrada con la base de prueba «Cotejo — prueba».

**Lo primero, antes de tocar nada:**

```sh
cd ~/Documentos/ClaudeCode/cotejo-diseno
git log --oneline master | head -3   # cd2d839 arriba
python3 -m unittest discover pruebas # 418, en verde
cotejo doctor                          # fuente activa y si conecta
```

Si algo de eso no cuadra, alguien tocó el repo: averígualo antes de seguir. Resuelto el 2026-09-26: los cambios sin commitear del catálogo de modelos (rama `enrutador-mide-su-reparto`) ya están en `master` (`2761d0b`, `5e258e9`), y el árbol, hoy en `~/Documentos/ClaudeCode/SecondBrain/01-Proyectos/Cotejo/cotejo`, está limpio.

**Los ocho hallazgos de la [[revision-ax-de-cotejo|Revisión AX de Cotejo]] están hechos.** El ciclo del agente está completo (`tomar` → `entregar --evidencia` o `bloquear --motivo` → comprobar o devolver con motivo) y el contrato ya no es el Markdown: es la CLI, con Obsidian detrás de una capa `Fuente` que se cambia escribiendo cuatro métodos.

**Por dónde continuar, en este orden:**

1. **Usarlo unos días sin añadirle nada.** Es lo que pide Apps para agentes antes de programar el MCP, y ahora sí hay ciclo completo que ensayar. Las dos tareas de observación que ya están anotadas (si la columna Pendiente satura con 60+, si hace falta filtrar por agente) se contestan usándolo, no pensándolo. Lo que salga de ahí decide lo que viene después; empezar a construir antes es adivinar.
2. **El MCP, cuando el uso lo pida.** La revisión AX ya lo dejó dicho: si los verbos están bien puestos, el servidor es un envoltorio de una tarde. Los verbos llevan una semana de uso y 172 pruebas encima.
3. ~~Un segundo cerebro de verdad~~ **hecho el 2026-09-24: Notion**, por un adaptador externo (`cotejo-notion`) probado contra una base real. Otra app es escribir su adaptador copiando `extras/plantilla/cotejo_plantilla.py`; cambiar de fuente es `cotejo fuentes usar <nombre>` (skill `cotejo-fuentes`).
4. ~~El medidor de ahorro~~ **hecho el 2026-09-18** y comprobado. Mide 10,4× sobre este vault y sale al pie de la lateral de CotejoBoard. Queda un defecto anotado como tarea: infla la razón cuando se filtra por `--proyecto`, porque `escanear` lee el vault entero aunque la respuesta traiga un solo proyecto.
5. **Las dos opcionales** de siempre: la fecha al marcar una tarea, y leer también `00-Inbox` y `06-Diario`. Ninguna es urgente; están asignadas.

**El medidor de ahorro, si se hace:** la gracia es que las dos mitades del número se pueden **medir**, no estimar. Lo que costó de verdad es el tamaño de lo que la CLI devolvió en cada llamada; lo que habría costado es el tamaño de las notas que la fuente leyó para contestar, que ya las leyó y las tiene en la mano. Lo único que no es medible es el supuesto de en medio —que sin Cotejo el agente habría leído esas notas enteras— y por eso hay que decirlo en voz alta allí donde salga el número, no esconderlo detrás de un total redondo.

Tres condiciones para que no se convierta en una medalla:

- **Fuera de la barra.** Es la misma decisión del 2026-09-17: un número permanente es FOMO, y el sitio del acento es lo que exige una acción. Esto se consulta cuando se quiere (`tareas-obsidian ahorro`, o una línea en el board), no se anuncia.
- **En su propio archivo de estado**, con totales acumulados y reemplazo atómico, no en `bitacora.jsonl`: la bitácora es historial de lo que se hizo y se lee con `tail`, y el resumen de la barra la consulta cada pocos minutos. Una línea por lectura la llenaría de ruido y encarecería justo el camino que el medidor dice abaratar.
- **Contar no puede costar.** Si medir el ahorro hace más lenta o más cara una lectura, el medidor se come lo que mide. Conviene una prueba que lo fije, como la que vigila que no aparezca un verbo para finalizar.

**Los temas, si se hacen:** hoy la paleta está escrita a mano en el CSS de `app.py` y el modo
oscuro va forzado (`FORCE_DARK`). Un tema es ese puñado de tokens —Negro, Grafito, Borde,
Plata, Señal y el Señal suave— sacado a un archivo; todo lo demás del CSS se queda donde está.

- **En la interfaz solo se elige.** El botón va a la izquierda de recargar, y solo en
  CotejoBoard: CotejoList es una lista angosta y un botón más la convierte en una barra de
  herramientas. El modal enseña los temas que haya y cuál está puesto, y nada más. Ni editar
  ni crear: un editor de colores dentro de la app es otra app, y esta existe para no distraer.
- **Crear es de un agente, por CLI.** Un verbo los lista y otro escribe uno nuevo: nombre, los
  tokens y nada más. Es el mismo reparto que en todo lo demás —el agente propone, la persona
  elige— y por la misma razón: lo que se hizo sin mirar hay que poder revisarlo mirando.
- **Un tema tiene que poder demostrarse sin abrir la app.** Que el texto se lea sobre su fondo
  es comprobable: contraste AA, par por par. Si el verbo que crea un tema lo comprueba y lo
  dice, un agente puede hacer diez sin que ninguno salga ilegible; si no, la única manera de
  saberlo es abrir la ventana y mirar, que es justo lo que el AX evita. El manual de la marca anterior ya
  tiene el precedente: Plata pasa AA sobre oscuro y Acero no.
- **El tema elegido es estado de interfaz**, no del vault: va con `board.json` y
  `expandidos.json`, por la misma razón que ellos —el board se puede rehacer entero sin
  renegociar nada con el agente.
- **El claro es lo que de verdad cuesta.** Los tokens salen baratos; lo que no es que el CSS da
  por hecho el oscuro allí donde hay `rgba(255, 255, 255, …)` y en `FORCE_DARK`. Ese es el
  trabajo de verdad, y conviene medirlo antes de prometer un tema claro.
