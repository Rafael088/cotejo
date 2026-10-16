// Comprueba la web en ancho de teléfono: `node web/scripts/comprobar-movil.mjs` después de
// `npm --prefix web run build` (o `npm run comprobar:movil` en web/). Sirve dist/ con un servidor
// node mínimo, abre Chromium headless a 390×844 y a 360×844, recorre la página entera (para que
// salgan las secciones que aparecen al hacer scroll), con Linux y con Windows elegidos, y falla si:
//   - document.documentElement.scrollWidth pasa del ancho (la página se mueve de lado);
//   - algún bloque de comando (.comando__linea) tiene scrollWidth > clientWidth (se corta y
//     hay que deslizarlo para leerlo entero).
// Cuando falla, lista los elementos que se salen por la derecha.
//
// Necesita un Chromium o Chrome instalado (no trae Playwright ni Puppeteer: habla con el
// navegador por el DevTools Protocol con el WebSocket de Node 22+). Busca chromium,
// chromium-browser, google-chrome y google-chrome-stable en el PATH; CHROMIUM=/ruta lo fija.
// Abre un solo navegador y lo cierra siempre, también si la prueba falla.
// CAPTURAS=/carpeta guarda movil-hero.png, movil-paso1.png y movil-instalar.png a 390.
import { createServer } from 'node:http'
import { spawn, execFileSync } from 'node:child_process'
import { readFile, mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, extname, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'

const dist = fileURLToPath(new URL('../dist/', import.meta.url))
const ANCHOS = process.env.ANCHOS ? process.env.ANCHOS.split(',').map(Number) : [390, 360]
const ALTO = 844
const capturas = process.env.CAPTURAS

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

const perfil = await mkdtemp(join(tmpdir(), 'cotejo-movil-'))
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

// ---------- Lo que se mide dentro de la página ----------

// Corre en la página: recorre todo para que aparezcan las secciones con animación al entrar.
const RECORRER = `(async () => {
  const paso = innerHeight * 0.6
  for (let y = 0; y < document.documentElement.scrollHeight; y += paso) {
    scrollTo(0, y)
    await new Promise((r) => setTimeout(r, 120))
  }
  scrollTo(0, 0)
  await new Promise((r) => setTimeout(r, 400))
})()`

const MEDIR = `(() => {
  const ancho = document.documentElement.clientWidth
  const describir = (el) => {
    let s = el.tagName.toLowerCase()
    if (el.id) s += '#' + el.id
    if (typeof el.className === 'string' && el.className.trim()) s += '.' + el.className.trim().split(/\\s+/).join('.')
    else if (el.className && el.className.baseVal) s += '.' + el.className.baseVal.trim().split(/\\s+/).join('.')
    return s
  }
  // Los que se salen por la derecha, quitando los que están dentro de otro que ya se sale.
  const fuera = []
  for (const el of document.body.querySelectorAll('*')) {
    const r = el.getBoundingClientRect()
    if (r.width === 0 && r.height === 0) continue
    if (r.right > ancho + 0.5) fuera.push([el, r.right])
  }
  const raices = fuera.filter(([el]) => !fuera.some(([otro]) => otro !== el && otro.contains(el)))
  const comandos = [...document.querySelectorAll('.comando__linea')]
    .filter((el) => el.getClientRects().length)
    .map((el) => ({ texto: el.textContent, scroll: el.scrollWidth, visible: el.clientWidth }))
  return {
    ancho,
    scrollWidth: document.documentElement.scrollWidth,
    fuera: raices.slice(0, 15).map(([el, right]) => describir(el) + ' → ' + Math.round(right * 10) / 10),
    comandos,
  }
})()`

const ELEGIR_WINDOWS = `(() => {
  for (const b of document.querySelectorAll('[role=tab]')) if (b.textContent.trim() === 'Windows') b.click()
  for (const b of document.querySelectorAll('.instalar button, .instalar [role=tab]')) if (b.textContent.trim() === 'Windows') b.click()
})()`

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
  await s('Page.enable')
  await s('Runtime.enable')

  for (const ancho of ANCHOS) {
    await s('Emulation.setDeviceMetricsOverride', { width: ancho, height: ALTO, deviceScaleFactor: 2, mobile: true })
    await s('Emulation.setTouchEmulationEnabled', { enabled: true })
    const cargada = new Promise((ok) => {
      const f = (m) => { if (m.method === 'Page.loadEventFired' && m.sessionId === sessionId) { oyentes.splice(oyentes.indexOf(f), 1); ok() } }
      oyentes.push(f)
    })
    await s('Page.navigate', { url: base })
    await cargada
    await evaluar('document.fonts.ready.then(() => true)')
    await espera(600)

    for (const sistema of ['Linux', 'Windows']) {
      if (sistema === 'Windows') { await evaluar(ELEGIR_WINDOWS); await espera(500) }
      await evaluar(RECORRER)
      const m = await evaluar(MEDIR)
      const etiqueta = `${ancho} px, ${sistema}`
      console.log(`${etiqueta}: scrollWidth ${m.scrollWidth} (ancho ${m.ancho})`)
      if (m.scrollWidth > m.ancho) {
        fallos.push(`${etiqueta}: la página mide ${m.scrollWidth} px de ancho, más que ${m.ancho}`)
        for (const f of m.fuera) console.log(`    se sale: ${f}`)
      }
      for (const c of m.comandos) {
        if (c.scroll > c.visible) fallos.push(`${etiqueta}: el comando «${c.texto}» se corta (${c.scroll} px en ${c.visible})`)
      }

      if (capturas && ancho === 390 && sistema === 'Linux') {
        await mkdir(capturas, { recursive: true })
        const piezas = [
          ['hero', '.hero'],
          ['cierre', '#cierre .instalar-rapido'],
          ['instalar', '#instalar'],
        ]
        for (const [nombre, selector] of piezas) {
          const caja = await evaluar(`(() => {
            const el = document.querySelector(${JSON.stringify(selector)})
            if (!el) return null
            el.scrollIntoView({ block: 'center' })
            const r = el.getBoundingClientRect()
            return { x: 0, y: Math.max(0, r.top + scrollY - 24), width: ${ancho}, height: Math.min(r.height + 48, 1600) }
          })()`)
          if (!caja) { console.log(`    (sin captura de ${nombre}: no hay ${selector})`); continue }
          await espera(500)
          const { data } = await s('Page.captureScreenshot', { format: 'png', clip: { ...caja, scale: 1 }, captureBeyondViewport: true })
          const ruta = join(capturas, `movil-${nombre}.png`)
          await writeFile(ruta, Buffer.from(data, 'base64'))
          console.log(`    captura: ${ruta}`)
        }
      }
    }
  }
} catch (e) {
  fallos.push(`la prueba no pudo correr: ${e.message}`)
} finally {
  await cerrar()
}

if (fallos.length) {
  console.error(`\ncomprobar-movil: ${fallos.length} fallo(s)`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log(`comprobar-movil: sin desborde horizontal y con los comandos enteros a ${ANCHOS.join(', ')} px`)
