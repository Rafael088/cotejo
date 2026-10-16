// La Content-Security-Policy de la web, en un solo sitio. GitHub Pages no deja poner cabeceras,
// así que va como <meta http-equiv="Content-Security-Policy">, y por meta no valen
// frame-ancestors, report-uri, report-to ni sandbox (Chromium avisa en consola): no se ponen.
//
// La mete scripts/prerender.mjs en dist/index.html y dist/404.html al final del build, cuando el
// HTML ya no cambia (la versión del JSON-LD ya está sustituida y el prerender ya está dentro), y
// los hashes sha256 de los <script> y <style> en línea se calculan sobre ese HTML final.
// En `vite dev` no hay CSP: el HMR de Vite mete scripts y estilos en línea y la rompería.
// La vigila scripts/comprobar-csp.mjs (en `npm run comprobar`) y, con navegador,
// scripts/comprobar-consola.mjs.
import { createHash } from 'node:crypto'

// Tipos de <script> que el navegador no ejecuta (bloques de datos, como el JSON-LD): la CSP
// no se les aplica, así que no llevan hash.
const DATOS = /^(application\/(ld\+)?json|application\/json|text\/plain)$/i

const hash = (texto) => `'sha256-${createHash('sha256').update(texto, 'utf8').digest('base64')}'`

// Los <script> sin src que se ejecutan y los <style>, con su contenido exacto.
export function enLinea(html) {
  const scripts = []
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const attrs = m[1]
    if (/\bsrc\s*=/i.test(attrs)) continue
    const tipo = attrs.match(/\btype\s*=\s*["']?([^"'\s>]+)/i)?.[1]
    if (tipo && DATOS.test(tipo)) continue
    scripts.push(m[2])
  }
  const estilos = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1])
  return { scripts, estilos }
}

export const hashDe = hash

// Portada: la app de Vite (JS y CSS propios desde 'self') y fuentes @fontsource locales.
//   script-src: 'self' y el hash del script que pone .js en <html> antes de pintar. Nunca
//     'unsafe-inline'.
//   style-src 'self' + style-src-attr 'unsafe-inline': el HTML prerenderizado trae atributos
//     style= (el estado inicial de Motion, opacity:0 y transform, y variables como --retraso y
//     --lleno). Un atributo style= en el HTML solo se aplica con 'unsafe-inline' (no admite
//     hash); sin él la consola se llena de violaciones. Se abre solo para atributos: los
//     <style> y las hojas siguen limitadas a 'self'. Lo que Motion cambia después lo hace por
//     CSSOM (element.style), que la CSP no bloquea. No hay CSS de terceros.
//   connect-src 'self': el polyfill de modulepreload de Vite hace fetch() a /assets/ en
//     navegadores sin modulepreload. Nada más pide datos.
export function cspPortada(html) {
  const { scripts, estilos } = enLinea(html)
  return [
    "default-src 'self'",
    ["script-src 'self'", ...scripts.map(hash)].join(' '),
    ["style-src 'self'", ...estilos.map(hash)].join(' '),
    "style-src-attr 'unsafe-inline'",
    "img-src 'self'",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'none'",
  ].join('; ')
}

// 404: estática, sin JavaScript ni fuentes descargadas; solo su <style> (por hash) y el favicon.
export function csp404(html) {
  const { scripts, estilos } = enLinea(html)
  if (scripts.length) throw new Error('404.html no debería llevar <script>')
  return [
    "default-src 'none'",
    ["style-src", ...estilos.map(hash)].join(' '),
    "img-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ')
}

// Mete la meta justo después de <meta charset>: la CSP por meta solo vale para lo que viene
// detrás, así que tiene que ir antes de cualquier <script>, <style> o <link>.
export function meterCsp(html, politica) {
  if (html.includes('http-equiv="Content-Security-Policy"')) throw new Error('el HTML ya trae una CSP')
  const charset = html.match(/<meta charset="utf-8"\s*\/?>/i)
  if (!charset) throw new Error('no encontré <meta charset="utf-8">')
  const meta = `<meta http-equiv="Content-Security-Policy" content="${politica}" />`
  return html.replace(charset[0], () => `${charset[0]}\n    ${meta}`)
}
