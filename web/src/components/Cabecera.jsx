import { Marca } from './Logo.jsx'
import { VERSION } from '../config.js'

export default function Cabecera() {
  return (
    <header className="cabecera">
      <a className="cabecera__marca" href="#" aria-label="Cotejo, inicio">
        <Marca tam={28} />
        <span className="cabecera__version">{VERSION} beta</span>
      </a>
      <nav className="cabecera__nav" aria-label="Secciones">
        <a href="#ahorro">Ahorro</a>
        <a href="#trato">Cómo funciona</a>
        <a href="#fuentes">Con qué funciona</a>
        <a className="cabecera__cta" href="#instalar">Instalar</a>
      </nav>
    </header>
  )
}
