import { useEffect, useId, useState } from 'react'
import { motion } from 'motion/react'
import Comando from './Comando.jsx'
import Icono from './Icono.jsx'
import { COMANDOS, DESCARGAS, RELEASES } from '../config.js'
import { sistemaDe } from '../sistema.js'

const SISTEMAS = [
  ['linux', 'Linux'],
  ['windows', 'Windows'],
]

const NOTAS = {
  linux: 'Cualquier distribución. En Arch y Omarchy, también con pacman.',
  windows: 'Windows 10 y 11, en PowerShell.',
}

// La descarga de Cotejo: un botón con el paquete del sistema (AppImage en Linux, instalador
// .exe en Windows) y, plegados, los comandos de siempre para quien programa. Los comandos
// salen de config.js, nunca escritos aquí.
// El prerender no sabe el sistema: arranca en Linux (igual en el servidor y al hidratar) y
// cambia después de montar, para no descuadrar la hidratación.
export default function InstalarRapido({ nota, pie, id: ancla, className = '', style }) {
  const [sistema, setSistema] = useState('linux')
  const [programaAbierto, setProgramaAbierto] = useState(false)
  const id = useId()
  useEffect(() => {
    const detectado = sistemaDe(navigator)
    if (detectado !== 'linux') setSistema(detectado)
  }, [])

  const descarga = DESCARGAS[sistema]
  const sinPaquete = !descarga

  return (
    <div className={`instalar-rapido ${className}`} style={style} id={ancla}>
      <div className="instalar-rapido__cabeza">
        {descarga ? (
          <a className="boton boton--claro instalar-rapido__descarga" href={descarga.href}>
            <Icono nombre="descarga" tam={18} />
            <span>Descargar para {descarga.sistema}</span>
            <span className="instalar-rapido__paquete">{descarga.paquete}</span>
          </a>
        ) : (
          <a className="boton boton--claro instalar-rapido__descarga" href={RELEASES}>
            <Icono nombre="descarga" tam={18} />
            <span>Ver las descargas</span>
          </a>
        )}
        {nota && <span className="instalar-rapido__aparte">{nota}</span>}
      </div>

      {sinPaquete && (
        <p className="instalar-rapido__otro">
          Cotejo es para Linux y Windows. Si usas otro sistema, desde aquí no hay paquete: los
          comandos de abajo instalan la CLI donde haya Python.
        </p>
      )}

      <details
        className="instalar-rapido__programa"
        open={sinPaquete || programaAbierto}
        onToggle={(e) => setProgramaAbierto(e.currentTarget.open)}
      >
        <summary className="instalar-rapido__resumen">
          <span>Para quien programa</span>
          <span className="instalar-rapido__resumen-nota">instalar con un comando</span>
        </summary>
        <div className="instalar-rapido__comandos">
          <div className="pestanas" role="tablist" aria-label="Sistema para el comando">
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
          <Comando texto={COMANDOS[sistema === 'windows' ? 'windows' : 'linux']} prompt={sistema === 'windows' ? 'PS>' : '$'} grande />
          <p className="instalar-rapido__nota">{NOTAS[sistema === 'windows' ? 'windows' : 'linux']}</p>
        </div>
      </details>

      {pie && <p className="instalar-rapido__nota">{pie}</p>}
    </div>
  )
}
