// Una nota de proyecto de ejemplo, como las que vive un proyecto en su repo (.cotejo/): tareas mezcladas con todo lo demás.
export const NOTA = `---
tipo: proyecto
estado: activo
prioridad: alta
tags: [web, lanzamiento]
---

# Web de Cotejo

Página pública: qué es, el ahorro medido, cómo se instala y el link de donaciones.
Sale antes del primer directo del canal. Si algo se atrasa, se recorta alcance, no la fecha.

## Contexto

La gente llega desde YouTube, en español, con un agente abierto en otra ventana.
No hay que explicar qué es un agente; sí por qué el check lo pone una persona.
La página no promete productividad. Dice lo que hace y enseña la medida.

## Decisiones

- 2026-09-26: el nombre es Cotejo. Se descartan Foco (choques de marca) y Relevo.
- 2026-09-26: un solo acento, Verde Hecho. El verde es lo que espera que lo compruebes.
- 2026-09-28: instalación por comando. Nada de asistente .exe para la web.
- 2026-09-28: se descartan npm y pip para distribuir: Cotejo no es JavaScript y es propietario.
- 2026-09-30: React con Framer Motion para la web; la app sigue en GTK4.
- El dominio se compra antes de publicar. Mientras tanto, una constante en config.js.

## Tareas

- [x] Kit de marca: logo, favicon, PNG de 180, 192 y 512 #facil #agente/haiku ^web-k2m1
- [x] Tokens de color desde el tema oscuro del board #medio #agente/opus ^web-p9d3
- [ ] Comprar el dominio y apuntarlo a GitHub Pages #facil #agente/persona ^web-a1b2
- [ ] Servir install.sh e install.ps1 desde el dominio #medio ^web-c3d4
- [ ] Escribir el texto de la sección de fuentes #facil ^web-e5f6
- [ ] Componente del comando con botón de copiar #facil #en-curso #agente/sonnet ^web-g7h8
- [ ] Animación de la órbita de apps compatibles #medio #en-curso #agente/opus ^web-i9j0
- [ ] Favicon y apple-touch-icon desde el kit #facil #por-validar #agente/haiku ^web-k1l2
- [ ] Pestañas Linux / Windows en el hero #facil #por-validar #agente/sonnet ^web-m3n4

## Notas de la reunión del lunes

Revisamos el mockup del hero en Excalidraw. La app va detrás, un poco animada, con el logo y
la frase al centro. Debajo, el comando de instalación con su botón de copiar. Se habló de
mostrar las fuentes alrededor de la C, girando: el repo primero; Obsidian y Notion solo para
importar lo que ya existe. Nada de logos de apps que no funcionan todavía.

Pendiente de decidir: si el directo enseña el medidor en vivo o una captura. En vivo es más
honesto, pero depende de que la máquina no esté despachando nada pesado en ese momento.

## Enlaces

- [[Cotejo]] · [[Cotejo - Lanzamiento v1.0]] · [[Canal de YouTube]]
- Kit de marca en docs/marca/ · Temas en data/temas/
- Conectar otra app: cómo se escribe un adaptador.

## Bitácora

- 09-28 La revisión del MVP congela el alcance de la 1.0.
- 09-28 Se reparten cinco tareas esa noche; todas quedan para comprobar.
- 09-29 Suite en verde: 580 pruebas. Se instala con install.sh y cotejo --version da 1.0.0.
- 09-30 Primer diseño de la web: hero, medidor, órbita, instalación y pie.

## Ideas sueltas

- Un modo claro para la web cuando salga la versión en inglés.
- Una página de documentación generada desde el protocolo de agentes.
- Un contador público de descargas, si algún día tiene sentido.
- Una galería de temas de color hechos por la comunidad, comprobados con cotejo temas comprobar.
`

// Lo que devuelve `cotejo tareas --proyecto web --estado pendiente`, con las claves reales del verbo.
const tarea = (id, texto, nombre, agente, dificultad) => ({
  id, texto, nombre, version: '', proyecto: 'web', estado: 'pendiente', agente, dificultad, nota: 'web/.cotejo/tareas.md',
})
export const RESPUESTA_DATOS = {
  esquema: 1,
  total: 3,
  tareas: [
    tarea('web-a1b2', 'Comprar el dominio y apuntarlo a GitHub Pages', 'Comprar el dominio…', 'persona', 'facil'),
    tarea('web-c3d4', 'Servir install.sh e install.ps1 desde el dominio', 'Servir install.sh…', '', 'medio'),
    tarea('web-e5f6', 'Escribir el texto de la sección de fuentes', 'Escribir el texto…', '', 'facil'),
  ],
}
export const RESPUESTA = JSON.stringify(RESPUESTA_DATOS)
