// Segundo paso de `npm run build`: mete en dist/index.html el HTML de la página, renderizado
// desde src con el SSR de Vite (vite build --ssr src/entrada-servidor.jsx). Así quien no corre
// JavaScript (curl, buscadores, vistas previas) ve el texto real; main.jsx luego hidrata.
// No hay textos copiados a mano: lo que haya en src es lo que sale.
import { readFileSync, writeFileSync, rmSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'

const web = fileURLToPath(new URL('..', import.meta.url))
const indice = `${web}dist/index.html`
const servidor = `${web}.prerender`

const { renderizar } = await import(pathToFileURL(`${servidor}/entrada-servidor.js`).href)
const pagina = renderizar()
if (!pagina.includes('<h1')) throw new Error('El prerender no produjo ningún <h1>')

const html = readFileSync(indice, 'utf8')
const vacio = '<div id="root"></div>'
if (!html.includes(vacio)) throw new Error(`No encontré ${vacio} en dist/index.html`)
writeFileSync(indice, html.replace(vacio, () => `<div id="root">${pagina}</div>`))
rmSync(servidor, { recursive: true, force: true })
console.log(`prerender: dist/index.html con ${pagina.length} caracteres de HTML`)
