import { CONSULTA } from '../../config.js'
import { NOTA, RESPUESTA_DATOS } from '../../nota-ejemplo.js'

// «Tu agente lee 480 tokens, no 4.700»: la nota entera pasando sin fin contra la respuesta corta
// de la CLI, y debajo las dos barras a escala. En blanco y plata: ahorrar no es «hecho».

const miles = (n) => Math.round(n).toLocaleString('de-DE')
const RESPUESTA = JSON.stringify(
  { total: RESPUESTA_DATOS.total, tareas: RESPUESTA_DATOS.tareas.map(({ id, nombre, agente, dificultad }) => ({ id, nombre, agente, dificultad })) },
  null,
  1,
)

export default function EscenaTokens() {
  return (
    <div
      className="escena escena--tokens"
      role="img"
      aria-label={`Tokens que lee el agente por consulta: la nota entera, unos ${miles(CONSULTA.nota)}; la respuesta de cotejo tareas, unos ${miles(CONSULTA.cli)}.`}
    >
      <div className="lecturas" aria-hidden="true">
        <div className="lectura lectura--nota">
          <div className="lectura__cab">
            <span>La nota entera</span>
            <b>~{miles(CONSULTA.nota)} tokens</b>
          </div>
          <div className="lectura__cinta">
            <pre>{NOTA}</pre>
            <pre>{NOTA}</pre>
          </div>
        </div>
        <div className="lectura lectura--cli">
          <div className="lectura__cab">
            <span>$ cotejo tareas</span>
            <b>~{miles(CONSULTA.cli)} tokens</b>
          </div>
          <pre className="lectura__json">{RESPUESTA}</pre>
        </div>
      </div>
      <div className="escala" aria-hidden="true">
        <span className="escala__fila">
          <span className="escala__barra escala__barra--nota" />
          {miles(CONSULTA.nota)}
        </span>
        <span className="escala__fila escala__fila--cli" style={{ '--parte': (CONSULTA.cli / CONSULTA.nota).toFixed(3) }}>
          <span className="escala__barra escala__barra--cli" />
          {miles(CONSULTA.cli)}
        </span>
      </div>
    </div>
  )
}
