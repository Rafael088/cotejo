import { useEffect, useId, useState } from 'react'
import { motion } from 'motion/react'
import Comando from './Comando.jsx'
import Icono from './Icono.jsx'
import { COMANDOS, RELEASES, VERSION } from '../config.js'
import { sistemaDe } from '../sistema.js'
import { enlace } from '../paginas.js'

const SISTEMAS = [
  ['linux', 'Linux', '$'],
  ['windows', 'Windows', 'PS>'],
]

// La instalación de la portada, para quien ya vive en una terminal: el comando a la vista con su
// botón de copiar (la acción principal), «Leer los docs» al lado y, debajo, el sistema y lo que
// hay que saber en una línea. Los comandos salen de config.js.
// El prerender no sabe el sistema: arranca en Linux y cambia después de montar si es Windows.
export default function Instalar({ id: ancla, className = '', style }) {
  const [sistema, setSistema] = useState('linux')
  const id = useId()
  useEffect(() => {
    if (sistemaDe(navigator) === 'windows') setSistema('windows')
  }, [])
  const prompt = SISTEMAS.find(([clave]) => clave === sistema)[2]

  return (
    <div className={`instalar ${className}`} style={style} id={ancla}>
      <div className="instalar__fila">
        <Comando texto={COMANDOS[sistema]} prompt={prompt} grande principal />
        <a className="boton boton--borde instalar__docs" href={enlace('/docs')}>
          Leer los docs <Icono nombre="flecha" tam={16} />
        </a>
      </div>
      <div className="instalar__pie">
        <div className="pestanas" role="tablist" aria-label="Sistema">
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
        <p className="instalar__nota">
          Gratis · Linux y Windows 10/11 · beta {VERSION}
          {sistema === 'windows' && (
            <>
              {' · '}
              <a href={RELEASES}>o baja el instalador .exe</a>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
