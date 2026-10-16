import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { Logo } from './Logo.jsx'
import Tablero from './Tablero.jsx'
import Comando from './Comando.jsx'
import Icono from './Icono.jsx'
import { COMANDOS } from '../config.js'

// La entrada es CSS (.aparece en styles.css, con su retraso en --retraso), no motion: el HTML
// prerenderizado llega visible y la animación solo corre si index.html marcó <html class="js">
// antes de pintar. Así, sin JavaScript, nada arriba del pliegue arranca en opacity:0.

export default function Hero() {
  // El prerender no sabe el sistema: arranca en Linux (igual en el servidor y al hidratar)
  // y cambia a Windows después de montar, para no descuadrar la hidratación.
  const [sistema, setSistema] = useState('linux')
  useEffect(() => {
    if (/Win/i.test(navigator.userAgent)) setSistema('windows')
  }, [])

  return (
    <section className="hero" aria-labelledby="hero-titulo">
      <div className="hero__fondo" aria-hidden="true">
        <Tablero />
      </div>
      <div className="hero__velo" aria-hidden="true" />

      <div className="hero__centro">
        <div className="aparece" style={{ '--retraso': '0s' }}>
          <Logo alto={72} animado className="hero__logo" />
        </div>
        <h1 id="hero-titulo" className="hero__titulo aparece" style={{ '--retraso': '0.12s' }}>
          Tus agentes entregan. <span className="hero__titulo-tu">Tú compruebas.</span>
        </h1>
        <p className="hero__bajada aparece" style={{ '--retraso': '0.22s' }}>
          Cotejo es el tablero de control para hacer vibe coding profesional. Tus agentes escriben
          el código; Cotejo organiza el proyecto y verifica lo que entregan. El check lo pones tú.
        </p>

        <div className="instalar-rapido aparece" style={{ '--retraso': '0.34s' }}>
          <div className="instalar-rapido__cabeza">
            <span className="instalar-rapido__titulo" id="instalar-rapido">Instálalo: pega un comando en una terminal</span>
            <div className="pestanas" role="tablist" aria-labelledby="instalar-rapido">
              {[
                ['linux', 'Linux'],
                ['windows', 'Windows'],
              ].map(([id, nombre]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={sistema === id}
                  className="pestanas__boton"
                  onClick={() => setSistema(id)}
                >
                  {sistema === id && (
                    <motion.span layoutId="pestana-activa" className="pestanas__fondo" transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }} />
                  )}
                  <span className="pestanas__texto">{nombre}</span>
                </button>
              ))}
            </div>
          </div>
          <Comando texto={COMANDOS[sistema]} prompt={sistema === 'windows' ? 'PS>' : '$'} grande />
          <p className="instalar-rapido__nota">
            {sistema === 'windows' ? 'Windows 10 y 11, en PowerShell.' : 'Cualquier distribución. En Arch y Omarchy, también con pacman.'}{' '}
            Gratis, versión beta. ¿No usas la terminal? Pídele a tu agente que lo instale.
          </p>
        </div>

        <a href="#ahorro" className="hero__seguir aparece" style={{ '--retraso': '0.5s' }}>
          Mira cuánto ahorra <Icono nombre="abajo" tam={16} />
        </a>
      </div>
    </section>
  )
}
