import { useState, useRef, useEffect } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import Icono from './Icono.jsx'

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    // Sin permiso de portapapeles (http, iframes): el método viejo.
    const area = document.createElement('textarea')
    area.value = texto
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    area.remove()
    return ok
  }
}

// Puntos donde el comando puede saltar de línea sin que nadie lo lea mal: después de cada «/»
// de la ruta (no en el «//» de https://, que partido se lee mal). <wbr> no añade caracteres: lo que se copia (y lo que se selecciona a mano) es el
// comando exacto. Sin window ni navigator: igual en el prerender y al hidratar.
function conCortes(texto) {
  return texto.split(/(?<=[^/:]\/)(?!\/)/).flatMap((trozo, i) => (i ? [<wbr key={i} />, trozo] : [trozo]))
}

// Una línea de terminal con su botón de copiar. El verde aparece solo al copiar: es «hecho».
export default function Comando({ texto, prompt = '$', grande = false }) {
  const [estado, setEstado] = useState('listo') // listo | copiado | error
  const reloj = useRef()
  useEffect(() => () => clearTimeout(reloj.current), [])

  async function alCopiar() {
    const ok = await copiar(texto)
    setEstado(ok ? 'copiado' : 'error')
    clearTimeout(reloj.current)
    reloj.current = setTimeout(() => setEstado('listo'), 2200)
  }

  return (
    <div className={`comando ${grande ? 'comando--grande' : ''}`} data-estado={estado}>
      <code className="comando__linea">
        <span className="comando__prompt" aria-hidden="true">{prompt}</span>
        <span className="comando__texto">{conCortes(texto)}</span>
      </code>
      <button type="button" className="comando__boton" onClick={alCopiar} aria-label={`Copiar: ${texto}`}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={estado}
            className="comando__boton-cara"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }}
          >
            {estado === 'copiado' ? (
              <><Icono nombre="check" tam={16} /> Copiado</>
            ) : estado === 'error' ? (
              <>Selecciónalo a mano</>
            ) : (
              <><Icono nombre="copiar" tam={16} /> Copiar</>
            )}
          </motion.span>
        </AnimatePresence>
      </button>
      <span className="sr-only" aria-live="polite">
        {estado === 'copiado' ? 'Comando copiado' : estado === 'error' ? 'No se pudo copiar' : ''}
      </span>
    </div>
  )
}
