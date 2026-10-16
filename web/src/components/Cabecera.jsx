import { useState } from 'react'
import { Logo } from './Logo.jsx'
import Icono from './Icono.jsx'
import { VERSION } from '../config.js'
import { enlace } from '../paginas.js'

const ENLACES = [
  ['/comofunciona', 'Cómo funciona'],
  ['/primerospasos', 'Primeros pasos'],
  ['/tokens', 'Tokens'],
]

function Enlace({ ruta, actual, children }) {
  return (
    <a href={enlace(ruta)} aria-current={actual === ruta ? 'page' : undefined}>
      {children}
    </a>
  )
}

// Cerrado en el primer render (igual en servidor y cliente): sin JavaScript el panel queda
// oculto y no tapa nada; la navegación de escritorio es la misma de siempre.
export default function Cabecera({ ruta }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <header className="cab">
      <div className="cab__fila">
        <a className="cab__marca" href={enlace('/')} aria-label="Cotejo, inicio">
          <Logo alto={28} />
          <span className="cab__version">{VERSION} beta</span>
        </a>
        <nav className="cab__nav" aria-label="Principal">
          {ENLACES.map(([r, texto]) => (
            <Enlace key={r} ruta={r} actual={ruta}>{texto}</Enlace>
          ))}
        </nav>
        <a className="cab__cta" href={`${enlace('/')}#instalar`}>Instalar</a>
        <button
          className="cab__menu"
          type="button"
          aria-expanded={abierto}
          aria-controls="menu-movil"
          aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'}
          onClick={() => setAbierto(!abierto)}
        >
          <Icono nombre={abierto ? 'cerrar' : 'menu'} tam={22} />
        </button>
      </div>
      <nav className="cab__panel" id="menu-movil" aria-label="Menú" hidden={!abierto}>
        <Enlace ruta="/" actual={ruta}>Inicio</Enlace>
        {ENLACES.map(([r, texto]) => (
          <Enlace key={r} ruta={r} actual={ruta}>{texto}</Enlace>
        ))}
      </nav>
    </header>
  )
}
