import { useEffect, useId, useState } from 'react'
import { motion } from 'motion/react'
import Comando from './Comando.jsx'
import { COMANDOS } from '../config.js'

const SISTEMAS = [
  ['linux', 'Linux'],
  ['windows', 'Windows'],
]

const NOTAS = {
  linux: 'Cualquier distribución. En Arch y Omarchy, también con pacman.',
  windows: 'Windows 10 y 11, en PowerShell.',
}

// El bloque de instalación con pestañas Linux / Windows: el del hero y el del primer paso de
// «Si no programas». Los comandos salen de config.js, nunca escritos aquí.
// El prerender no sabe el sistema: arranca en Linux (igual en el servidor y al hidratar) y
// cambia a Windows después de montar, para no descuadrar la hidratación.
export default function InstalarRapido({ titulo, coletilla, className = '', style }) {
  const [sistema, setSistema] = useState('linux')
  const id = useId()
  useEffect(() => {
    if (/Win/i.test(navigator.userAgent)) setSistema('windows')
  }, [])

  return (
    <div className={`instalar-rapido ${className}`} style={style}>
      <div className="instalar-rapido__cabeza">
        <span className="instalar-rapido__titulo" id={`${id}-titulo`}>{titulo}</span>
        <div className="pestanas" role="tablist" aria-labelledby={`${id}-titulo`}>
          {SISTEMAS.map(([clave, nombre]) => (
            <button
              key={clave}
              type="button"
              role="tab"
              aria-selected={sistema === clave}
              className="pestanas__boton"
              onClick={() => setSistema(clave)}
            >
              {sistema === clave && (
                <motion.span layoutId={`${id}-pestana`} className="pestanas__fondo" transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }} />
              )}
              <span className="pestanas__texto">{nombre}</span>
            </button>
          ))}
        </div>
      </div>
      <Comando texto={COMANDOS[sistema]} prompt={sistema === 'windows' ? 'PS>' : '$'} grande />
      <p className="instalar-rapido__nota">
        {NOTAS[sistema]}
        {coletilla && <> {coletilla}</>}
      </p>
    </div>
  )
}
