import { useRef } from 'react'
import BotonCopiar from './BotonCopiar.jsx'
import useCopiar from './useCopiar.js'

// Una frase para decirle al agente, con su botón de copiar. Entre comillas por CSS: lo que se
// copia es la frase sola.
export default function Frase({ texto }) {
  const ref = useRef()
  const { estado, alCopiar } = useCopiar(texto, ref)
  return (
    <div className="frase" data-estado={estado}>
      <span className="frase__t" ref={ref}>{texto}</span>
      <BotonCopiar estado={estado} onClick={alCopiar} texto={texto} className="comando__boton" />
    </div>
  )
}
