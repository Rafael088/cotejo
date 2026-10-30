// Comprueba el prerender sin navegador ni shell: `node web/scripts/comprobar-prerender.mjs`
// (o `npm run comprobar` en web/) después de `npm run build`. Lee el HTML de cada ruta de
// src/rutas.js en dist/ (lo mismo que trae `curl https://cotejo.dev/comofunciona`) y falla si:
//   - #root llega vacío o no hay un <h1> con texto;
//   - alguna <section> no tiene su título (el elemento de su aria-labelledby, con texto);
//   - el <h1> o algo de la sección del h1 (lo de arriba del pliegue) llega con opacity:0 en línea;
//   - en cualquier ruta, el h1 no es el de EXIGIDAS o falta alguna de sus secciones exigidas con
//     su titular exacto, o llega con opacity:0 en línea;
//   - dos rutas traen el mismo <h1> (el prerender pintó la misma página en todas).
// Fuera de EXIGIDAS no conoce los textos.
import { readFileSync } from 'node:fs'
import { RUTAS } from '../src/rutas.js'

// Lo que cada ruta tiene que traer en el HTML: su h1 y sus secciones (por id de la <section> o,
// si no lleva, por el id de su aria-labelledby) con el h2 exacto. Los textos son los de dist/.
const EXIGIDAS = {
  '/': {
    h1: 'El tablero de control para tu vibe coding.',
    secciones: [
      ['pasos', 'De cero a tu primera entrega.'],
      ['ahorro-inicio', 'Tu agente lee 480 tokens, no 4.700.'],
      ['puertas', 'Programes o no, el check es tuyo.'],
      ['cierre', 'Instálalo y pregúntale a tu agente qué falta.'],
    ],
  },
  '/comofunciona': {
    h1: 'Cómo funciona.',
    secciones: [['empieza', 'Instálalo y crea tu primer proyecto.']],
  },
  '/primerospasos': {
    h1: 'Primeros pasos.',
    secciones: [
      ['t-dia1', 'El primer día.'],
      ['t-cada', 'Cada día.'],
    ],
  },
  '/tokens': {
    h1: 'Tu agente lee 480 tokens, no 4.700.',
    secciones: [
      ['t-versus', 'La nota entera contra la respuesta de Cotejo'],
      ['t-medido', 'menos texto leído, medido con cotejo ahorro en la máquina del autor.'],
      ['t-cerebro', '¿Tu proyecto vive en tu segundo cerebro?'],
      ['cierre-tokens', 'Mídelo en tu propio proyecto.'],
    ],
  },
}

const texto = (s) => s.replace(/<[^>]*>/g, ' ').replace(/&[a-z#0-9]+;/gi, ' ').replace(/\s+/g, ' ').trim()
const opacidadCero = /style="[^"]*opacity:\s*0(?:\.0+)?(?![.\d])/

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
  return { h1: h1 ? texto(h1[2]) : '', titulos }
}

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
if (mal) process.exit(1)
