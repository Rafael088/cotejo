import { createRoot, hydrateRoot } from 'react-dom/client'
import '@fontsource-variable/sora'
import '@fontsource-variable/inter'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './styles.css'
import Raiz from './Raiz.jsx'
import { rutaDe } from './rutas.js'

// `npm run build` deja la página ya renderizada dentro de #root (scripts/prerender.mjs):
// aquí se hidrata, con la misma ruta que se prerenderizó. En `npm run dev` #root llega vacío y se
// monta de cero (Vite sirve index.html para /comofunciona y las demás).
const raiz = document.getElementById('root')
const ruta = rutaDe(location.pathname, import.meta.env.BASE_URL)
if (raiz.firstElementChild) hydrateRoot(raiz, <Raiz ruta={ruta} />)
else createRoot(raiz).render(<Raiz ruta={ruta} />)
