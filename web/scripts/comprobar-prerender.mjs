// Comprueba el prerender sin navegador ni shell: `node web/scripts/comprobar-prerender.mjs`
// (o `npm run comprobar` en web/) después de `npm run build`. Lee el HTML de cada ruta de
// src/rutas.js en dist/ (lo mismo que trae `curl https://cotejo.dev/comofunciona`) y falla si:
//   - #root llega vacío o no hay un <h1> con texto;
//   - alguna <section> no tiene su título (el elemento de su aria-labelledby, con texto);
//   - el <h1> o algo de la sección del h1 (lo de arriba del pliegue) llega con opacity:0 en línea;
//   - en cualquier ruta, el h1 no es el de EXIGIDAS o falta alguna de sus secciones exigidas con
//     su titular exacto, o llega con opacity:0 en línea;
//   - dos rutas traen el mismo <h1> (el prerender pintó la misma página en todas);
//   - una página de /docs no trae su barra lateral (con ella misma como aria-current), su «En esta
//     página» con un enlace por cada h2, o su «Anterior / Siguiente» según src/docs.js; o src/docs.js
//     y src/rutas.js no hablan de las mismas páginas;
//   - una página de antes (REDIRECCIONES) no redirige a su destino con meta refresh, canonical y un
//     enlace visible, o se coló en el sitemap.
// Fuera de EXIGIDAS no conoce los textos.
import { readFileSync } from 'node:fs'
import { RUTAS, REDIRECCIONES, canonical } from '../src/rutas.js'
import { PAGINAS_DOCS, vecinas } from '../src/docs.js'

// Lo que cada ruta tiene que traer en el HTML: su h1 y sus secciones (por id de la <section> o,
// si no lleva, por el id de su aria-labelledby) con el h2 exacto. Los textos son los de dist/.
const EXIGIDAS = {
  '/': {
    h1: 'El tablero de control para tu vibe coding.',
    secciones: [
      ['agentes', 'Funciona con tu agente.'],
      ['funciones', 'Diriges tú. Trabajan ellos.'],
      ['cierre', 'Instálalo y arrastra tu primera tarea.'],
    ],
  },
  '/docs': {
    h1: 'Documentación de Cotejo.',
    secciones: [
      ['que-es', 'Qué es Cotejo'],
      ['instalar', 'Instalar'],
      ['ciclo', 'El ciclo, de init a release'],
      ['seguir', 'Por dónde seguir'],
    ],
  },
  '/docs/primeros-pasos': {
    h1: 'Primeros pasos.',
    secciones: [
      ['desde-la-app', 'Desde la app, sin terminal'],
      ['en-un-repo', 'En un repo, con cotejo init'],
      ['cada-dia', 'Cada día'],
    ],
  },
  '/docs/board': {
    h1: 'El board.',
    secciones: [
      ['columnas', 'Las cuatro columnas'],
      ['haciendo', 'Arrastrar a Haciéndola'],
      ['pausar', 'Pausar y retomar'],
      ['comprobar', 'Comprobar una entrega'],
      ['rechazar', 'Rechazar con motivo'],
      ['capacidad', 'Capacidad de la máquina'],
      ['teclado', 'Teclado'],
    ],
  },
  '/docs/maestro': {
    h1: 'El maestro.',
    secciones: [
      ['que-es', 'Una conversación dentro del board'],
      ['que-hace', 'Qué puede hacer'],
      ['aprobar', 'Aprobar, nunca'],
      ['agente', 'Con qué agente habla'],
      ['cli', 'Desde la terminal'],
    ],
  },
  '/docs/enrutador': {
    h1: 'El enrutador.',
    secciones: [
      ['niveles', 'Niveles'],
      ['veto', 'El veto humano'],
      ['orden', 'Orden de decisión'],
      ['despachar', 'despachar'],
      ['revisar', 'revisar'],
      ['capacidad', 'capacidad'],
    ],
  },
  '/docs/agentes': {
    h1: 'Agentes y modelos.',
    secciones: [
      ['compatibles', 'Con qué agentes funciona'],
      ['mcp', 'MCP'],
      ['permisos', 'Permisos del modo sin interfaz'],
      ['modelos', 'Catálogo de modelos'],
    ],
  },
  '/docs/almacen': {
    h1: 'El almacén.',
    secciones: [
      ['que-es', 'Qué es el almacén'],
      ['enterarse', 'Para enterarse, de menos a más'],
      ['escribir', 'Para escribir'],
      ['decisiones', 'Las decisiones no se editan ni se aceptan por verbo'],
    ],
  },
  '/docs/tokens': {
    h1: 'Ahorro de tokens.',
    secciones: [
      ['consulta', 'Una consulta, comparada'],
      ['medidor', 'El medidor: cotejo ahorro'],
      ['honesto', 'Cómo se mantiene honesto'],
    ],
  },
  '/docs/fuentes': {
    h1: 'Fuentes.',
    secciones: [
      ['repo', 'El repo, por defecto'],
      ['importar', 'Traer un proyecto que ya existe'],
      ['obsidian', 'Obsidian'],
      ['notion', 'Notion'],
      ['cambiar', 'Cambiar de fuente'],
      ['adaptadores', 'Conectar otra app'],
    ],
  },
  '/docs/cli': {
    h1: 'La CLI.',
    secciones: [
      ['principios', 'Cómo habla la CLI'],
      ['tareas', 'Tareas'],
      ['enrutador', 'Enrutador'],
      ['contexto', 'Contexto'],
      ['proyecto', 'Proyecto, fuentes y configuración'],
    ],
  },
  '/docs/configuracion': {
    h1: 'Configuración.',
    secciones: [
      ['archivo', 'El archivo de configuración'],
      ['rutas', 'Dónde guarda cosas'],
      ['enrutador', 'El enrutador y el maestro'],
      ['variables', 'Variables de entorno'],
      ['instalador', 'Opciones del instalador'],
      ['barra', 'La barra de Omarchy y los temas'],
    ],
  },
}

const texto = (s) => s.replace(/<[^>]*>/g, ' ').replace(/&[a-z#0-9]+;/gi, ' ').replace(/\s+/g, ' ').trim()
const opacidadCero = /style="[^"]*opacity:\s*0(?:\.0+)?(?![.\d])/

// Lo que toda página de /docs trae en el HTML: el índice, «En esta página» y «Anterior / Siguiente».
function revisarDocs(ruta, pagina, fallos) {
  const enlaces = (nav) => [...nav.matchAll(/<a\b([^>]*)>/g)].map((m) => ({ href: m[1].match(/href="([^"]*)"/)?.[1], actual: /aria-current="page"/.test(m[1]) }))
  const nav = (nombre) => pagina.match(new RegExp(`<nav\\b[^>]*aria-label="${nombre}"[^>]*>([\\s\\S]*?)</nav>`))?.[1]
  const lateral = pagina.match(/<nav class="docs-lateral"[^>]*>([\s\S]*?)<\/nav>/)?.[1]
  if (!lateral) fallos.push('Falta la barra lateral (.docs-lateral)')
  else {
    const ls = enlaces(lateral)
    for (const p of PAGINAS_DOCS) if (!ls.some((l) => l.href === p.ruta)) fallos.push(`La barra lateral no enlaza ${p.ruta}`)
    const actuales = ls.filter((l) => l.actual).map((l) => l.href)
    if (actuales.length !== 1 || actuales[0] !== ruta) fallos.push(`La barra lateral marca «${actuales.join(', ')}» como página actual, esperaba ${ruta}`)
  }
  if (!/<details class="docs-movil"/.test(pagina)) fallos.push('Falta el desplegable de móvil (.docs-movil)')
  const toc = nav('En esta página')
  const h2s = [...pagina.matchAll(/<h2 id="([^"]+)"/g)].map((m) => m[1])
  if (!toc) fallos.push('Falta «En esta página»')
  else for (const id of h2s) if (!toc.includes(`href="#${id}"`)) fallos.push(`«En esta página» no enlaza el h2 «${id}»`)
  const { anterior, siguiente } = vecinas(ruta)
  const vec = nav('Anterior y siguiente')
  if (!vec) fallos.push('Falta «Anterior / Siguiente»')
  else {
    const hrefs = enlaces(vec).map((l) => l.href)
    if (anterior && !hrefs.includes(anterior.ruta)) fallos.push(`Falta el enlace Anterior a ${anterior.ruta}`)
    if (siguiente && !hrefs.includes(siguiente.ruta)) fallos.push(`Falta el enlace Siguiente a ${siguiente.ruta}`)
    if (!anterior && /rel="prev"/.test(vec)) fallos.push('Trae Anterior en la primera página')
    if (!siguiente && /rel="next"/.test(vec)) fallos.push('Trae Siguiente en la última página')
  }
  // Cada bloque de código lleva su botón Copiar, salvo los que son una salida que se lee (data-lectura).
  for (const [fig] of pagina.matchAll(/<figure class="codigo[^"]*"[\s\S]*?<\/figure>/g))
    if (!/data-lectura/.test(fig.slice(0, 120)) && !/<button/.test(fig)) fallos.push('Un bloque de código no lleva botón Copiar')
}

function revisar(ruta, html, fallos) {
  const raiz = html.match(/<div id="root">([\s\S]*)<\/div>\s*<\/body>/)
  if (!raiz || !texto(raiz[1])) fallos.push('#root llega vacío: el build no prerenderizó la página')
  const pagina = raiz ? raiz[1] : ''

  const h1 = pagina.match(/<h1\b([^>]*)>([\s\S]*?)<\/h1>/)
  if (!h1 || !texto(h1[2])) fallos.push('No hay un <h1> con texto en el HTML')
  else if (opacidadCero.test(`<h1${h1[1]}>`)) fallos.push('El <h1> arranca en opacity:0 en línea')

  // Cada <section> con su título: el id de aria-labelledby debe existir y tener texto.
  const titulos = []
  for (const [etiqueta] of pagina.matchAll(/<section\b[^>]*>/g)) {
    const ids = etiqueta.match(/aria-labelledby="([^"]+)"/)?.[1]
    if (!ids) {
      fallos.push(`Sección sin aria-labelledby: ${etiqueta}`)
      continue
    }
    for (const id of ids.split(/\s+/)) {
      const el = pagina.match(new RegExp(`<(\\w+)\\b[^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)</\\1>`))
      if (!el || !texto(el[2])) fallos.push(`La sección «${id}» no tiene su título en el HTML`)
      else titulos.push(texto(el[2]))
    }
  }
  const minimo = ruta === '/' ? 2 : 1
  if (titulos.length < minimo) fallos.push(`Solo ${titulos.length} títulos de sección en el HTML`)

  // Arriba del pliegue: la sección que contiene el h1, sin opacity:0 en línea.
  if (h1) {
    const inicio = pagina.lastIndexOf('<section', pagina.indexOf(h1[0]))
    const fin = pagina.indexOf('</section>', pagina.indexOf(h1[0]))
    const pliegue = inicio >= 0 && fin > 0 ? pagina.slice(inicio, fin) : h1[0]
    if (opacidadCero.test(pliegue)) fallos.push('Algo de la sección del <h1> arranca en opacity:0 en línea')
  }

  // Secciones exigidas: presentes, con su titular exacto y sin nada en opacity:0 en línea.
  const exigidas = EXIGIDAS[ruta]
  if (!exigidas) fallos.push(`La ruta ${ruta} no tiene fila en EXIGIDAS`)
  else if (h1 && texto(h1[2]) !== exigidas.h1) fallos.push(`El <h1> no es «${exigidas.h1}»`)
  for (const [id, titular] of exigidas?.secciones ?? []) {
    const seccion = pagina.match(
      new RegExp(`<section\\b[^>]*(?:\\bid="${id}"|aria-labelledby="${id}(?:-titulo)?")[^>]*>([\\s\\S]*?)</section>`),
    )
    if (!seccion) {
      fallos.push(`Falta la sección «${id}» en el HTML`)
      continue
    }
    const h2 = seccion[1].match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/)
    if (!h2 || texto(h2[1]) !== titular) fallos.push(`La sección «${id}» no trae su titular «${titular}»`)
    if (opacidadCero.test(seccion[0])) fallos.push(`Algo de la sección «${id}» arranca en opacity:0 en línea`)
  }
  if (ruta.startsWith('/docs')) revisarDocs(ruta, pagina, fallos)
  return { h1: h1 ? texto(h1[2]) : '', titulos }
}

// src/docs.js y src/rutas.js tienen que hablar de las mismas páginas de /docs.
const generales = []
const deRutas = RUTAS.filter((r) => r.ruta.startsWith('/docs')).map((r) => r.ruta).sort().join(' ')
const deIndice = PAGINAS_DOCS.map((p) => p.ruta).sort().join(' ')
if (deRutas !== deIndice) generales.push(`src/rutas.js y src/docs.js no coinciden:\n    rutas: ${deRutas}\n    docs:  ${deIndice}`)

const vistos = new Map()
let mal = false
for (const { ruta, archivo } of RUTAS) {
  const camino = new URL(`../dist/${archivo}`, import.meta.url)
  const fallos = []
  let html = ''
  try {
    html = readFileSync(camino, 'utf8')
  } catch {
    fallos.push(`No encuentro dist/${archivo}: corre antes «npm --prefix web run build».`)
  }
  const { h1, titulos } = html ? revisar(ruta, html, fallos) : { h1: '', titulos: [] }
  if (h1 && vistos.has(h1)) fallos.push(`Trae el mismo <h1> que ${vistos.get(h1)}: «${h1}»`)
  vistos.set(h1, ruta)
  if (fallos.length) {
    mal = true
    console.error(`prerender: MAL en ${ruta} (dist/${archivo})`)
    for (const f of fallos) console.error(`  - ${f}`)
    continue
  }
  console.log(`prerender: bien en ${ruta}. h1: «${h1}»`)
  for (const t of titulos) console.log(`  sección: «${t}»`)
}

// Las páginas de antes redirigen a /docs: HTML estático con meta refresh, canonical y un enlace visible.
const sitemap = readFileSync(new URL('../dist/sitemap.xml', import.meta.url), 'utf8')
for (const { ruta, archivo, destino } of REDIRECCIONES) {
  const fallos = []
  let html = ''
  try {
    html = readFileSync(new URL(`../dist/${archivo}`, import.meta.url), 'utf8')
  } catch {
    fallos.push(`No encuentro dist/${archivo}: corre antes «npm --prefix web run build».`)
  }
  if (html) {
    const refresh = html.match(/<meta\s+http-equiv="refresh"\s+content="0;\s*url=([^"]*)"/)?.[1]
    if (refresh !== destino) fallos.push(`El meta refresh va a «${refresh ?? '(falta)'}», esperaba «${destino}»`)
    const canon = html.match(/<link rel="canonical" href="([^"]*)"/)?.[1]
    if (canon !== canonical(destino)) fallos.push(`El canonical es «${canon ?? '(falta)'}», esperaba «${canonical(destino)}»`)
    if (!new RegExp(`<a href="${destino}">`).test(html)) fallos.push(`No hay un enlace visible a ${destino}`)
    if (/<script\b/.test(html)) fallos.push('La página de redirección no debería llevar <script>')
    if (!RUTAS.some((r) => r.ruta === destino)) fallos.push(`${destino} no es una ruta de src/rutas.js`)
  }
  if (sitemap.includes(`<loc>${canonical(ruta)}</loc>`)) fallos.push('Está en el sitemap, y no debería')
  if (fallos.length) {
    mal = true
    console.error(`prerender: MAL en la redirección ${ruta} (dist/${archivo})`)
    for (const f of fallos) console.error(`  - ${f}`)
  } else console.log(`prerender: bien en la redirección ${ruta} → ${destino}`)
}
if (generales.length) {
  mal = true
  for (const f of generales) console.error(`prerender: MAL: ${f}`)
}
if (mal) process.exit(1)
