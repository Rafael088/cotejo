// Comprueba los archivos sueltos que la web publica desde web/public, sin navegador ni
// dependencias: `node web/scripts/comprobar-public.mjs` después de `npm --prefix web run build`.
// Lee dist/ (lo que acaba en gh-pages) y falla si:
//   - dist/robots.txt no permite rastrear o no apunta a Sitemap: https://cotejo.dev/sitemap.xml;
//   - dist/sitemap.xml no es XML bien formado (declaración, etiquetas que cierran en orden,
//     una sola raíz <urlset> del espacio de sitemaps) o sus <loc> no son exactamente las rutas
//     de src/rutas.js (lo escribe scripts/prerender.mjs), o falta el HTML de alguna;
//   - dist/404.html no existe, no es <html lang="es">, no lleva noindex, no enlaza a la
//     portada («/») o depende de JavaScript (<script>).
import { readFileSync } from 'node:fs'
import { RUTAS, canonical } from '../src/rutas.js'

const dist = new URL('../dist/', import.meta.url)
const fallos = []

const leer = (nombre) => {
  try {
    return readFileSync(new URL(nombre, dist), 'utf8')
  } catch {
    fallos.push(`falta dist/${nombre}: ¿corriste «npm --prefix web run build»?`)
    return null
  }
}

// robots.txt
const robots = leer('robots.txt')
if (robots !== null) {
  const lineas = robots.split(/\r?\n/).map((l) => l.trim())
  if (!lineas.some((l) => /^user-agent:\s*\*$/i.test(l))) fallos.push('robots.txt: falta «User-agent: *»')
  if (lineas.some((l) => /^disallow:\s*\/\S*/i.test(l))) fallos.push('robots.txt: bloquea alguna ruta')
  if (!lineas.includes('Sitemap: https://cotejo.dev/sitemap.xml'))
    fallos.push('robots.txt: falta «Sitemap: https://cotejo.dev/sitemap.xml»')
}

// sitemap.xml: un comprobador mínimo de buena formación (sin DTD ni CDATA, que no usamos).
const xmlBienFormado = (xml) => {
  if (!/^<\?xml version="1\.0" encoding="UTF-8"\?>/.test(xml)) return 'no empieza por la declaración <?xml … UTF-8?>'
  const cuerpo = xml.replace(/^<\?xml[^?]*\?>/, '').replace(/<!--[\s\S]*?-->/g, '')
  const pila = []
  let raices = 0
  let raiz = null
  let resto = cuerpo
  const marca = /<(\/?)([A-Za-z_][\w.:-]*)((?:\s+[\w.:-]+\s*=\s*(?:"[^"<]*"|'[^'<]*'))*)\s*(\/?)>/y
  let i = 0
  while (i < resto.length) {
    const lt = resto.indexOf('<', i)
    const texto = resto.slice(i, lt === -1 ? resto.length : lt)
    if (/&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-f]+);)/i.test(texto)) return 'hay un & sin escapar'
    if (pila.length === 0 && texto.trim()) return 'hay texto fuera de la raíz'
    if (lt === -1) break
    marca.lastIndex = lt
    const m = marca.exec(resto)
    if (!m) return `etiqueta mal escrita cerca de «${resto.slice(lt, lt + 30)}»`
    const [, cierre, nombre, atributos, sola] = m
    if (cierre) {
      if (atributos.trim() || sola) return `cierre raro </${nombre}>`
      if (pila.pop() !== nombre) return `</${nombre}> no cierra la última etiqueta abierta`
    } else {
      if (pila.length === 0) {
        raices++
        raiz = { nombre, atributos }
      }
      if (!sola) pila.push(nombre)
    }
    i = marca.lastIndex
  }
  if (pila.length) return `quedan sin cerrar: ${pila.join(', ')}`
  if (raices !== 1) return `tiene ${raices} raíces, esperaba 1`
  if (raiz.nombre !== 'urlset' || !raiz.atributos.includes('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'))
    return 'la raíz no es <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
  return null
}
const sitemap = leer('sitemap.xml')
if (sitemap !== null) {
  const error = xmlBienFormado(sitemap)
  if (error) fallos.push(`sitemap.xml: ${error}`)
  const locs = [...sitemap.matchAll(/<loc>([^<]*)<\/loc>/g)].map((m) => m[1])
  const esperadas = RUTAS.map((r) => canonical(r.ruta))
  for (const url of esperadas) if (!locs.includes(url)) fallos.push(`sitemap.xml: falta <loc>${url}</loc>`)
  for (const url of locs) if (!esperadas.includes(url)) fallos.push(`sitemap.xml: sobra <loc>${url}</loc>`)
}
for (const { archivo } of RUTAS) leer(archivo)

// 404.html
const pagina = leer('404.html')
if (pagina !== null) {
  if (!/<html\b[^>]*\blang="es"/.test(pagina)) fallos.push('404.html: falta <html lang="es">')
  const robotsMeta = pagina.match(/<meta\b[^>]*\bname="robots"[^>]*>/)?.[0] ?? ''
  if (!/\bcontent="[^"]*noindex/.test(robotsMeta)) fallos.push('404.html: falta <meta name="robots" content="noindex">')
  if (!/<a\b[^>]*\bhref="\/"/.test(pagina)) fallos.push('404.html: no enlaza a la portada (href="/")')
  if (/<script\b/i.test(pagina)) fallos.push('404.html: lleva <script> y debe funcionar sin JavaScript')
  if (!/<title>[^<]+<\/title>/.test(pagina)) fallos.push('404.html: falta el <title>')
}

if (fallos.length) {
  console.error(`comprobar-public: ${fallos.length} fallo(s)`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log(`comprobar-public: robots.txt, sitemap.xml (${RUTAS.length} rutas), sus HTML y 404.html en orden`)
