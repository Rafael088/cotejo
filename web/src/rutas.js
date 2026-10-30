// Las páginas de la web, en un solo sitio y sin JSX: las lee la app (main.jsx, paginas.jsx), el
// prerender (scripts/prerender.mjs, que saca un HTML por ruta con su <head> y el sitemap) y las
// comprobaciones de scripts/. Una página nueva es una fila aquí y su componente en paginas.jsx.
//
// `archivo` es lo que el build deja en dist/: GitHub Pages sirve /comofunciona desde
// comofunciona.html, sin barra final y sin redirección. El canonical sale de SITIO + ruta.
export const SITIO = 'https://cotejo.dev'

export const RUTAS = [
  {
    ruta: '/',
    archivo: 'index.html',
    titulo: 'Cotejo · Vibe coding con Claude Code y proyectos que crecen',
    descripcion:
      'El tablero de control para vibe coding profesional: tus proyectos en orden, Claude Code u otro agente entrega y tú compruebas. Gratis en Linux y Windows.',
  },
  {
    ruta: '/comofunciona',
    archivo: 'comofunciona.html',
    titulo: 'Cómo funciona Cotejo · Tu agente trabaja, tú decides',
    descripcion:
      'Programes o no: tu agente planea y entrega con un resumen claro, y tú apruebas o devuelves. El ciclo de Cotejo, de init a release, con la salida real.',
  },
  {
    ruta: '/primerospasos',
    archivo: 'primerospasos.html',
    titulo: 'Primeros pasos con Cotejo · El primer día y cada día',
    descripcion:
      'Instala Cotejo, crea tu primer proyecto en el Inicio de la app, revisa el plan y aprueba cada entrega en CotejoBoard. Y las frases para cada día.',
  },
  {
    ruta: '/tokens',
    archivo: 'tokens.html',
    titulo: 'Cotejo y los tokens · Tu agente lee 480, no 4.700',
    descripcion:
      'Cuánto contexto ahorra Cotejo, medido: la respuesta de la CLI contra la nota entera, con su supuesto, y tu segundo cerebro de Obsidian o Notion en .cotejo/.',
  },
]

export const canonical = (ruta) => `${SITIO}${ruta}`

// De una ruta del navegador (con la base de Vite delante, /cotejo/ sin dominio) a la de RUTAS.
// Acepta la barra final y el .html; lo que no es de ninguna página cae en la portada.
export function rutaDe(pathname, base = '/') {
  let p = pathname.startsWith(base) ? pathname.slice(base.length - 1) : pathname
  p = p.replace(/\/index\.html$/, '/').replace(/\.html$/, '')
  if (p.length > 1) p = p.replace(/\/+$/, '')
  return RUTAS.some((r) => r.ruta === p) ? p : '/'
}
