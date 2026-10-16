import Icono from './Icono.jsx'
import { enlace } from '../paginas.js'
import { CONSULTA } from '../config.js'

// Portada · «Tu agente lee 480 tokens, no 4.700»: dos barras a escala (ancho = cifra / nota).
// Las cifras salen de CONSULTA (config.js), la misma fuente que el medidor de /tokens.
const miles = (n) => Math.round(n).toLocaleString('de-DE')
const porcentaje = (n) => `${((n / CONSULTA.nota) * 100).toFixed(1)}%`

export default function InicioAhorro() {
  return (
    <section className="seccion" id="ahorro-inicio" aria-labelledby="ahorro-inicio-titulo">
      <div className="seccion__cabeza">
        <h2 id="ahorro-inicio-titulo" className="titulo-2">
          {`Tu agente lee ${miles(CONSULTA.cli)} tokens, no ${miles(CONSULTA.nota)}.`}
        </h2>
        <p className="parrafo parrafo--tenue">Le da a tu agente solo lo que necesita del proyecto.</p>
      </div>
      <div className="ini-escala" role="img" aria-label={`Tokens que lee el agente por consulta: la nota entera, unos ${miles(CONSULTA.nota)}; cotejo tareas, unos ${miles(CONSULTA.cli)}`}>
        <div className="ini-escala__fila">
          <span className="ini-escala__nombre">La nota entera</span>
          <div className="ini-escala__barra" style={{ width: porcentaje(CONSULTA.nota) }} />
          <span className="ini-escala__cifra">~{miles(CONSULTA.nota)}</span>
        </div>
        <div className="ini-escala__fila">
          <span className="ini-escala__nombre">cotejo tareas</span>
          <div className="ini-escala__barra ini-escala__barra--cli" style={{ width: porcentaje(CONSULTA.cli) }} />
          <span className="ini-escala__cifra">~{miles(CONSULTA.cli)}</span>
        </div>
      </div>
      <p className="nota-al-pie">
        Las pendientes de un proyecto contra su nota completa. Supuesto: sin Cotejo, el agente leería la nota entera.
      </p>
      <p className="ini-enlace">
        <a className="enlace-flecha" href={enlace('/tokens')}>
          Cómo ahorra tokens <Icono nombre="flecha" />
        </a>
      </p>
    </section>
  )
}
