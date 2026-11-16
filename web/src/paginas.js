import Inicio from './paginas/Inicio.jsx'
import Introduccion from './paginas/docs/Introduccion.jsx'
import PrimerosPasos from './paginas/docs/PrimerosPasos.jsx'
import Board from './paginas/docs/Board.jsx'
import Maestro from './paginas/docs/Maestro.jsx'
import Enrutador from './paginas/docs/Enrutador.jsx'
import Agentes from './paginas/docs/Agentes.jsx'
import Almacen from './paginas/docs/Almacen.jsx'
import Tokens from './paginas/docs/Tokens.jsx'
import Fuentes from './paginas/docs/Fuentes.jsx'
import Cli from './paginas/docs/Cli.jsx'
import Configuracion from './paginas/docs/Configuracion.jsx'

// El componente de cada ruta de rutas.js. Falta uno y el build se cae en el prerender.
export const PAGINAS = {
  '/': Inicio,
  '/docs': Introduccion,
  '/docs/primeros-pasos': PrimerosPasos,
  '/docs/board': Board,
  '/docs/maestro': Maestro,
  '/docs/enrutador': Enrutador,
  '/docs/agentes': Agentes,
  '/docs/almacen': Almacen,
  '/docs/tokens': Tokens,
  '/docs/fuentes': Fuentes,
  '/docs/cli': Cli,
  '/docs/configuracion': Configuracion,
}

export { enlace } from './enlace.js'
