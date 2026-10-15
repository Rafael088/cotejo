import { useState } from 'react'
import { motion } from 'motion/react'
import { Logo } from './Logo.jsx'
import Tablero from './Tablero.jsx'
import Comando from './Comando.jsx'
import Icono from './Icono.jsx'
import { COMANDOS } from '../config.js'

function sistemaInicial() {
  if (typeof navigator === 'undefined') return 'linux'
  return /Win/i.test(navigator.userAgent) ? 'windows' : 'linux'
}

const aparecer = (retraso) => ({
  initial: { opacity: 0, y: 14, filter: 'blur(6px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  transition: { delay: retraso, duration: 0.8, ease: [0.16, 1, 0.3, 1] },
})

export default function Hero() {
  const [sistema, setSistema] = useState(sistemaInicial)

  return (
    <section className="hero" aria-labelledby="hero-titulo">
      <div className="hero__fondo" aria-hidden="true">
        <Tablero />
      </div>
      <div className="hero__velo" aria-hidden="true" />

      <div className="hero__centro">
        <motion.div {...aparecer(0)}>
          <Logo alto={72} animado className="hero__logo" />
        </motion.div>
        <motion.h1 id="hero-titulo" className="hero__titulo" {...aparecer(0.12)}>
          Tus agentes entregan. <span className="hero__titulo-tu">Tú compruebas.</span>
        </motion.h1>
        <motion.p className="hero__bajada" {...aparecer(0.22)}>
          Cotejo es el tablero de control para hacer vibe coding profesional. Tus agentes escriben
          el código; Cotejo organiza el proyecto y verifica lo que entregan. El check lo pones tú.
        </motion.p>

        <motion.div className="instalar-rapido" {...aparecer(0.34)}>
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
        </motion.div>

        <motion.a href="#ahorro" className="hero__seguir" {...aparecer(0.5)}>
          Mira cuánto ahorra <Icono nombre="abajo" tam={16} />
        </motion.a>
      </div>
    </section>
  )
}
