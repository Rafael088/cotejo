// Comprueba, sin navegador, que la web elige bien la instalación de cada sistema:
// `node web/scripts/comprobar-sistema.mjs` (va en `npm run comprobar`). Prueba los navegadores
// que importan para la descarga y los que no tienen paquete (macOS, Android, iOS, uno raro).
import { sistemaDe } from '../src/sistema.js'

// Vite sustituye esta constante al compilar. En esta comprobación de Node basta un valor neutro
// para poder importar el mismo contrato que usa la interfaz.
globalThis.__COTEJO_VERSION__ = 'prueba'
const { COMANDOS, DESCARGAS } = await import('../src/config.js')

const CASOS = [
  [{ userAgentData: { platform: 'Linux' }, platform: 'Linux x86_64', userAgent: 'Mozilla/5.0 (X11; Linux x86_64)' }, 'linux'],
  [{ userAgentData: { platform: 'Windows' }, platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }, 'windows'],
  [{ platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }, 'windows'],
  [{ userAgentData: { platform: 'macOS' }, platform: 'MacIntel', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' }, 'otro'],
  [{ userAgentData: { platform: 'Android' }, platform: 'Linux armv8l', userAgent: 'Mozilla/5.0 (Linux; Android 14)' }, 'otro'],
  [{ platform: 'iPhone', userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)' }, 'otro'],
  [{}, 'otro'],
]

const fallos = []
for (const [nav, esperado] of CASOS) {
  const real = sistemaDe(nav)
  if (real !== esperado) {
    const pistas = JSON.stringify(nav)
    fallos.push(`${pistas}: dijo «${real}», esperaba «${esperado}»`)
  }
}

if (DESCARGAS.linux) fallos.push('Linux no debe ofrecer una descarga de paquete')
if (DESCARGAS.windows?.paquete !== 'Instalador .exe') {
  fallos.push('Windows debe ofrecer el instalador .exe')
}
if (!COMANDOS.linux.includes('/install.sh | sh')) {
  fallos.push('Linux debe instalarse con install.sh')
}

if (fallos.length) {
  console.error(`comprobar-sistema: ${fallos.length} fallo(s)`)
  for (const f of fallos) console.error(`  - ${f}`)
  process.exit(1)
}
console.log(`comprobar-sistema: ${CASOS.length} navegadores; Linux usa install.sh, Windows el .exe y el resto «otro»`)
