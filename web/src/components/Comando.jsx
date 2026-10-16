import { useRef } from 'react'
import BotonCopiar from './BotonCopiar.jsx'
import useCopiar from './useCopiar.js'

// Puntos donde el comando puede saltar de línea sin que nadie lo lea mal: después de cada «/»
// de la ruta (no en el «//» de https://, que partido se lee mal). <wbr> no añade caracteres: lo que se copia (y lo que se selecciona a mano) es el
// comando exacto. Sin window ni navigator: igual en el prerender y al hidratar.
function conCortes(texto) {
  return texto.split(/(?<=[^/:]\/)(?!\/)/).flatMap((trozo, i) => (i ? [<wbr key={i} />, trozo] : [trozo]))
}

// Una línea de terminal con su botón de copiar. El verde aparece solo al copiar: es «hecho».
export default function Comando({ texto, prompt = '$', grande = false }) {
  const texto_ref = useRef()
  const { estado, alCopiar } = useCopiar(texto, texto_ref)

  return (
    <div className={`comando ${grande ? 'comando--grande' : ''}`} data-estado={estado}>
      <code className="comando__linea">
        <span className="comando__prompt" aria-hidden="true">{prompt}</span>
        <span className="comando__texto" ref={texto_ref}>{conCortes(texto)}</span>
      </code>
      <BotonCopiar estado={estado} onClick={alCopiar} texto={texto} className="comando__boton" />
    </div>
  )
}
