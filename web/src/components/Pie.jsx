import { Logo } from './Logo.jsx'
import { CONTACTO, DONAR, LICENCIA, RELEASES, VERSION } from '../config.js'
import Icono from './Icono.jsx'
import { enlace } from '../paginas.js'

export default function Pie() {
  return (
    <footer className="pie">
      <div className="pie__dentro">
        <div className="pie__fila">
          <div className="pie__firma">
            <Logo alto={26} />
            <p className="pie__frase">
              Tus agentes entregan. <span>Tú compruebas.</span>
            </p>
          </div>
          <nav className="pie__links" aria-label="Pie">
            <a href={enlace('/')}>Inicio</a>
            <a href={enlace('/comofunciona')}>Cómo funciona</a>
            <a href={enlace('/primerospasos')}>Primeros pasos</a>
            <a href={enlace('/tokens')}>Tokens</a>
            <a href={RELEASES}>Descargas</a>
            <a href={LICENCIA}>Licencia</a>
            <a href={`mailto:${CONTACTO}`}>{CONTACTO}</a>
          </nav>
        </div>
        <div className="pie__donar">
          <p className="parrafo">Cotejo es gratis. Si te ahorra tokens, invítale un café a quien lo hace.</p>
          <a className="boton boton--claro" href={DONAR}>
            Donar con Mercado Pago <Icono nombre="flecha" tam={16} />
          </a>
        </div>
        <p className="pie__legal">
          <span>Versión {VERSION} beta · Linux y Windows</span>
          <span>Obsidian y Notion son marcas de sus dueños; Cotejo importa de ellas, no es parte de ellas.</span>
        </p>
      </div>
    </footer>
  )
}
