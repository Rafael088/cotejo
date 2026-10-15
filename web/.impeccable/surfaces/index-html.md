---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Página web de Cotejo (landing)

Scope: la página pública de Cotejo (`web/`, React + motion, estática en GitHub Pages). Modo: **Persuade**.
Audiencia: quien usa agentes de código y tiene un segundo cerebro; llega desde YouTube. Acción: copiar el comando de instalación. Prueba: el medidor de ahorro (19,7× medido, con su supuesto) y el board real. Restricciones: solo Obsidian y Notion como compatibles; dominio sin comprar (constante); beta.
Memorable: la nota entera contra lo que devuelve la CLI, a escala real.
Pendiente: dominio; los scripts `install.sh`/`install.ps1` servidos desde él aún no existen.

## Direction contract

THESIS: La página se gana con una cifra medida y enseña el material que mide: la nota entera contra la respuesta de la CLI, a escala, con el supuesto escrito debajo. Rechaza la landing de categoría: grid de features con iconos, captura flotante y testimonios.

OWN-WORLD: El mundo de CotejoBoard tal cual: fondo #101114, columnas #15161A, cartas #2A2C33 con borde 1px #3A3D45 y radio 10px, texto blanco, tenue #A8ACB6. Sora para titulares, Inter para texto, IBM Plex Mono para comandos, cifras y etiquetas en mayúsculas espaciadas. Verde Hecho solo en el check del logo, en lo que espera comprobación y en el «copiado»; el medidor va en blanco y plata, sin verde, como en el board. Ámbar solo para devuelta/bloqueada.

STORY: Ve el board vivo detrás del logo y lee «Tus agentes entregan. Tú compruebas.»; copia el comando o baja. Ve una nota real de 4.700 tokens contra 480 de la CLI y el 19,7× con su supuesto; entiende el trato (el agente toma y entrega, tú compruebas); ve con qué apps funciona y copia el comando de su sistema.

FIRST VIEWPORT: 100svh. Detrás, CotejoBoard dibujado en HTML a ancho completo, inclinado en perspectiva, atenuado bajo un velo radial; una carta viaja sola de Haciéndola a Para comprobar. Al centro: logo (64px de alto), H1 en Sora ~clamp(40px,6vw,76px), una línea en Inter tenue, y debajo el bloque de instalación: pestañas Linux/Windows, comando en mono con botón copiar (acción principal). Bajo él, enlace «Mira cuánto ahorra».

FORM: El medidor, puesto 3 de mi lista ordenada; seed key 72845005. Interacción firma: al hacer scroll, la columna de la nota corre y un contador mono suma caracteres; la barra de la CLI se dibuja a 1/19,7 de la de la nota. Movimiento: muelles cortos como las cartas del board; todo estático con reduced-motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
