---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Página web de Cotejo (portada)

Scope: la portada `/` de cotejo.dev (`web/`, React + Vite, prerender a estática). Modo: **Persuade**.
Audiencia: desarrolladores que ya trabajan con agentes de terminal (Claude Code, Codex, OpenCode, Gemini CLI, Antigravity CLI) y prueban la beta 1.3. Acción: copiar el comando de instalación; secundaria, abrir `/docs`. Prueba: el board en marcha (video real cuando exista; mientras, recreación animada) y cinco funciones demostradas con UI viva; cifras medidas (480 contra 4.700 tokens, 19,7× con su supuesto; 24 de 65 tareas eran de una persona). Restricciones: voz de marca, solo lo que trae la 1.3.1, sin testimonios, sin logos ajenos, el dot no sale.
Memorable: arrastras una ficha a Haciéndola y un agente arranca delante de ti.
Lo de «cómo se usa» vive en `/docs` (lo construye otra tarea); /comofunciona, /primerospasos y /tokens siguen publicadas hasta entonces, enlazadas desde el pie.
Pendiente del dueño: grabar el video del hero (`VIDEO_HERO` en `src/config.js`).

## Direction contract

THESIS: La portada no explica Cotejo: lo enseña trabajando. Cada idea es una pieza del board en movimiento con un titular corto y una línea; el texto largo se va a /docs. Rechaza la rejilla de iconos con párrafos y los degradados de SaaS: las tarjetas llevan UI viva hecha con el material real del board.

OWN-WORLD: El mundo de CotejoBoard (tema Oscuro) tal cual: fondo #101114, columnas #15161A/#18191E, cartas #2A2C33 con borde 1px y radio 10px, Sora / Inter / IBM Plex Mono. Verde Hecho solo en lo que espera comprobación, lo hecho, «Copiado» y el foco; ámbar solo en lo devuelto; el ahorro, en blanco y plata. El halo del hero es luz blanca, nunca verde.

STORY: Lee el titular, ve el board recibir tareas del maestro, ve cómo se arrastran a Haciéndola y cómo los agentes arrancan en paralelo; copia el comando. Si baja: con qué agentes funciona; cinco funciones (arrastrar, maestro, enrutador, comprobación, tokens), cada una demostrada; cierre con el comando otra vez.

FIRST VIEWPORT: Cabecera mínima (logo, versión, Docs, Instalar). Hero centrado: H1 «El tablero de control para tu vibe coding.» en dos tonos (Sora, clamp 40–84px), una línea de bajada, fila de acción (comando con Copiar en blanco + «Leer los docs») y la nota «Gratis · Linux y Windows 10/11 · beta». Debajo, a todo el ancho de la columna, la ventana de CotejoBoard flotando sobre un halo de luz blanca, asomando por el pliegue y ya en marcha.

FORM: Una página: hero con ventana viva, franja de agentes en texto, rejilla asimétrica 7/5 · 5/7 · 12 de funciones con mini-escenas en bucle, cierre. Estructura fijada por el encargo del dueño (code-led, sin ronda de conceptos; sin seed key). Interacción firma: el cursor que arrastra la ficha y el agente que arranca. Las escenas solo corren en pantalla; con `prefers-reduced-motion` y sin JavaScript queda una foto que se lee entera.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
