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
  texto: "#ffffff"
  texto-chip: "#d6d9df"
  tenue: "#a8acb6"
  tenue-hondo: "#878b95"
  senal: "#16c98d"
  sobre-senal: "#101114"
  ambar: "#f0c987"
  velo: "rgba(255, 255, 255, 0.05)"
  velo-fuerte: "rgba(255, 255, 255, 0.08)"
typography:
  display:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(38px, 6.4vw, 78px)"
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.04em"
  cifra:
    fontFamily: "'Sora Variable', 'Sora', system-ui, sans-serif"
    fontSize: "clamp(64px, 10vw, 136px)"
    fontWeight: 600
    lineHeight: 1
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
  boton-senal:
    backgroundColor: "{colors.senal}"
    textColor: "{colors.sobre-senal}"
    rounded: "{rounded.boton}"
    padding: "0 20px"
    height: "46px"
  boton-senal-disabled:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.tenue}"
  boton-fantasma:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.boton}"
    padding: "0 20px"
    height: "46px"
  boton-fantasma-hover:
    backgroundColor: "{colors.velo-fuerte}"
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
  filtro:
    backgroundColor: "transparent"
    textColor: "{colors.tenue}"
    rounded: "{rounded.pastilla}"
    padding: "8px 14px"
  filtro-activo:
    backgroundColor: "{colors.texto}"
    textColor: "{colors.fondo}"
---

# Design System: Cotejo (web)

## Overview

**Creative North Star: "El board, tal cual"**

La página no inventa un mundo de marketing: usa el material de CotejoBoard sin traducirlo. Fondo casi negro, columnas un punto más claras, cartas grises con borde de 1px y radio de 10px, texto blanco y un solo acento que significa una sola cosa. Lo que la página enseña (la nota entera contra la respuesta de la CLI, el board vivo detrás del titular, el ciclo tomar-entregar-comprobar) se dibuja con esas mismas piezas, en HTML, a escala real. Quien instala Cotejo debería reconocer la ventana que va a abrir.

La densidad es de herramienta, no de folleto: paneles oscuros que contienen terminales, JSON y cifras en mono, separados por huecos grandes entre secciones. La persuasión viene de la cifra medida y del material que la produce, no de decoración. La paleta, el reparto del verde y las tres familias tipográficas son compromisos de marca; la web los hereda del tema Oscuro (`../data/temas/oscuro.json`) con una sola desviación deliberada (ver Colors).

El movimiento es el del board: muelles cortos y una curva de salida rápida (`cubic-bezier(0.16, 1, 0.3, 1)`). Todo respeta `prefers-reduced-motion`: `MotionConfig reducedMotion="user"` en la raíz, y las animaciones CSS (deriva del board de fondo, flecha que baja) se apagan con la media query.

**Key Characteristics:**
- Neutros del negro al blanco y un único acento, Verde Hecho, con significado fijo.
- Superficies planas en tres escalones (fondo, columna, superficie); la profundidad es tonal.
- Sora para titulares, Inter para texto, IBM Plex Mono para comandos, cifras y JSON.
- Las piezas son las del board: columnas, cartas, chips, comandos con botón de copiar.
- Iconos dibujados a mano en SVG, trazo 1,75 sobre caja de 24.

## Colors

Neutros fríos del negro al blanco, heredados nombre por nombre del tema Oscuro de CotejoBoard, con un verde que significa «espera que lo compruebes / hecho» y un ámbar que significa «devuelta / bloqueada».

### Primary
- **Verde Hecho** (`senal`): el check del logo, lo que espera comprobación (nombre de la columna «Para comprobar», su conteo, el borde de la carta entregada), el estado «Copiado» del comando, el botón «Marcar como hecha», el anillo de foco (`outline 2px` con `offset 3px`), la selección de texto y el cursor. Nada más.
- **Sobre Verde** (`sobre-senal`): texto sobre cualquier relleno verde; es el mismo valor que el fondo.

### Secondary
- **Ámbar Devuelta** (`ambar`): exclusivamente para una tarea devuelta o bloqueada (la etiqueta de motivo y el borde de la carta devuelta). Nunca decorativo, nunca aviso genérico.

### Neutral
- **Fondo Noche** (`fondo`): lienzo de la página, fondo del board y relleno de nodos vacíos.
- **Columna** (`columna`): columnas del board, paneles del medidor, consola del trato, bloques de instalación, comandos y pestañas.
- **Superficie** (`superficie`): cartas, botón de copiar en reposo, pestaña activa, nodos de la órbita, `code` en línea.
- **Superficie Alta** (`superficie-alta`): hover de superficies (botón de copiar, nodo activo).
- **Borde** (`borde`): el borde de 1px de cartas, comandos, botones fantasma y del aviso beta.
- **Borde Hondo** (`borde-hondo`): bordes de paneles sobre fondo y divisorias internas (cabeceras y pies de panel, separador del pie).
- **Borde Chip** (`borde-chip`): chip con borde, nodo vacío punteado, hover de comando y pulgar de la barra de scroll.
- **Blanco** (`texto`): titulares, texto fuerte, comandos, la cifra del medidor y su barra.
- **Plata** (`texto-chip`): párrafos, bajada del hero, valores del JSON.
- **Tenue** (`tenue`): texto secundario, navegación en reposo, segunda línea del H1, etiquetas.
- **Tenue Hondo** (`tenue-hondo`): prompts de terminal, la nota cruda del medidor, notas al pie, texto legal. Es la única desviación respecto al board (allí `#6A6E78`): en la web lleva texto de cuerpo y se subió para pasar 4,5:1 sobre `fondo` y `columna`.
- **Velo / Velo Fuerte** (`velo`, `velo-fuerte`): rellenos translúcidos de chips, evidencias, hover de navegación y botón fantasma, proyecto activo.

### Named Rules
**The Un Solo Verde Rule.** El verde significa «espera que lo compruebes / hecho / foco». Si algo es verde y no es eso, está mal. El verde nunca es el único portador de significado: va con texto («Copiado», «Para comprobar») o con el check.

**The Medidor en Plata Rule.** El medidor de ahorro va en blanco y plata, nunca en verde: la barra de la CLI es blanca y la de la nota `tenue-hondo`. Ahorrar no es «hecho».

**The Ámbar Es Devuelta Rule.** El ámbar solo aparece en una tarea devuelta o bloqueada.

**The Tema Manda Rule.** Un color nuevo sale del tema Oscuro de CotejoBoard con su nombre; una desviación se declara en un comentario junto al token y dice por qué.

## Typography

**Display Font:** Sora (variable, con system-ui)
**Body Font:** Inter (variable, con system-ui)
**Label/Mono Font:** IBM Plex Mono 400 y 500 (con ui-monospace)

**Character:** Sora geométrica y apretada en los titulares, Inter neutra para leer, Plex Mono para todo lo que una máquina escribe o mide. Las tres son las del board y del logo, servidas desde `@fontsource`.

### Hierarchy
- **Display** (600, clamp 38–78px, 1.02, -0.04em): solo el H1 del hero; la segunda frase en `tenue`.
- **Cifra** (600, clamp 64–136px, 1, -0.05em, cifras tabulares): la razón medida del medidor (19,7×), en Sora y en blanco.
- **Headline** (600, clamp 32–56px, 1.08, -0.03em, `text-wrap: balance`): un H2 por sección.
- **Title** (600, clamp 21–26px, 1.25): H3 dentro de una sección; Sora a 13–22px también nombra columnas, el board y frases de cierre.
- **Body** (400, 17px / 16px en móvil, 1.6): párrafos en `texto-chip`, máximo 62ch; la bajada del hero sube a clamp 17–20px con 54ch.
- **Mono** (400–500, 11,5–15,5px, cifras tabulares): comandos, JSON, contadores, nombres de fila de la escala, sello de entrega.
- **Label** (500, 10–11px, 0,06–0,1em, mayúsculas): solo dentro del cromo del board (rótulo «PROYECTOS», aviso de la cabecera del board) y la etiqueta de motivo de una devuelta.

### Named Rules
**The Mono Es Máquina Rule.** Lo que escribe o devuelve la CLI, y toda cifra medida, va en IBM Plex Mono con `tabular-nums`. El texto que habla con la persona va en Inter.

**The Mayúsculas Del Board Rule.** Las etiquetas mono en mayúsculas espaciadas son cromo del board, no titulares de sección: viven dentro de una réplica del board o de una carta.

## Layout

Una columna central de `ancho` (1180px) con `margen` lateral fluido; cada sección abre con `hueco-seccion` arriba y una cabeza de hasta 760px (H2 + párrafo) separada del contenido por clamp 40–72px. El hero ocupa `100svh` con el contenido centrado (ancho máximo 960px; el bloque de instalación 640px) sobre el board dibujado a 1280×820, inclinado (`rotateX(32deg)`), al 50% de opacidad y enmascarado por un velo radial.

Dentro de las secciones, rejillas de dos columnas desiguales (1,25fr/1fr en el medidor, 1,4fr/1fr en la consola, 1fr/1,5fr en instalar) con 16px entre paneles; las cuatro columnas del board van a 10px, como en la app. Puntos de corte: a 960px todo pasa a una columna y el trato a 2×2; a 720px el trato a una sola columna (solo la actual conserva su hueco), la navegación queda en el CTA, el botón de copiar se reduce a icono de 44px y la órbita pierde su anillo exterior.

## Elevation & Depth

Plano por defecto: la profundidad se lee por tono (fondo → columna → superficie → superficie alta) y por bordes de 1px. Hay sombra solo en tres objetos que flotan de verdad sobre el lienzo, todas negras, difusas y sin desplazamiento lateral.

### Shadow Vocabulary
- **Board de fondo** (`box-shadow: 0 40px 120px rgba(0, 0, 0, 0.55)`): la ventana del board detrás del hero.
- **Carta en movimiento** (`box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35)`): la carta que viaja entre columnas en el trato.
- **Centro de la órbita** (`box-shadow: 0 0 0 10px var(--fondo), 0 24px 60px rgba(0, 0, 0, 0.5)`): el halo de fondo separa la marca de los radios.

### Named Rules
**The Tonal Antes Que Sombra Rule.** Un panel nuevo se separa con un escalón de tono y un borde de 1px; la sombra queda para lo que se mueve o flota sobre todo lo demás.

## Shapes

Esquinas suaves y escalonadas por tamaño: 6px en chips, evidencias y `code` en línea; 8px en controles internos (botón de copiar, pestaña); 10px en cartas (el radio del board); 12px en botones, comandos y columnas del board; 14px en paneles y columnas del trato; 16px en bloques grandes y la ventana del board. Pastilla completa (999px) para filtros y etiquetas de agente; círculos para nodos y anillos de la órbita. Bordes siempre de 1px; el punteado marca lo que todavía no existe (nodo vacío, anillo de agentes, radio vacío).

## Components

### Buttons
Directos y compactos, de herramienta.
- **Shape:** esquinas de 12px, alto mínimo 46px, padding horizontal 20px, Inter 600 a 15px, icono de 16–18px con 10px de separación.
- **Verde (`boton-senal`):** solo para la acción de comprobar («Marcar como hecha»). Hover a un verde más claro; deshabilitado pasa a `superficie` y `tenue`.
- **Fantasma (`boton-fantasma`):** transparente con borde `borde`; hover con `velo-fuerte`. Acciones secundarias («Devolver con motivo», «Otra vez»).
- **Claro (`boton-claro`):** blanco sobre `fondo`, hover a `texto-chip`. La acción principal fuera del ciclo (donar).
- **Active:** `translateY(1px) scale(0.99)`. Transiciones de 0,2s con la curva de salida.

### Comando (firma)
La acción principal de la página es copiar un comando.
- **Estilo:** fila en `columna` (o `fondo` cuando va sobre un bloque `columna`) con borde `borde` y esquinas de 12px (14px en la variante grande); prompt (`$` o `PS>`) en `tenue-hondo`, comando en blanco, mono a 14px (15,5px grande), con scroll horizontal si no cabe.
- **Botón copiar:** `superficie` con esquinas de 8px, 40px de alto (44px grande); hover a `superficie-alta`. Al copiar, el botón y el borde se vuelven verdes y la cara cambia a check + «Copiado» durante 2,2s, anunciado en una región `aria-live`.

### Pestañas
Segmentado sobre `columna` con borde hondo y padding de 3px; la activa lleva una píldora `superficie` que se desliza entre opciones con un muelle corto (`layoutId`, bounce 0,15).

### Chips y filtros
- **Chip de carta:** mono 10,5px en `tenue` sobre `velo`, esquinas de 6px; variante con borde `borde-chip` y texto `texto-chip`.
- **Filtro:** pastilla con borde `borde` y texto `tenue`; seleccionado se invierte a blanco con texto `fondo`.

### Cards / Containers
- **Carta:** `superficie`, borde 1px `borde`, 10px de radio, padding 12px; la que espera comprobación cambia el borde a verde, la devuelta a ámbar, la hecha baja al 55% de opacidad.
- **Columna:** `columna`, sin borde, 12–14px de radio; nombre en Sora 600; la columna «Para comprobar» nombra en verde.
- **Panel:** `columna` con borde `borde-hondo`, 14–16px de radio, padding 20px (clamp 20–32px en bloques grandes); cabeceras y pies separados por divisorias `borde-hondo`.
- **Evidencia:** caja mono 11–11,5px en `tenue` sobre `velo`, radio 6px, debajo del texto de la carta.

### Navigation
Cabecera absoluta sobre el hero (no fija): logo y versión en una pastilla mono con borde; enlaces Inter 500 a 15px en `tenue` con hover a blanco sobre `velo`, radio 9px; el CTA lleva borde `borde` y es lo único que queda en móvil. Enlace «Saltar al contenido» visible al foco.

### Medidor (firma)
La nota real en mono 11,5px `tenue-hondo` corriendo dentro de un panel enmascarado arriba y abajo, contra la respuesta JSON de la CLI en `texto-chip`; debajo, una escala de cuadros de 15px (12px en móvil) en `tenue-hondo` para la nota y en blanco para la CLI, con su supuesto escrito en una nota al pie. Sin verde.

## Do's and Don'ts

### Do:
- **Do** sacar cada color del tema Oscuro de CotejoBoard con su nombre, y declarar junto al token cualquier desviación y su motivo (como `tenue-hondo`).
- **Do** reservar `senal` para el check, lo que espera comprobación, lo hecho, el «Copiado» y el foco, y acompañarlo siempre de texto o del check.
- **Do** dibujar las pruebas con piezas del board (columna, carta, chip, evidencia, comando) en HTML, no con capturas.
- **Do** poner comandos, JSON y cifras en IBM Plex Mono con `tabular-nums`.
- **Do** usar los muelles cortos y la curva `cubic-bezier(0.16, 1, 0.3, 1)`, y dejar todo estático con `prefers-reduced-motion`.
- **Do** dibujar iconos en SVG con trazo 1,75 sobre caja de 24, `stroke-linecap: round`.

### Don't:
- **Don't** pintar de verde el medidor de ahorro, una cifra, un enlace o un botón que no sea comprobar.
- **Don't** usar ámbar fuera de una tarea devuelta o bloqueada.
- **Don't** separar la C de «otejo», rotar, sombrear o degradar el logo, ni poner el check en otro color que `senal`.
- **Don't** poner etiquetas mono en mayúsculas como titulillo encima de un H2; esas etiquetas son cromo del board.
- **Don't** usar texto de cuerpo en un gris más oscuro que `tenue-hondo` (#878B95).
- **Don't** construir grids de features con iconos, capturas flotantes ni testimonios.
