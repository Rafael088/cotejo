// Comprueba los metadatos para compartir y buscar, sin navegador ni dependencias:
// `node web/scripts/comprobar-meta.mjs` después de `npm --prefix web run build`.
// Lee el HTML de cada ruta de src/rutas.js en dist/ (lo que ven buscadores y vistas previas) y
// falla si:
//   - falta <html lang="es">, el <title> (≤ 60) o la descripción (≤ 160), o no son los de su
//     ruta en src/rutas.js; en la portada, si no nombran «vibe coding», «proyectos» y «Claude Code»;
//   - el canonical y og:url no son la URL absoluta de esa ruta en cotejo.dev; og:title,
//     og:description, twitter:title y twitter:description no repiten el título y la descripción;
//     og:image o twitter:image no son la de cotejo.dev, o twitter:card no es summary_large_image;
//   - el JSON-LD no parsea con JSON.parse, no es un SoftwareApplication o le faltan los datos
//     (Linux y Windows, precio 0, la versión de tareas/__init__.py), o trae valoraciones;
// y que web/public/og.png es un PNG de 1200×630 (lo lee de la cabecera IHDR) de menos de 300 KB.
import { readFileSync, statSync } from 'node:fs'
import { RUTAS, canonical } from '../src/rutas.js'

const web = new URL('..', import.meta.url)
const SITIO = canonical('/')
const IMAGEN = 'https://cotejo.dev/og.png'
const init = readFileSync(new URL('../tareas/__init__.py', web), 'utf8')
const version = init.match(/^__version__ = "([^"]+)"/m)?.[1]
const desescapar = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')

function revisar(html, esperado, fallos) {
  const head = html.match(/<head>([\s\S]*?)<\/head>/)?.[1] ?? ''
  const igual = (que, valor, esperadoAqui) => {
    if (valor !== esperadoAqui) fallos.push(`${que}: «${valor ?? '(falta)'}», esperaba «${esperadoAqui}»`)
  }
  // El contenido de <meta> por name o property (en cualquier orden de atributos).
  const meta = (clave) => {
    for (const [etiqueta] of head.matchAll(/<meta\b[^>]*>/g)) {
      if (new RegExp(`\\b(?:name|property)="${clave}"`).test(etiqueta)) {
        const c = etiqueta.match(/\bcontent="([^"]*)"/)
        return c ? desescapar(c[1]) : ''
      }
    }
    return null
  }

  if (!/<html\b[^>]*\blang="es"/.test(html)) fallos.push('Falta <html lang="es">')

  const titulo = desescapar(head.match(/<title>([^<]*)<\/title>/)?.[1] ?? '')
  const descripcion = meta('description') ?? ''
  if (!titulo) fallos.push('Falta el <title>')
  igual('<title>', titulo, esperado.titulo)
  igual('description', descripcion, esperado.descripcion)
  if (titulo.length > 60) fallos.push(`El título mide ${titulo.length} caracteres (máximo 60)`)
  if (!descripcion) fallos.push('Falta la descripción')
  if (descripcion.length > 160) fallos.push(`La descripción mide ${descripcion.length} caracteres (máximo 160)`)
  for (const palabra of esperado.ruta === '/' ? ['vibe coding', 'proyectos', 'Claude Code'] : []) {
    if (!`${titulo} ${descripcion}`.toLowerCase().includes(palabra.toLowerCase()))
      fallos.push(`Ni el título ni la descripción dicen «${palabra}»`)
  }
  for (const prohibida of ['10x', 'supercarga', 'automatiza todo']) {
    if (`${titulo} ${descripcion}`.toLowerCase().includes(prohibida)) fallos.push(`El texto promete «${prohibida}»`)
  }

  const enlace = head.match(/<link\b[^>]*\brel="canonical"[^>]*>/)?.[0]?.match(/\bhref="([^"]*)"/)?.[1]
  igual('canonical', enlace, canonical(esperado.ruta))
  igual('og:url', meta('og:url'), canonical(esperado.ruta))
  igual('og:image', meta('og:image'), IMAGEN)
  igual('og:image:width', meta('og:image:width'), '1200')
  igual('og:image:height', meta('og:image:height'), '630')
  igual('twitter:card', meta('twitter:card'), 'summary_large_image')
  igual('twitter:image', meta('twitter:image'), IMAGEN)
  igual('og:title', meta('og:title'), titulo)
  igual('og:description', meta('og:description'), descripcion)
  igual('twitter:title', meta('twitter:title'), titulo)
  igual('twitter:description', meta('twitter:description'), descripcion)

  // JSON-LD.
  const bloques = [...head.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)]
  let app = null
  if (!bloques.length) fallos.push('No hay JSON-LD en el <head>')
  for (const [, cuerpo] of bloques) {
    let datos
    try {
      datos = JSON.parse(cuerpo)
    } catch (e) {
      fallos.push(`El JSON-LD no parsea: ${e.message}`)
      continue
    }
    if (datos['@type'] === 'SoftwareApplication') app = datos
  }
  if (bloques.length && !app) fallos.push('Ningún JSON-LD tiene @type SoftwareApplication')
  if (app) {
    igual('JSON-LD name', app.name, 'Cotejo')
    igual('JSON-LD url', app.url, SITIO)
    igual('JSON-LD applicationCategory', app.applicationCategory, 'DeveloperApplication')
    igual('JSON-LD operatingSystem', app.operatingSystem, 'Linux, Windows')
    igual('JSON-LD softwareVersion', app.softwareVersion, version)
    igual('JSON-LD offers.price', String(app.offers?.price), '0')
    igual('JSON-LD offers.priceCurrency', app.offers?.priceCurrency, 'USD')
    if (!app.description) fallos.push('El JSON-LD no trae description')
    for (const inventada of ['aggregateRating', 'review'])
      if (inventada in app) fallos.push(`El JSON-LD trae «${inventada}»: no hay reseñas que respalden eso`)
  }
  return { titulo, descripcion }
}

const fallos = []
const vistas = []
for (const r of RUTAS) {
  let html
  try {
    html = readFileSync(new URL(`dist/${r.archivo}`, web), 'utf8')
  } catch {
    fallos.push(`No encuentro dist/${r.archivo}: corre antes «npm --prefix web run build».`)
    continue
  }
  const propios = []
  vistas.push({ ...r, ...revisar(html, r, propios) })
  fallos.push(...propios.map((f) => `${r.ruta}: ${f}`))
}

// og.png: firma PNG y ancho/alto del IHDR (bytes 16–23, big-endian).
const png = new URL('public/og.png', web)
try {
  const b = readFileSync(png)
  const firma = '89504e470d0a1a0a'
  if (b.subarray(0, 8).toString('hex') !== firma || b.subarray(12, 16).toString() !== 'IHDR') {
    fallos.push('web/public/og.png no es un PNG')
  } else {
    const ancho = b.readUInt32BE(16)
    const alto = b.readUInt32BE(20)
    if (ancho !== 1200 || alto !== 630) fallos.push(`og.png mide ${ancho}×${alto}, esperaba 1200×630`)
  }
  const kb = statSync(png).size / 1024
  if (kb >= 300) fallos.push(`og.png pesa ${kb.toFixed(0)} KB (máximo 300)`)
} catch {
  fallos.push('Falta web/public/og.png')
}
try {
  readFileSync(new URL('dist/og.png', web))
} catch {
  fallos.push('dist/og.png no llegó al build')
}

if (fallos.length) {
  console.error('meta: MAL')
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
for (const v of vistas) {
  console.log(`meta: bien en ${v.ruta}. título (${v.titulo.length}): «${v.titulo}»`)
  console.log(`  descripción (${v.descripcion.length}): «${v.descripcion}»`)
  console.log(`  canonical y og:url ${canonical(v.ruta)}`)
}
console.log(`og:image ${IMAGEN} (1200×630), JSON-LD SoftwareApplication ${version} en las ${vistas.length} páginas`)
