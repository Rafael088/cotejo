import { createRoot, hydrateRoot } from 'react-dom/client'
import '@fontsource-variable/sora'
import '@fontsource-variable/inter'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './styles.css'
import Raiz from './Raiz.jsx'

// `npm run build` deja la página ya renderizada dentro de #root (scripts/prerender.mjs):
// aquí se hidrata. En `npm run dev` #root llega vacío y se monta de cero.
const raiz = document.getElementById('root')
if (raiz.firstElementChild) hydrateRoot(raiz, <Raiz />)
else createRoot(raiz).render(<Raiz />)
