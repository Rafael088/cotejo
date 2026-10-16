---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Página web de Cotejo (landing)

Scope: la página pública de Cotejo (`web/`, React + Vite, prerender a estática para GitHub Pages en `cotejo.dev`). Modo: **Persuade**.
Audiencia: quien usa agentes de código (Claude Code, Codex, Gemini CLI, opencode) y quiere estructura, programe o no; llega desde YouTube. Acción: copiar el comando de instalación. Prueba: la demo donde el agente entrega y el visitante pone el check, y el ahorro medido (480 contra 4.700 tokens; 19,7× con su supuesto). Restricciones: Obsidian y Notion como compatibles; beta.
Memorable: en la demo, el último paso es tuyo: aprobar o devolver.
Dominio: `cotejo.dev`. Los scripts `install.sh`/`install.ps1` se sirven desde `web/public/` (GitHub Pages).

## Direction contract

**Diseño aprobado:** https://claude.ai/artifact/5q6VXzDzPHG6Tdknemtw1D (mundo Oscuro, una columna, 4 páginas, demo viva)

THESIS: La portada se gana con una demo viva donde el visitante pone el check: el agente reparte y entrega solo, y el último paso (aprobar o devolver) espera a quien mira. Todo lo demás es corto y lleva a una de tres páginas. Rechaza la landing de categoría: grid de features con iconos, captura flotante y testimonios.

OWN-WORLD: El mundo de CotejoBoard tal cual (tema Oscuro): fondo #101114, columnas #15161A, cartas #2A2C33 con borde 1px #3A3D45 y radio 10px, texto blanco, tenue #A8ACB6. Sora para titulares, Inter para texto, IBM Plex Mono para comandos, cifras y JSON. Una columna de 1180px. Verde Hecho (#16C98D) solo en el check, en lo que espera comprobación (Para comprobar, Aprobar) y en el «Copiado»; el ahorro va en blanco y plata. Ámbar (#F0C987) solo para devuelta.

STORY: Lee «El tablero de control para tu vibe coding.» y copia el comando, o baja. En la demo ve a un agente repartir dos tareas, hacerlas y entregarlas con pruebas; la demo se para y le toca a él: aprueba o devuelve (la devuelta vuelve en ámbar con su motivo y el agente la rehace). Tres pasos de cero a la primera entrega; 480 contra 4.700 tokens a proporción; dos puertas (No programo / Programo) a /comofunciona; con qué agentes funciona; cierre con el comando. El pie firma: «Tus agentes entregan. Tú compruebas.».

FIRST VIEWPORT: Cabecera fija (logo, versión, Cómo funciona, Primeros pasos, Tokens, Instalar). Hero alineado a la izquierda, sin fondo ni logo grande: H1 «El tablero de control para tu vibe coding.» (Sora, clamp 42–88px), bajada corta y el bloque de instalación (pestañas Linux/Windows, comando, Copiar; «Gratis · beta»). La ventana de la demo asoma debajo.

FORM: Cuatro páginas reales y prerenderizadas (`src/rutas.js`): / (hero, demo, pasos, ahorro, puertas, cierre), /comofunciona (selector No programo: cuatro escenas que avanzan solas / Programo: seis verbos con su salida real y el árbol de .cotejo/), /primerospasos (el primer día y cada día, con frases copiables) y /tokens (la nota que corre contra la respuesta de la CLI, la escala, 19,7× con su supuesto y el segundo cerebro → .cotejo/). Interacción firma: Aprobar / Devolver en la demo. Movimiento: muelles cortos y `cubic-bezier(0.16, 1, 0.3, 1)`; con `prefers-reduced-motion` nada avanza solo y la demo se queda en su foto, con los botones vivos. Sin JavaScript, la demo se lee entera (el HTML trae el guion aplicado).

FINISH: DESIGN.md al día con lo construido; comprobaciones (`npm run comprobar`, `comprobar:consola`, `comprobar:movil`) en verde en las cuatro rutas.
