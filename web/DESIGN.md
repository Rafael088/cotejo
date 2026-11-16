---
name: Cotejo (web)
description: La página pública de Cotejo, dibujada con el mismo material que CotejoBoard.
colors:
  fondo: "#101114"
  columna: "#15161a"
  superficie: "#2a2c33"
  superficie-alta: "#31343c"
  borde: "#3a3d45"
  borde-hondo: "#1e2025"
  borde-chip: "#474a53"
  columna-board: "#18191e"
  texto: "#ffffff"
  texto-chip: "#d6d9df"
  tenue: "#a8acb6"
  tenue-hondo: "#878b95"
  senal: "#16c98d"
  senal-claro: "#3fdcaa"
  sobre-senal: "#101114"
  ambar: "#f0c987"
  velo: "rgba(255, 255, 255, 0.05)"
  velo-fuerte: "rgba(255, 255, 255, 0.08)"
typography:
  display:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(42px, 7vw, 88px)"
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  cifra:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(80px, 13vw, 168px)"
    fontWeight: 600
    lineHeight: 0.9
    letterSpacing: "-0.05em"
    fontFeature: "tnum"
  headline:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(32px, 4.6vw, 56px)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  title:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(21px, 2.2vw, 26px)"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  body:
    fontFamily: "'Inter Variable', 'Inter', system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.6
  body-lead:
    fontFamily: "'Inter Variable', 'Inter', system-ui, sans-serif"
    fontSize: "clamp(17px, 1.7vw, 20px)"
    fontWeight: 400
    lineHeight: 1.55
  mono:
    fontFamily: "'IBM Plex Mono', ui-monospace, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "'IBM Plex Mono', ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.06em"
rounded:
  chip: "6px"
  control: "8px"
  carta: "10px"
  boton: "12px"
  panel: "14px"
  bloque: "16px"
  pastilla: "999px"
spacing:
  margen: "clamp(16px, 4vw, 40px)"
  hueco-seccion: "clamp(96px, 14vw, 184px)"
  ancho: "1180px"
  hueco-columnas: "10px"
  hueco-paneles: "16px"
components:
  mini-senal:
    backgroundColor: "{colors.senal}"
    textColor: "{colors.sobre-senal}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  mini:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  boton-claro:
    backgroundColor: "{colors.texto}"
    textColor: "{colors.fondo}"
    rounded: "{rounded.boton}"
    padding: "0 20px"
    height: "46px"
  boton-claro-hover:
    backgroundColor: "{colors.texto-chip}"
  comando:
    backgroundColor: "{colors.columna}"
    textColor: "{colors.texto}"
    typography: "{typography.mono}"
    rounded: "{rounded.boton}"
    padding: "6px 6px 6px 16px"
  comando-boton:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.control}"
    height: "40px"
  comando-boton-copiado:
    backgroundColor: "{colors.senal}"
    textColor: "{colors.sobre-senal}"
  pestanas:
    backgroundColor: "{colors.columna}"
    rounded: "{rounded.carta}"
    padding: "3px"
  pestana-activa:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.control}"
    padding: "7px 14px"
  carta:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.carta}"
    padding: "12px"
  columna:
    backgroundColor: "{colors.columna}"
    rounded: "{rounded.panel}"
    padding: "12px 10px 10px"
  panel:
    backgroundColor: "{colors.columna}"
    rounded: "{rounded.panel}"
    padding: "20px"
  chip:
    backgroundColor: "{colors.velo}"
    textColor: "{colors.tenue}"
    rounded: "{rounded.chip}"
    padding: "1px 6px"
---

# Design System: Cotejo (web)

## Overview

**Creative North Star: "El board, tal cual"**

La página no inventa un mundo de marketing: usa el material de CotejoBoard sin traducirlo. Fondo casi negro, columnas un punto más claras, cartas grises con borde de 1px y radio de 10px, texto blanco y un solo acento que significa una sola cosa. Lo que la página enseña (la demo donde el agente entrega y el visitante pone el check, la nota entera contra la respuesta de la CLI, la salida real de cada verbo) se dibuja con esas mismas piezas, en HTML, a escala real. Quien instala Cotejo debería reconocer la ventana que va a abrir.

La densidad es de herramienta, no de folleto: paneles oscuros que contienen terminales, JSON y cifras en mono, separados por huecos grandes entre secciones. La persuasión viene de la cifra medida y del material que la produce, no de decoración. La paleta, el reparto del verde y las tres familias tipográficas son compromisos de marca; la web los hereda del tema Oscuro (`../data/temas/oscuro.json`) con una sola desviación deliberada (ver Colors).

El movimiento es el del board: muelles cortos y una curva de salida rápida (`cubic-bezier(0.16, 1, 0.3, 1)`). Todo respeta `prefers-reduced-motion`: `MotionConfig reducedMotion="user"` en la raíz, y las animaciones CSS (cursor de la terminal, pulso del botón Aprobar, la nota que corre en /tokens, la barra de progreso de las escenas) se apagan con la media query. La demo y las escenas de /comofunciona no avanzan solas con movimiento reducido.

**Key Characteristics:**
- Neutros del negro al blanco y un único acento, Verde Hecho, con significado fijo (check, comprobación, «Copiado»).
- Superficies planas en tres escalones (fondo, columna, superficie); la profundidad es tonal.
- Sora para titulares, Inter para texto, IBM Plex Mono para comandos, cifras y JSON.
- Las piezas son las del board: columnas, cartas, chips, comandos con botón de copiar, terminal.
- Iconos dibujados a mano en SVG, trazo 1,75 sobre caja de 24.
- Cuatro páginas estáticas (rutas reales, no hash): /, /comofunciona, /primerospasos, /tokens. Navegación sin JavaScript.

## Colors

Neutros fríos del negro al blanco, heredados nombre por nombre del tema Oscuro de CotejoBoard, con un verde que significa «espera que lo compruebes / hecho» y un ámbar que significa «devuelta / bloqueada».

### Primary
- **Verde Hecho** (`senal`): el check del logo, lo que espera comprobación (nombre de la columna «Para comprobar», su conteo, el borde de la carta entregada), el estado «Copiado» del comando y de las frases, el botón «Aprobar» de la demo y de /comofunciona, el anillo de foco (`outline 2px` con `offset 3px`), la selección de texto y el cursor. Nada más.
- **Sobre Verde** (`sobre-senal`): texto sobre cualquier relleno verde; es el mismo valor que el fondo.

### Secondary
- **Ámbar Devuelta** (`ambar`): exclusivamente para una tarea devuelta o bloqueada (la etiqueta de motivo y el borde de la carta devuelta). Nunca decorativo, nunca aviso genérico.

### Neutral
- **Fondo Noche** (`fondo`): lienzo de la página, fondo del board y relleno de nodos vacíos.
- **Columna** (`columna`): la ventana de la demo, paneles, consola de /comofunciona, bloques de instalación, comandos, frases y pestañas.
- **Columna Board** (`columna-board`): las cuatro columnas del tablero dentro de la demo, un punto más claras que la ventana que las contiene.
- **Superficie** (`superficie`): cartas, botón de copiar en reposo, pestaña activa, globos y resumen de entrega en /comofunciona, `code` en línea.
- **Superficie Alta** (`superficie-alta`): hover de superficies (botón de copiar).
- **Borde** (`borde`): el borde de 1px de cartas, comandos, frases, la ventana de la demo y los botones secundarios.
- **Borde Hondo** (`borde-hondo`): bordes de paneles sobre fondo y divisorias internas (cabeceras y pies de panel, separador del pie).
- **Borde Chip** (`borde-chip`): chip con borde (modelo de una carta, agentes compatibles), hover de comando y pulgar de la barra de scroll.
- **Blanco** (`texto`): titulares, texto fuerte, comandos, la cifra 19,7× y la barra de la CLI.
- **Plata** (`texto-chip`): párrafos, bajada del hero, valores del JSON.
- **Tenue** (`tenue`): texto secundario, navegación en reposo, «Tú compruebas.» en la firma del pie, etiquetas.
- **Tenue Hondo** (`tenue-hondo`): prompts de terminal, la nota cruda que corre en /tokens y su barra, notas al pie, texto legal. Es la única desviación respecto al board (allí `#6A6E78`): en la web lleva texto de cuerpo y se subió para pasar 4,5:1 sobre `fondo` y `columna`.
- **Velo / Velo Fuerte** (`velo`, `velo-fuerte`): rellenos translúcidos de chips, evidencias y hover de navegación y de botones secundarios.
- **Verde Claro** (`senal-claro`): solo el hover del botón verde.

### Named Rules
**The Un Solo Verde Rule.** El verde significa «espera que lo compruebes / hecho / foco». Si algo es verde y no es eso, está mal. El verde nunca es el único portador de significado: va con texto («Copiado», «Para comprobar») o con el check.

**The Ahorro en Plata Rule.** El ahorro de tokens (la escala de la portada y todo /tokens) va en blanco y plata, nunca en verde: la barra de la CLI es blanca y la de la nota `tenue-hondo`. Ahorrar no es «hecho».

**The Ámbar Es Devuelta Rule.** El ámbar solo aparece en una tarea devuelta o bloqueada.

**The Tema Manda Rule.** Un color nuevo sale del tema Oscuro de CotejoBoard con su nombre; una desviación se declara en un comentario junto al token y dice por qué.

## Typography

**Display Font:** Sora (variable, con system-ui)
**Body Font:** Inter (variable, con system-ui)
**Label/Mono Font:** IBM Plex Mono 400 y 500 (con ui-monospace)

**Character:** Sora geométrica y apretada en los titulares, Inter neutra para leer, Plex Mono para todo lo que una máquina escribe o mide. Las tres son las del board y del logo, servidas desde `@fontsource`.

### Hierarchy
- **Display** (600, clamp 42–88px en el hero de /; clamp 40–80px en el H1 de las páginas interiores; -0.04em): solo el H1.
- **Cifra** (600, clamp 80–168px, 0.9, -0.05em, cifras tabulares): la razón medida (19,7×) en /tokens, en Sora y en blanco.
- **Headline** (600, clamp 32–56px, 1.08, -0.03em, `text-wrap: balance`): un H2 por sección.
- **Title** (600, clamp 21–26px, 1.25): H3 dentro de una sección; Sora a 13–22px también nombra columnas, el board y frases de cierre.
- **Body** (400, 17px / 16px en móvil, 1.6): párrafos en `texto-chip`, máximo 62ch; la bajada del hero sube a clamp 17–20px con 54ch.
- **Mono** (400–500, 11,5–15,5px, cifras tabulares): comandos, JSON, contadores, nombres de fila de la escala, sello de entrega.
- **Label** (500, 10–11px, 0,06–0,1em, mayúsculas): solo dentro del cromo del board y la etiqueta de motivo de una devuelta.

### Named Rules
**The Mono Es Máquina Rule.** Lo que escribe o devuelve la CLI, y toda cifra medida, va en IBM Plex Mono con `tabular-nums`. El texto que habla con la persona va en Inter.

**The Mayúsculas Del Board Rule.** Las etiquetas mono en mayúsculas espaciadas son cromo del board, no titulares de sección: viven dentro de una réplica del board o de una carta.

## Layout

Una columna central de `ancho` (1180px) con `margen` lateral fluido; cada sección abre con `hueco-seccion` arriba. La portada (`src/portada.css`) es la única página centrada: hero con H1 en dos tonos (blanco y `tenue`), una línea de bajada, la fila de acción (comando con Copiar en blanco + «Leer los docs») y, debajo, la ventana de CotejoBoard a todo el ancho de la columna, flotando sobre un halo de luz blanca. Sigue la franja de agentes (nombres en Sora, sin logos), la rejilla de funciones en 12 columnas (7/5 · 5/7 · 12) y el cierre.

Páginas: `/` (hero + franja de agentes + rejilla de funciones + cierre), y las interiores `/comofunciona`, `/primerospasos`, `/tokens`, que quedan como estaban hasta que `/docs` las reemplace (la cabecera solo enlaza Docs e Instalar; el pie las conserva). Puntos de corte de la portada: 1100px (la franja de agentes se apila), 1020px (la ventana pierde su lateral de proyectos), 940px (la rejilla pasa a una columna), 860px (el tablero del hero se desplaza de lado y sigue solo a la acción), 640px (la fila de acción se apila) y 520px (la cabecera esconde la versión).

## Elevation & Depth

Plano por defecto: la profundidad se lee por tono (fondo → columna → superficie → superficie alta) y por bordes de 1px. Hay una sola sombra, en lo único que flota de verdad sobre el lienzo, negra, difusa y sin desplazamiento lateral.

### Shadow Vocabulary
- **Ventana del hero** (`box-shadow: 0 40px 120px rgba(0, 0, 0, 0.55), 0 14px 36px rgba(0, 0, 0, 0.35)`): CotejoBoard en la portada, con un filo de luz de 1px en el borde de arriba y un halo radial blanco detrás (nunca verde). La ficha que se arrastra y los paneles del maestro llevan su propia sombra negra con desplazamiento.
- **Pulso de Aprobar** (`0 0 0 5px` en verde al 18%, animado): el botón Aprobar de una carta que espera tu turno en la demo. No es profundidad sino llamada; se apaga con movimiento reducido.

### Named Rules
**The Tonal Antes Que Sombra Rule.** Un panel nuevo se separa con un escalón de tono y un borde de 1px; la sombra queda para lo que se mueve o flota sobre todo lo demás.

## Shapes

Esquinas suaves y escalonadas por tamaño: 6px en chips, evidencias y `code` en línea; 8px en controles internos (botón de copiar, pestaña); 10px en cartas (el radio del board); 12px en botones, comandos y columnas del board; 14px en pasos, frases y el selector; 16px en paneles, la ventana de la demo y la consola. Pastilla completa (999px) para la versión de la cabecera y las etiquetas de agente. Bordes siempre de 1px.

## Componentes

### Hero
Centrado. H1 «El tablero de control para tu vibe coding.» en clamp 38–84px (la segunda mitad en `tenue`), bajada de una línea, `Instalar` y el producto. Fondo: una trama de puntos `borde` que se apaga con una máscara radial. La entrada es CSS (`.aparece`), nunca `opacity:0` en línea.

### Producto del hero (video o BoardVivo)
`VIDEO_HERO` en `src/config.js`: con un video, la ventana es un `<video autoplay muted loop playsinline>` con póster (con movimiento reducido se queda en el póster, con controles). Mientras sea `null`, `components/BoardVivo.jsx` recrea CotejoBoard: cabecera con el estado en mono, lateral de proyectos, las cuatro columnas y la barra del maestro en el pie. Su guion: se escribe un pedido al maestro, aparecen dos fichas en Pendiente, un cursor las arrastra a Haciéndola, los agentes muestran lo que hacen y las entregas quedan en Para comprobar. Nadie aprueba en el hero.

### Escenas vivas (`components/vivo.jsx`)
El motor común: `usePasos` (un guion por pasos que solo corre en pantalla; el prerender, el primer render y `prefers-reduced-motion` enseñan una «foto» que se lee sola), `useCursor`/`Cursor` (el puntero que arrastra, medido por offsets), `Ficha` y `Columna` (las piezas del board; las fichas cambian de columna por `layoutId`) y `Tecleada`. Estados de ficha: normal, viva (borde `borde-chip`, con lo que el agente hace en mono), cola (borde discontinuo), entregada (borde verde), devuelta (borde ámbar, con motivo), hecha (sin relleno, con check).

### Franja de agentes
«Funciona con tu agente.» a la izquierda con «O con cualquier agente que hable MCP.», y los nombres (`AGENTES` en config.js) en Sora 600 `tenue`, entre dos divisorias `borde-hondo`. Sin logos ajenos.

### Rejilla de funciones
Cinco `article` sobre `columna` con borde `borde-hondo` y 16px de radio: arriba la escena (484px, sobre `fondo`) y abajo un H3 y una línea. Cada escena es una pieza del board en bucle: `EscenaAgentes` (Haciéndola de cerca, dos agentes y una tarea en cola), `EscenaMaestro` (el panel de la conversación con el botón Repartir y el aviso ámbar de la aprobación deshecha), `EscenaEnrutador` (cada pendiente recibe su modelo; lo tuyo va en un chip blanco lleno; debajo, 65 puntos con 24 en blanco), `EscenaComprobar` (entrega con evidencia y captura, Rechazar con motivo, reentrega y Aprobar) y `EscenaTokens` (la nota entera pasando contra el JSON de la CLI y las barras a escala, en blanco y plata). Las escenas de tablero enseñan la columna central entera y las vecinas cortadas con una máscara lateral.

### Instalar (portada)
`components/Instalar.jsx`: el comando grande con su botón Copiar en blanco (`comando--principal`; verde al copiar), «Leer los docs» como botón con borde, pestañas Linux/Windows y la nota «Gratis · Linux y Windows 10/11 · beta». `InstalarRapido` queda para las páginas interiores.

### Cierre de la portada
Panel `columna` de 24px de radio con un eco del halo, H2 «Instálalo y arrastra tu primera tarea.» e `Instalar`.

### ComoFunciona
Selector de dos pestañas (tablist con flechas): No programo (CfHistoria) y Programo (CfCiclo). Abre la que pida `?publico=no|si` y lo reescribe al cambiar.

### CfHistoria
Cuatro pasos (Pides, Se planea, Te entrega, Decides) con su escena: globos de diálogo, cartas, el resumen de una entrega con borde verde y, en la última, Aprobar o Devolver. Avanzan solos con una barra de progreso (animación CSS) hasta que se toca un paso; no avanzan con movimiento reducido ni con su panel oculto.

### CfCiclo
Seis verbos de la CLI (init, plan, despachar, entregar, comprobar, release) con su salida real abreviada (`src/comofunciona.js`, sacada de la CLI sobre un repo de prueba: claves y valores de verdad), el árbol real de `.cotejo/` y «Nada se cierra sin ti».

### PrimerosPasos
Dos secciones: El primer día (instalar, «empiezo un proyecto», las cinco preguntas, aceptar decisiones) y Cada día (frases copiables: `Frase`, `BotonCopiar` y el hook `useCopiar`, el mismo que usa el comando). Cada fila es una rejilla de `dia__cuando` (cuando) y `dia__cuerpo` (descripción + componente).

### Tokens
La nota entera corriendo contra la respuesta de `cotejo tareas` (claves reales), la escala a proporción, la cifra 19,7× con sus datos y su supuesto (y `cotejo ahorro` para medirlo uno mismo), y el flujo Obsidian/Notion → importar → `.cotejo/` → contexto, que se apila en móvil. Todas las cifras salen de `src/config.js`.

### Cierre
Panel con H2 e InstalarRapido, al final de /, /comofunciona y /tokens. Props: `id`, `titulo`, `nota`, `pie`.

### Buttons
Directos y compactos, de herramienta.
- **Shape:** esquinas de 12px, alto mínimo 46px, padding horizontal 20px, Inter 600 a 15px, icono de 16–18px con 10px de separación.
- **Mini verde (`mini-senal`):** solo «Aprobar», en la demo y en /comofunciona: Inter 600 a 12,5px, esquinas de 8px, hover a `senal-claro`.
- **Mini (`mini`):** transparente con borde `borde`, hover con `velo-fuerte`: «Devolver», y «Otra vez» en la barra de la demo.
- **Claro (`boton-claro`):** blanco sobre `fondo`, hover a `texto-chip`. La acción principal fuera del ciclo (donar, en el pie).
- **Active:** `translateY(1px) scale(0.99)`. Transiciones de 0,2s con la curva de salida.

### Comando (firma)
La acción principal de la página es copiar un comando.
- **Estilo:** fila en `columna` (o `fondo` cuando va sobre un bloque `columna`) con borde `borde` y esquinas de 12px (14px en la variante grande); prompt (`$` o `PS>`) en `tenue-hondo`, comando en blanco, mono a 14px (15,5px grande), con scroll horizontal si no cabe.
- **Botón copiar:** `superficie` con esquinas de 8px, 40px de alto (44px grande); hover a `superficie-alta`. Al copiar, el botón y el borde se vuelven verdes y la cara cambia a check + «Copiado» durante 2,2s, anunciado en una región `aria-live`.

### Pestañas
Segmentado sobre `columna` con borde hondo y padding de 3px; la activa lleva una píldora `superficie` que se desliza entre opciones con un muelle corto (`layoutId`, bounce 0,15).

### Chips
- **Chip de carta:** mono 10,5px en `tenue` sobre `velo`, esquinas de 6px; variante con borde `borde-chip` y texto `texto-chip` (el modelo de la carta).
- **Etiqueta de agente:** pastilla mono con borde `borde-chip` (agentes compatibles en la portada, rasgos en /comofunciona).

### Cards / Containers
- **Carta:** `superficie`, borde 1px `borde`, 10px de radio, padding 12px; la que espera comprobación cambia el borde a verde, la devuelta a ámbar, la hecha baja al 55% de opacidad.
- **Columna:** `columna-board`, sin borde, 12px de radio; nombre en Sora 600; la columna «Para comprobar» nombra en verde.
- **Panel:** `columna` con borde `borde-hondo`, 14–16px de radio, padding 20px (clamp 20–32px en bloques grandes); cabeceras y pies separados por divisorias `borde-hondo`.
- **Evidencia:** caja mono 11–11,5px en `tenue` sobre `velo`, radio 6px, debajo del texto de la carta.

### Navigation
Cabecera fija arriba (`position: sticky`, 64px, fondo translúcido con desenfoque y divisoria `borde-hondo`): logo y versión en una pastilla mono con borde; un solo enlace, «Docs» (a `/docs`), en Inter 500 a 15px, `tenue` con hover a blanco; «Instalar» en blanco lleva al bloque de instalación de la portada. Sin menú: cabe entera en un teléfono (bajo 520px se esconde la versión). Enlace «Saltar al contenido» visible al foco.

### Pie
Firma con el logo y «Tus agentes entregan. Tú compruebas.» (la segunda frase en `tenue`): la frase de marca vive aquí y en la og:image, ya no en el titular. Enlaces a las cuatro páginas, descargas, licencia y contacto; donar con Mercado Pago; línea legal con la versión.

### El board en marcha (firma)
La portada se gana con el producto trabajando: el visitante ve cómo se piden tareas al maestro, cómo se arrastran a Haciéndola y cómo arrancan los agentes; aprobar sigue siendo de quien mira. Ver «Producto del hero» arriba.

## Do's and Don'ts

### Do:
- **Do** sacar cada color del tema Oscuro de CotejoBoard con su nombre, y declarar junto al token cualquier desviación y su motivo (como `tenue-hondo`).
- **Do** reservar `senal` para el check, lo que espera comprobación, lo hecho, el «Copiado» y el foco, y acompañarlo siempre de texto o del check.
- **Do** dibujar las pruebas con piezas del board (columna, carta, chip, evidencia, comando) en HTML, no con capturas.
- **Do** poner comandos, JSON y cifras en IBM Plex Mono con `tabular-nums`.
- **Do** usar los muelles cortos y la curva `cubic-bezier(0.16, 1, 0.3, 1)`, y dejar todo estático con `prefers-reduced-motion`.
- **Do** dibujar iconos en SVG con trazo 1,75 sobre caja de 24, `stroke-linecap: round`.

### Don't:
- **Don't** pintar de verde el ahorro de tokens, una cifra, un enlace o un botón que no sea Aprobar.
- **Don't** usar ámbar fuera de una tarea devuelta o bloqueada.
- **Don't** separar la C de «otejo», rotar, sombrear o degradar el logo, ni poner el check en otro color que `senal`.
- **Don't** poner etiquetas mono en mayúsculas como titulillo encima de un H2; esas etiquetas son cromo del board.
- **Don't** usar texto de cuerpo en un gris más oscuro que `tenue-hondo` (#878B95).
- **Don't** construir tarjetas de función con un icono y un párrafo: cada una lleva su escena de UI viva hecha con piezas del board. Sin testimonios ni logos ajenos.
- **Don't** teñir de verde ni de color el halo del hero: es luz blanca.
