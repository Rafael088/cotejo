// Comprueba el prerender sin navegador ni shell: `node web/scripts/comprobar-prerender.mjs`
// (o `npm run comprobar` en web/) después de `npm run build`. Lee dist/index.html, lo mismo que
// trae `curl https://cotejo.dev/`, y falla si:
//   - #root llega vacío o no hay un <h1> con texto;
//   - alguna <section> no tiene su título (el elemento de su aria-labelledby, con texto);
//   - el <h1> o algo de la sección del h1 (lo de arriba del pliegue) llega con opacity:0 en línea.
// No conoce los textos: vale igual cuando cambien o lleguen maquetaciones nuevas.
import { readFileSync } from 'node:fs'

const ruta = process.argv[2] || new URL('../dist/index.html', import.meta.url)
let html
try {
  html = readFileSync(ruta, 'utf8')
} catch {
  console.error(`No encuentro ${ruta}: corre antes «npm --prefix web run build».`)
  process.exit(1)
}

const fallos = []
const texto = (s) => s.replace(/<[^>]*>/g, ' ').replace(/&[a-z#0-9]+;/gi, ' ').replace(/\s+/g, ' ').trim()
const opacidadCero = /style="[^"]*opacity:\s*0(?:\.0+)?(?![.\d])/

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
if (titulos.length < 2) fallos.push(`Solo ${titulos.length} títulos de sección en el HTML`)

// Arriba del pliegue: la sección que contiene el h1, sin opacity:0 en línea.
if (h1) {
  const inicio = pagina.lastIndexOf('<section', pagina.indexOf(h1[0]))
  const fin = pagina.indexOf('</section>', pagina.indexOf(h1[0]))
  const pliegue = inicio >= 0 && fin > 0 ? pagina.slice(inicio, fin) : h1[0]
  if (opacidadCero.test(pliegue)) fallos.push('Algo de la sección del <h1> arranca en opacity:0 en línea')
}

if (fallos.length) {
  console.error(`prerender: MAL (${ruta})`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log(`prerender: bien. h1: «${texto(h1[2])}»`)
for (const t of titulos) console.log(`  sección: «${t}»`)
