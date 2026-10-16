// Segundo paso de `npm run build`: de dist/index.html (la plantilla que deja Vite) saca un HTML
// por cada ruta de src/rutas.js, con la página renderizada desde src con el SSR de Vite
// (vite build --ssr src/entrada-servidor.jsx) y su propio <head>: título, descripción,
// canonical, og:* y twitter:*. Así quien no corre JavaScript (curl, buscadores, vistas previas)
// ve el texto real de cada página; main.jsx luego hidrata la que toque.
// No hay textos copiados a mano: lo que haya en src es lo que sale. También escribe el sitemap
// con las mismas rutas, para que no se desfasen.
import { readFileSync, writeFileSync, rmSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { cspPortada, csp404, meterCsp } from './csp.mjs'

const web = fileURLToPath(new URL('..', import.meta.url))
const dist = `${web}dist/`
const servidor = `${web}.prerender`

const { renderizar, RUTAS, canonical } = await import(pathToFileURL(`${servidor}/entrada-servidor.js`).href)

const plantilla = readFileSync(`${dist}index.html`, 'utf8')
const vacio = '<div id="root"></div>'
if (!plantilla.includes(vacio)) throw new Error(`No encontré ${vacio} en dist/index.html`)

const atributo = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// Cambia un valor del <head> de la plantilla; si no está, la plantilla cambió y hay que mirarlo.
function cambiar(html, patron, nuevo, que) {
  if (!patron.test(html)) throw new Error(`La plantilla no trae ${que}`)
  return html.replace(patron, () => nuevo)
}
const meta = (clave) => new RegExp(`<meta (name|property)="${clave}" content="[^"]*" />`)

function cabeza(html, { ruta, titulo, descripcion }) {
  const url = canonical(ruta)
  html = cambiar(html, /<title>[^<]*<\/title>/, `<title>${atributo(titulo)}</title>`, '<title>')
  html = cambiar(html, /<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`, 'el canonical')
  for (const [clave, valor] of [
    ['description', descripcion],
    ['og:url', url],
    ['og:title', titulo],
    ['og:description', descripcion],
    ['twitter:title', titulo],
    ['twitter:description', descripcion],
  ]) {
    const patron = meta(clave)
    if (!patron.test(html)) throw new Error(`La plantilla no trae <meta> ${clave}`)
    html = html.replace(patron, (_, tipo) => `<meta ${tipo}="${clave}" content="${atributo(valor)}" />`)
  }
  return html
}

for (const r of RUTAS) {
  const pagina = renderizar(r.ruta)
  if (!pagina.includes('<h1')) throw new Error(`El prerender de ${r.ruta} no produjo ningún <h1>`)
  const html = cabeza(plantilla, r).replace(vacio, () => `<div id="root">${pagina}</div>`)
  // Último paso: la CSP, con los hashes calculados sobre el HTML ya terminado (scripts/csp.mjs).
  writeFileSync(`${dist}${r.archivo}`, meterCsp(html, cspPortada(html)))
  console.log(`prerender: dist/${r.archivo} (${r.ruta}) con ${pagina.length} caracteres de HTML y su CSP`)
}
rmSync(servidor, { recursive: true, force: true })

const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...RUTAS.map((r) => `  <url>\n    <loc>${canonical(r.ruta)}</loc>\n  </url>`),
  '</urlset>',
  '',
].join('\n')
writeFileSync(`${dist}sitemap.xml`, sitemap)
console.log(`prerender: dist/sitemap.xml con ${RUTAS.length} rutas`)

const pagina404 = `${dist}404.html`
const html404 = readFileSync(pagina404, 'utf8')
writeFileSync(pagina404, meterCsp(html404, csp404(html404)))
console.log('prerender: CSP puesta en dist/404.html')
