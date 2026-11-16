// Segundo paso de `npm run build`: de dist/index.html (la plantilla que deja Vite) saca un HTML
// por cada ruta de src/rutas.js, con la página renderizada desde src con el SSR de Vite
// (vite build --ssr src/entrada-servidor.jsx) y su propio <head>: título, descripción,
// canonical, og:* y twitter:*. Así quien no corre JavaScript (curl, buscadores, vistas previas)
// ve el texto real de cada página; main.jsx luego hidrata la que toque.
// No hay textos copiados a mano: lo que haya en src es lo que sale. También escribe el sitemap
// con las mismas rutas, para que no se desfasen.
import { readFileSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { cspPortada, csp404, meterCsp } from './csp.mjs'

const web = fileURLToPath(new URL('..', import.meta.url))
const dist = `${web}dist/`
const servidor = `${web}.prerender`

const { renderizar, RUTAS, REDIRECCIONES, canonical } = await import(pathToFileURL(`${servidor}/entrada-servidor.js`).href)

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
  mkdirSync(dirname(`${dist}${r.archivo}`), { recursive: true })
  writeFileSync(`${dist}${r.archivo}`, meterCsp(html, cspPortada(html)))
  console.log(`prerender: dist/${r.archivo} (${r.ruta}) con ${pagina.length} caracteres de HTML y su CSP`)
}
rmSync(servidor, { recursive: true, force: true })

// Las páginas de antes: HTML estático y autónomo (como la 404: sin JavaScript, solo su <style> con
// hash) que manda a su equivalente en /docs con <meta http-equiv="refresh">, canonical al destino
// y un enlace visible para quien no sigue la redirección. Fuera del sitemap. La CSP no frena el
// refresh por meta (no hay directiva que lo gobierne), así que se queda la misma que la 404.
const base = process.env.BASE || '/'
const paginaRedireccion = ({ destino }) => `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark" />
  <meta name="theme-color" content="#101114" />
  <title>Esta página se mudó · Cotejo</title>
  <meta http-equiv="refresh" content="0; url=${base}${destino.slice(1)}" />
  <link rel="canonical" href="${canonical(destino)}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <style>
    :root { --fondo: #101114; --texto: #ffffff; --texto-chip: #d6d9df; --tenue: #a8acb6; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-content: center; padding: 24px; background: var(--fondo); color: var(--texto-chip); font: 400 17px/1.6 'Inter Variable', 'Inter', ui-sans-serif, system-ui, sans-serif; }
    p { margin: 0; max-width: 46ch; }
    a { color: var(--texto); text-underline-offset: 0.2em; }
    .t { margin-bottom: 8px; font: 600 24px/1.2 'Sora Variable', 'Sora', ui-sans-serif, system-ui, sans-serif; color: var(--texto); }
  </style>
</head>
<body>
  <p class="t">Esta página se mudó.</p>
  <p>Ahora vive en <a href="${base}${destino.slice(1)}">cotejo.dev${destino}</a>. Si no te lleva sola, entra desde ese enlace.</p>
</body>
</html>
`
for (const r of REDIRECCIONES) {
  const html = paginaRedireccion(r)
  mkdirSync(dirname(`${dist}${r.archivo}`), { recursive: true })
  writeFileSync(`${dist}${r.archivo}`, meterCsp(html, csp404(html)))
  console.log(`prerender: dist/${r.archivo} (${r.ruta}) redirige a ${r.destino}`)
}

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
