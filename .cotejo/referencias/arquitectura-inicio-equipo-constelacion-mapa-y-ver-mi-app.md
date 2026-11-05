---
id: ref-ss7l
temas: [arquitectura, board, inicio]
resumen: pendiente
---
# Arquitectura · Inicio, equipo, constelación, mapa y Ver mi app

Movido del CLAUDE.md del repo el 2026-11-04 (cotejo-d9cbol), sin cambiar el texto. Es el detalle por módulo de arq-lfay (un proyecto tiene una sola arquitectura; volver a anotarla la reescribe).

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
