// Comprueba que la web carga sin mensajes en la consola: `node web/scripts/comprobar-consola.mjs`
// después de `npm --prefix web run build` (o `npm run comprobar:consola` en web/). Sirve dist/
// con un servidor node mínimo, abre Chromium headless y carga cada ruta de src/rutas.js y la 404 a 1440×900
// (escritorio) y 390×844 (teléfono); en la portada recorre la página entera (para que corran
// las animaciones de Motion al entrar cada sección) y elige Windows en los selectores. Falla si
// sale cualquier cosa de nivel error o warning:
//   - Log.entryAdded (lo que escribe el propio navegador: violaciones de CSP, recursos que no
//     cargan, avisos de meta que no valen);
//   - Runtime.consoleAPICalled (console.error/warn/assert de la página);
//   - Runtime.exceptionThrown (excepciones sin capturar);
//   - eventos securitypolicyviolation (escuchados desde un script que mete el DevTools antes
//     de que cargue la página, al que la CSP no afecta).
// La CSP la pone el build (scripts/csp.mjs); la comprobación sin navegador es comprobar-csp.mjs.
//
// Como comprobar-movil.mjs: sin Playwright ni Puppeteer, habla con Chromium o Chrome por el
// DevTools Protocol con el WebSocket de Node 22+ (CHROMIUM=/ruta lo fija). Un solo navegador,
// que se cierra siempre, también si la prueba falla.
import { createServer } from 'node:http'
import { spawn, execFileSync } from 'node:child_process'
import { readFile, mkdtemp, rm } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, extname, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { RUTAS } from '../src/rutas.js'

const dist = fileURLToPath(new URL('../dist/', import.meta.url))

if (!existsSync(join(dist, 'index.html'))) {
  console.error('No encuentro web/dist/index.html: corre antes «npm --prefix web run build».')
  process.exit(1)
}

function buscarNavegador() {
  if (process.env.CHROMIUM) return process.env.CHROMIUM
  for (const nombre of ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable']) {
    try {
      return execFileSync('which', [nombre], { encoding: 'utf8' }).trim()
    } catch {}
  }
  return null
}

const navegador = buscarNavegador()
if (!navegador) {
  console.error('No encuentro Chromium ni Chrome. Instala uno o pasa CHROMIUM=/ruta/al/navegador.')
  process.exit(2)
}

// ---------- Servidor de dist/ ----------

const TIPOS = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
  '.json': 'application/json',
  '.txt': 'text/plain',
  '.xml': 'application/xml',
}

const servidor = createServer(async (pet, res) => {
  let ruta = decodeURIComponent(new URL(pet.url, 'http://x').pathname)
  if (ruta.endsWith('/')) ruta += 'index.html'
  // Como GitHub Pages: /comofunciona se sirve desde comofunciona.html.
  else if (!extname(ruta)) ruta += '.html'
  const archivo = normalize(join(dist, ruta))
  if (!archivo.startsWith(dist)) return res.writeHead(403).end()
  try {
    const cuerpo = await readFile(archivo)
    res.writeHead(200, { 'content-type': TIPOS[extname(archivo)] || 'application/octet-stream' })
    res.end(cuerpo)
  } catch {
    res.writeHead(404).end()
  }
})
await new Promise((ok) => servidor.listen(0, '127.0.0.1', ok))
const base = `http://127.0.0.1:${servidor.address().port}/`

// ---------- Navegador y DevTools Protocol ----------

const perfil = await mkdtemp(join(tmpdir(), 'cotejo-consola-'))
const proceso = spawn(
  navegador,
  [
    '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${perfil}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--disable-extensions',
    '--hide-scrollbars',
    '--mute-audio',
    'about:blank',
  ],
  { stdio: ['ignore', 'ignore', 'pipe'] },
)

let cerrado = false
async function cerrar() {
  if (cerrado) return
  cerrado = true
  try { proceso.kill('SIGKILL') } catch {}
  servidor.close()
  await rm(perfil, { recursive: true, force: true }).catch(() => {})
}
for (const senal of ['SIGINT', 'SIGTERM']) {
  process.on(senal, async () => { await cerrar(); process.exit(130) })
}

const espera = (ms) => new Promise((ok) => setTimeout(ok, ms))

function urlDevtools() {
  return new Promise((ok, mal) => {
    let texto = ''
    const reloj = setTimeout(() => mal(new Error('Chromium no abrió el DevTools en 20 s')), 20000)
    proceso.stderr.on('data', (trozo) => {
      texto += trozo
      const m = texto.match(/DevTools listening on (ws:\/\/\S+)/)
      if (m) { clearTimeout(reloj); ok(m[1]) }
    })
    proceso.on('exit', (codigo) => { clearTimeout(reloj); mal(new Error(`Chromium salió (${codigo}): ${texto.slice(-400)}`)) })
  })
}

async function conectar(url) {
  const ws = new WebSocket(url)
  await new Promise((ok, mal) => { ws.onopen = ok; ws.onerror = () => mal(new Error('No pude conectar al DevTools')) })
  let n = 0
  const pendientes = new Map()
  const oyentes = []
  ws.onmessage = (e) => {
    const msj = JSON.parse(e.data)
    if (msj.id && pendientes.has(msj.id)) {
      const { ok, mal } = pendientes.get(msj.id)
      pendientes.delete(msj.id)
      msj.error ? mal(new Error(msj.error.message)) : ok(msj.result)
    } else if (msj.method) {
      for (const f of oyentes) f(msj)
    }
  }
  const enviar = (method, params = {}, sessionId) =>
    new Promise((ok, mal) => {
      const id = ++n
      pendientes.set(id, { ok, mal })
      ws.send(JSON.stringify({ id, method, params, sessionId }))
    })
  return { ws, enviar, oyentes }
}

// ---------- Lo que se hace dentro de la página ----------

const RECORRER = `(async () => {
  const paso = innerHeight * 0.6
  for (let y = 0; y < document.documentElement.scrollHeight; y += paso) {
    scrollTo(0, y)
    await new Promise((r) => setTimeout(r, 120))
  }
  scrollTo(0, 0)
  await new Promise((r) => setTimeout(r, 400))
})()`

const ELEGIR_WINDOWS = `(() => {
  for (const b of document.querySelectorAll('[role=tab]')) if (b.textContent.trim() === 'Windows') b.click()
})()`

// Se mete antes de cada carga; guarda las violaciones de CSP para leerlas al final.
const ESCUCHAR_CSP = `window.__violaciones = []
document.addEventListener('securitypolicyviolation', (e) => {
  window.__violaciones.push(e.violatedDirective + ' ← ' + (e.blockedURI || 'en línea') + (e.sample ? ' «' + e.sample + '»' : ''))
})`

const PAGINAS = [
  ['portada', ''],
  ...RUTAS.filter((r) => r.ruta !== '/').map((r) => [r.ruta, r.ruta.slice(1)]),
  ['404', '404.html'],
]
const VISTAS = [
  [1440, 900, false],
  [390, 844, true],
]

// ---------- La prueba ----------

const fallos = []
try {
  const { enviar, oyentes } = await conectar(await urlDevtools())
  const { targetId } = await enviar('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await enviar('Target.attachToTarget', { targetId, flatten: true })
  const s = (m, p) => enviar(m, p, sessionId)
  const evaluar = async (expr) => {
    const r = await s('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
    return r.result.value
  }

  // Todo lo que llegue mientras se mira una página va a `mensajes`.
  let mensajes = []
  oyentes.push((m) => {
    if (m.sessionId !== sessionId) return
    const p = m.params
    if (m.method === 'Log.entryAdded' && ['error', 'warning'].includes(p.entry.level))
      mensajes.push(`[${p.entry.source} ${p.entry.level}] ${p.entry.text}${p.entry.url ? ` (${p.entry.url})` : ''}`)
    else if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning', 'assert'].includes(p.type))
      mensajes.push(`[console.${p.type}] ${p.args.map((a) => a.value ?? a.description ?? '').join(' ')}`)
    else if (m.method === 'Runtime.exceptionThrown')
      mensajes.push(`[excepción] ${p.exceptionDetails.exception?.description || p.exceptionDetails.text}`)
  })

  await s('Page.enable')
  await s('Runtime.enable')
  await s('Log.enable')
  await s('Page.addScriptToEvaluateOnNewDocument', { source: ESCUCHAR_CSP })

  for (const [ancho, alto, movil] of VISTAS) {
    await s('Emulation.setDeviceMetricsOverride', { width: ancho, height: alto, deviceScaleFactor: movil ? 2 : 1, mobile: movil })
    await s('Emulation.setTouchEmulationEnabled', { enabled: movil })
    for (const [nombre, ruta] of PAGINAS) {
      mensajes = []
      const cargada = new Promise((ok) => {
        const f = (m) => { if (m.method === 'Page.loadEventFired' && m.sessionId === sessionId) { oyentes.splice(oyentes.indexOf(f), 1); ok() } }
        oyentes.push(f)
      })
      await s('Page.navigate', { url: base + ruta })
      await cargada
      await evaluar('document.fonts.ready.then(() => true)')
      await espera(600)
      if (nombre === 'portada') {
        await evaluar(RECORRER)
        await evaluar(ELEGIR_WINDOWS)
        await espera(500)
        await evaluar(RECORRER)
      }
      await espera(500)
      const violaciones = await evaluar('window.__violaciones || []')
      for (const v of violaciones) mensajes.push(`[securitypolicyviolation] ${v}`)
      const etiqueta = `${nombre} a ${ancho} px`
      if (mensajes.length) {
        fallos.push(`${etiqueta}: ${mensajes.length} mensaje(s) en la consola`)
        for (const t of [...new Set(mensajes)].slice(0, 20)) console.log(`    ${etiqueta}: ${t}`)
      } else {
        console.log(`${etiqueta}: consola limpia`)
      }
    }
  }
} catch (e) {
  fallos.push(`la prueba no pudo correr: ${e.message}`)
} finally {
  await cerrar()
}

if (fallos.length) {
  console.error(`\ncomprobar-consola: ${fallos.length} fallo(s)`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log(`comprobar-consola: las ${RUTAS.length} rutas y la 404 sin errores, avisos ni violaciones de CSP a 1440 y 390 px`)
