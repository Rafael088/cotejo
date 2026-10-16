import Cabecera from './components/Cabecera.jsx'
import Pie from './components/Pie.jsx'
import { PAGINAS } from './paginas.js'

export default function App({ ruta }) {
  const Pagina = PAGINAS[ruta]
  return (
    <>
      <a className="saltar" href="#contenido">Saltar al contenido</a>
      <Cabecera ruta={ruta} />
      <main id="contenido">
        <Pagina />
      </main>
      <Pie />
    </>
  )
}
