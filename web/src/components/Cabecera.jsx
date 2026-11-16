import { Logo } from './Logo.jsx'
import { VERSION } from '../config.js'
import { enlace } from '../enlace.js'

// Logo, versión, Docs e Instalar: cabe entera en un teléfono, sin menú. El índice de /docs vive
// en la barra lateral de cada página de docs (components/docs/Doc.jsx), no aquí.
export default function Cabecera() {
  return (
    <header className="cab">
      <div className="cab__fila">
        <a className="cab__marca" href={enlace('/')} aria-label="Cotejo, inicio">
          <Logo alto={26} />
          <span className="cab__version">{VERSION} beta</span>
        </a>
        <nav className="cab__nav" aria-label="Principal">
          <a href={enlace('/docs')}>Docs</a>
        </nav>
        <a className="cab__cta" href={`${enlace('/')}#instalar`}>Instalar</a>
      </div>
    </header>
  )
}
