import { renderToString } from 'react-dom/server'
import Raiz from './Raiz.jsx'

// Lo usa scripts/prerender.mjs en el build: la página entera a HTML, sin navegador.
export function renderizar() {
  return renderToString(<Raiz />)
}
