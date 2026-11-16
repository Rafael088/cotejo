// Las páginas de la web, en un solo sitio y sin JSX: las lee la app (main.jsx, paginas.jsx), el
// prerender (scripts/prerender.mjs, que saca un HTML por ruta con su <head> y el sitemap) y las
// comprobaciones de scripts/. Una página nueva es una fila aquí y su componente en paginas.jsx.
//
// `archivo` es lo que el build deja en dist/: GitHub Pages sirve /docs/board desde
// docs/board.html (y /docs desde docs.html), sin barra final y sin redirección. El canonical sale
// de SITIO + ruta.
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
    ruta: '/docs',
    archivo: 'docs.html',
    titulo: 'Docs de Cotejo · Qué es, instalar y el ciclo',
    descripcion:
      'Qué es Cotejo, cómo instalarlo en Linux y Windows y el ciclo de init a release: tus agentes entregan, tú compruebas. Gratis y en beta.',
  },
  {
    ruta: '/docs/primeros-pasos',
    archivo: 'docs/primeros-pasos.html',
    titulo: 'Primeros pasos · Docs de Cotejo',
    descripcion:
      'Crea tu primer proyecto desde el Inicio de la app o con cotejo init en un repo, revisa el plan y comprueba tu primera entrega. Y lo que repites cada día.',
  },
  {
    ruta: '/docs/board',
    archivo: 'docs/board.html',
    titulo: 'El board · Docs de Cotejo',
    descripcion:
      'Las cuatro columnas de CotejoBoard, arrastrar a Haciéndola para lanzar al agente, pausar, rechazar con motivo, aprobar y la capacidad de la máquina.',
  },
  {
    ruta: '/docs/maestro',
    archivo: 'docs/maestro.html',
    titulo: 'El maestro · Docs de Cotejo',
    descripcion:
      'La conversación dentro del board: le pides tareas en llano, pregunta por el proyecto y reparte lo asignado. Hace casi todo menos aprobar.',
  },
  {
    ruta: '/docs/enrutador',
    archivo: 'docs/enrutador.html',
    titulo: 'El enrutador · Docs de Cotejo',
    descripcion:
      'Cómo decide Cotejo a qué modelo le toca cada tarea: niveles, veto humano, orden de decisión, y los verbos despachar, revisar y capacidad.',
  },
  {
    ruta: '/docs/agentes',
    archivo: 'docs/agentes.html',
    titulo: 'Agentes y modelos · Docs de Cotejo',
    descripcion:
      'Claude Code, Codex, OpenCode, Gemini CLI y Antigravity CLI, MCP, los permisos del modo sin interfaz y el catálogo de modelos.',
  },
  {
    ruta: '/docs/almacen',
    archivo: 'docs/almacen.html',
    titulo: 'El almacén · Docs de Cotejo',
    descripcion:
      'La carpeta .cotejo/ de tu repo: decisiones, arquitectura, problemas y bitácora, y los verbos para enterarse barato y escribir sin editar a mano.',
  },
  {
    ruta: '/docs/tokens',
    archivo: 'docs/tokens.html',
    titulo: 'Ahorro de tokens · Docs de Cotejo',
    descripcion:
      'El medidor de ahorro de Cotejo: lo que lee tu agente con la CLI contra la nota entera, medido con cotejo ahorro y con su supuesto a la vista.',
  },
  {
    ruta: '/docs/fuentes',
    archivo: 'docs/fuentes.html',
    titulo: 'Fuentes · Docs de Cotejo',
    descripcion:
      'Las tareas viven en tu repo por defecto. Cómo importar un proyecto desde Obsidian o Notion y cómo conectar otra app con un adaptador.',
  },
  {
    ruta: '/docs/cli',
    archivo: 'docs/cli.html',
    titulo: 'La CLI · Docs de Cotejo',
    descripcion:
      'Todos los verbos de cotejo para agentes y para el enrutador, una línea cada uno: tareas, contexto, proyecto, fuentes y configuración.',
  },
  {
    ruta: '/docs/configuracion',
    archivo: 'docs/configuracion.html',
    titulo: 'Configuración · Docs de Cotejo',
    descripcion:
      'Lo esencial de la configuración de Cotejo: el archivo único, dónde guarda cosas, ajustes del enrutador, variables de entorno y opciones del instalador.',
  },
]

// Las páginas de antes, que siguen existiendo como HTML estático que redirige a su equivalente en
// /docs (meta refresh + canonical + enlace visible). No están en RUTAS ni en el sitemap: no son
// páginas, son cabos sueltos para quien guardó el enlace viejo.
export const REDIRECCIONES = [
  { ruta: '/comofunciona', archivo: 'comofunciona.html', destino: '/docs' },
  { ruta: '/primerospasos', archivo: 'primerospasos.html', destino: '/docs/primeros-pasos' },
  { ruta: '/tokens', archivo: 'tokens.html', destino: '/docs/tokens' },
]

export const canonical = (ruta) => `${SITIO}${ruta}`

// De una ruta del navegador (con la base de Vite delante, /cotejo/ sin dominio) a la de RUTAS.
// Acepta la barra final y el .html (también en las anidadas: /docs/board.html); lo que no es de
// ninguna página cae en la portada.
export function rutaDe(pathname, base = '/') {
  let p = pathname.startsWith(base) ? pathname.slice(base.length - 1) : pathname
  p = p.replace(/\/index\.html$/, '/').replace(/\.html$/, '')
  if (p.length > 1) p = p.replace(/\/+$/, '')
  return RUTAS.some((r) => r.ruta === p) ? p : '/'
}
