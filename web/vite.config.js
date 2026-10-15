import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// La versión que enseña la web sale de tareas.__version__, la única que hay: escrita a mano
// aquí se quedó en 1.0 cuando ya había salido la 1.1. Solo «mayor.menor» (1.1, no 1.1.0).
const init = readFileSync(new URL('../tareas/__init__.py', import.meta.url), 'utf8')
const completa = init.match(/^__version__ = "([^"]+)"/m)?.[1]
if (!completa) throw new Error('No encontré __version__ en tareas/__init__.py')
const version = completa.split('.').slice(0, 2).join('.')

// En GitHub Pages sin dominio la web vive en /cotejo/; con dominio propio, en la raíz.
// publicar.sh pasa BASE según el caso.
export default defineConfig({
  plugins: [react()],
  base: process.env.BASE || '/',
  define: { __COTEJO_VERSION__: JSON.stringify(version) },
})
