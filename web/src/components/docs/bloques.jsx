import { useRef } from 'react'
import BotonCopiar from '../BotonCopiar.jsx'
import useCopiar from '../useCopiar.js'

// Un bloque de código con su botón de Copiar. `copiar={false}` para una salida que se lee y no
// se pega. Mono es máquina: todo lo que va aquí es lo que escribe o devuelve la CLI.
export function Codigo({ texto, titulo, copiar = true }) {
  const ref = useRef()
  const { estado, alCopiar } = useCopiar(texto, ref)
  return (
    <figure className={`codigo${copiar && !titulo ? ' codigo--suelto' : ''}`} data-estado={estado} data-lectura={copiar ? undefined : ''}>
      {(titulo || copiar) && (
        <figcaption className="codigo__cab">
          <span>{titulo}</span>
          {copiar && <BotonCopiar estado={estado} onClick={alCopiar} texto={texto} className="codigo__copiar" />}
        </figcaption>
      )}
      <pre className="codigo__pre" tabIndex={0}>
        <code ref={ref}>{texto}</code>
      </pre>
    </figure>
  )
}

// Un aviso dentro del texto. «nota» da contexto; «ojo» es lo que no conviene pasar por alto.
// Ninguno lleva color: el verde y el ámbar tienen significado fijo en la web.
export function Aviso({ tipo = 'nota', children }) {
  return (
    <aside className={`aviso aviso--${tipo}`}>
      <b className="aviso__tipo">{tipo === 'ojo' ? 'Ojo' : 'Nota'}</b>
      <div className="aviso__texto">{children}</div>
    </aside>
  )
}

// Una tabla que se lee. `cabeza`: los títulos; `filas`: arreglos de celdas (texto o JSX).
export function Tabla({ cabeza, filas, etiqueta }) {
  return (
    <div className="tabla" role="region" aria-label={etiqueta} tabIndex={0}>
      <table>
        <thead>
          <tr>
            {cabeza.map((c) => (
              <th key={c} scope="col">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, i) => (
            <tr key={i}>
              {fila.map((celda, j) => (
                <td key={j}>{celda}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
