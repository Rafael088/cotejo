// Comprueba la Content-Security-Policy del build sin navegador:
// `node web/scripts/comprobar-csp.mjs` después de `npm --prefix web run build` (va en
// `npm run comprobar`). Lee dist/index.html y dist/404.html y falla si:
//   - no hay exactamente una <meta http-equiv="Content-Security-Policy">, o no va antes de
//     cualquier <script>, <style> o <link> (por meta solo vale para lo que viene detrás);
//   - script-src (o default-src, si falta script-src) admite 'unsafe-inline', 'unsafe-eval',
//     data: o *; o falta object-src 'none' o base-uri;
//   - algún <script> en línea que se ejecuta (no el JSON-LD) o algún <style> no tiene su hash
//     sha256 en la política, o la política trae un hash que ya no corresponde a nada;
//   - aparece frame-ancestors, report-uri, report-to o sandbox (por meta no valen y avisan);
//   - falta <meta name="referrer" content="strict-origin-when-cross-origin">.
// La política sale de scripts/csp.mjs; esta comprobación no la reconstruye: la lee del HTML.
import { readFileSync } from 'node:fs'
import { enLinea, hashDe } from './csp.mjs'

const dist = new URL('../dist/', import.meta.url)
const fallos = []

function revisar(nombre, { estilosPorHash }) {
  let html
  try {
    html = readFileSync(new URL(nombre, dist), 'utf8')
  } catch {
    fallos.push(`falta dist/${nombre}: ¿corriste «npm --prefix web run build»?`)
    return
  }
  const metas = [...html.matchAll(/<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"[^>]*>/gi)]
  if (metas.length !== 1) {
    fallos.push(`${nombre}: ${metas.length} metas de CSP (tiene que haber una)`)
    return
  }
  const pos = metas[0].index
  const primero = html.search(/<(script|style|link)\b/i)
  if (primero !== -1 && primero < pos) fallos.push(`${nombre}: la CSP va después de un <script>, <style> o <link>`)

  const directivas = new Map()
  for (const trozo of metas[0][1].split(';')) {
    const [d, ...valores] = trozo.trim().split(/\s+/)
    if (d) directivas.set(d.toLowerCase(), valores)
  }
  for (const d of ['frame-ancestors', 'report-uri', 'report-to', 'sandbox'])
    if (directivas.has(d)) fallos.push(`${nombre}: «${d}» no vale por meta`)
  const script = directivas.get('script-src') ?? directivas.get('default-src') ?? []
  for (const prohibido of ["'unsafe-inline'", "'unsafe-eval'", 'data:', '*'])
    if (script.includes(prohibido)) fallos.push(`${nombre}: script-src admite ${prohibido}`)
  if (!(directivas.get('object-src') ?? directivas.get('default-src') ?? []).includes("'none'"))
    fallos.push(`${nombre}: falta object-src 'none'`)
  if (!directivas.has('base-uri')) fallos.push(`${nombre}: falta base-uri`)
  if ((directivas.get('style-src') ?? []).includes("'unsafe-inline'"))
    fallos.push(`${nombre}: style-src admite 'unsafe-inline' (solo se permite en style-src-attr)`)

  const { scripts, estilos } = enLinea(html)
  const hashesScript = new Set((directivas.get('script-src') ?? []).filter((v) => v.startsWith("'sha256-")))
  const hashesEstilo = new Set((directivas.get('style-src') ?? []).filter((v) => v.startsWith("'sha256-")))
  for (const s of scripts) {
    const h = hashDe(s)
    if (!hashesScript.delete(h)) fallos.push(`${nombre}: el script en línea «${s.trim().slice(0, 50)}» no tiene su hash (${h})`)
  }
  for (const h of hashesScript) fallos.push(`${nombre}: script-src trae ${h}, que no es de ningún script`)
  for (const s of estilos) {
    const h = hashDe(s)
    if (estilosPorHash && !hashesEstilo.delete(h)) fallos.push(`${nombre}: el <style> en línea no tiene su hash (${h})`)
  }
  for (const h of hashesEstilo) fallos.push(`${nombre}: style-src trae ${h}, que no es de ningún <style>`)

  if (!/<meta\s+name="referrer"\s+content="strict-origin-when-cross-origin"/i.test(html))
    fallos.push(`${nombre}: falta <meta name="referrer" content="strict-origin-when-cross-origin">`)

  if (!fallos.some((f) => f.startsWith(nombre)))
    console.log(`${nombre}: ${metas[0][1]}`)
}

revisar('index.html', { estilosPorHash: true })
revisar('404.html', { estilosPorHash: true })

if (fallos.length) {
  console.error(`\ncomprobar-csp: ${fallos.length} fallo(s)`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log('comprobar-csp: CSP por meta en la portada y la 404, sin \'unsafe-inline\' en script-src y con los hashes al día')
