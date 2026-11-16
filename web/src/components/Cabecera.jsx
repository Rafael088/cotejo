import { Logo } from './Logo.jsx'
import { VERSION } from '../config.js'
import { enlace } from '../paginas.js'

// Logo, versión, Docs e Instalar: cabe entera en un teléfono, sin menú. Las páginas de antes
// (/comofunciona, /primerospasos, /tokens) siguen enlazadas desde el pie hasta que llegue /docs.
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
