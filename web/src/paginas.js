import Inicio from './paginas/Inicio.jsx'
import ComoFunciona from './paginas/ComoFunciona.jsx'
import PrimerosPasos from './paginas/PrimerosPasos.jsx'
import Tokens from './paginas/Tokens.jsx'

// El componente de cada ruta de rutas.js. Falta uno y el build se cae en el prerender.
export const PAGINAS = {
  '/': Inicio,
  '/comofunciona': ComoFunciona,
  '/primerospasos': PrimerosPasos,
  '/tokens': Tokens,
}

// El href de una ruta con la base de Vite (/ con dominio, /cotejo/ sin él). Son enlaces de
// verdad, a otra página prerenderizada: navegan sin JavaScript.
export const enlace = (ruta) => `${import.meta.env.BASE_URL}${ruta.slice(1)}`
