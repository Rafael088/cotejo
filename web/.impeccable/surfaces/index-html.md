---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Página web de Cotejo (landing)

Scope: la página pública de Cotejo (`web/`, React + Vite, prerender a estática para GitHub Pages en `cotejo.dev`). Modo: **Persuade**.
Audiencia: quien usa agentes de código (Claude Code, Codex, Gemini CLI, opencode) y quiere estructura; llega desde YouTube. Acción: copiar el comando de instalación. Prueba: medidor de ahorro (19,7× medido, con supuesto) y tablero vivo detrás del hero. Restricciones: Obsidian y Notion como compatibles; beta.
Memorable: la nota entera contra lo que devuelve `cotejo tareas`, a escala real, con supuesto.
Dominio: `cotejo.dev` existe. Los scripts `install.sh`/`install.ps1` se sirven desde `web/public/` (GitHub Pages) sin servidor custom.

## Direction contract

**Diseño aprobado:** https://claude.ai/artifact/5q6VXzDzPHG6Tdknemtw1D (mundo Oscuro, una columna, 4 páginas, demo viva)

THESIS: La página se gana con una cifra medida y enseña el material que mide: la nota entera contra la respuesta de la CLI, a escala, con el supuesto escrito debajo. Rechaza la landing de categoría: grid de features con iconos, captura flotante y testimonios.

OWN-WORLD: El mundo de CotejoBoard tal cual (tema Oscuro): fondo #101114, columnas #15161A, cartas #2A2C33 con borde 1px #3A3D45 y radio 10px, texto blanco, tenue #A8ACB6. Sora para titulares, Inter para texto, IBM Plex Mono para comandos, cifras y etiquetas en mayúsculas espaciadas. Verde Hecho (#16C98D) solo en el check del logo, en lo que espera comprobación y en el «Copiado»; el medidor va en blanco y plata, sin verde, como en el board. Ámbar (#F0C987) solo para devuelta/bloqueada.

STORY: Ve el board vivo detrás del titular y lee la frase de pie «Tus agentes entregan. Tú compruebas.»; copia el comando o baja. Una nota real de 4.700 tokens contra 480 de la CLI y el 19,7× con su supuesto; entiende el trato (el agente toma y entrega, tú compruebas, no hay verbo para terminar); ve con qué apps funciona y copia el comando de su sistema. Cuatro páginas estáticas: cómo funciona (No programo / Programo), primeros pasos (primer día + cada día), y tokens (medidor con flujo del contexto).

FIRST VIEWPORT: 100svh. Hero con titular «El tablero de control para tu vibe coding.», bajada, e InstalarRapido (2 tabs, comando + copiar). Debajo, Demo: tablero vivo a la derecha, terminal a la izquierda, una carta se mueve de Haciéndola a Para comprobar. Tres pasos (Instala, Arranca, Revisa). Escala: nota entera vs. CLI (19,7×). Dos puertas: No programo / Programo (a /comofunciona). Cierre con instalación.

FORM: Cuatro secciones principales en la portada: 
1. **Hero + InstalarRapido:** H1 + bajada + bloque de instalación (tablas SO, comando, botón copiar)
2. **Demo:** Tablero vivo (4 columnas) + terminal del agente, con animaciones cortas y respect a reduced-motion
3. **InicioPasos:** 3 pasos en grid (Instala, Arranca, Revisa)
4. **InicioAhorro:** Escala de barras (nota vs. CLI, 19,7×, con supuesto en nota al pie)
5. **InicioPuertas:** 2 paneles (No programo / Programo) que van a /comofunciona
6. **Cierre:** Panel de instalación final

Movimiento: transiciones de 200ms con `cubic-bezier(0.16, 1, 0.3, 1)`; todo estático con `prefers-reduced-motion: reduce`.

FINISH: DESIGN.md actualizado con componentes y decisiones; dominio existente; HTML prerenderizado sin JS para accesibilidad (rutas reales, sin hash).
