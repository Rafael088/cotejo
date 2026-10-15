import { Logo } from './Logo.jsx'
import Icono from './Icono.jsx'
import { CONTACTO, DONAR, LICENCIA, RELEASES, VERSION } from '../config.js'

export default function Pie() {
  return (
    <footer className="pie">
      <div className="pie__cierre">
        <Logo alto={44} />
        <p className="pie__frase">Tus agentes entregan. Tú compruebas.</p>
      </div>
      <div className="pie__donar">
        <p className="parrafo">Cotejo es gratis. Si te ahorra tokens, invítale un café a quien lo hace.</p>
        <a className="boton boton--claro" href={DONAR}>
          Donar con Mercado Pago <Icono nombre="flecha" tam={16} />
        </a>
      </div>
      <div className="pie__legal">
        <span>Versión {VERSION} beta · Linux y Windows</span>
        <a href={RELEASES}>Descargas</a>
        <a href={LICENCIA}>Licencia</a>
        <a href={`mailto:${CONTACTO}`}>{CONTACTO}</a>
        <span>Obsidian y Notion son marcas de sus dueños; Cotejo importa de ellas, no es parte de ellas.</span>
      </div>
    </footer>
  )
}
