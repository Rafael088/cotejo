import { renderToString } from 'react-dom/server'
import Raiz from './Raiz.jsx'

export { RUTAS, SITIO, canonical } from './rutas.js'

// Lo usa scripts/prerender.mjs en el build: la página de una ruta a HTML, sin navegador.
export function renderizar(ruta) {
  return renderToString(<Raiz ruta={ruta} />)
}
