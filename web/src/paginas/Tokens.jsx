import Icono from '../components/Icono.jsx'
import Cierre from '../components/Cierre.jsx'
import { NOTA, RESPUESTA_DATOS } from '../nota-ejemplo.js'
import { AHORRO, CONSULTA } from '../config.js'

// /tokens: la nota entera contra la respuesta de la CLI, la escala a proporción, la medida real
// (con su supuesto a la vista) y el camino del segundo cerebro al repo. Todas las cifras salen
// de config.js (CONSULTA y AHORRO): aquí no se escribe ninguna a mano.
const miles = (n) => Math.round(n).toLocaleString('de-DE')
const aprox = (n) => `~${miles(n)}`
const decimal = (n) => n.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const porcentaje = (n) => `${((n / CONSULTA.nota) * 100).toFixed(1)}%`

// La salida real de `cotejo tareas`: una tarea por línea, con la clave resaltada.
function Json({ valor }) {
  const k = (nombre) => <span className="tk-k">"{nombre}"</span>
  const campos = (obj) =>
    Object.entries(obj).map(([nombre, v], i, todos) => (
      <span key={nombre}>
        {k(nombre)}: {JSON.stringify(v)}
        {i < todos.length - 1 ? ', ' : ''}
      </span>
    ))
  return (
    <>
      {'{'}
      {k('esquema')}: {valor.esquema}, {k('total')}: {valor.total}, {k('tareas')}: [{'\n'}
      {valor.tareas.map((t, i) => (
        <span key={t.id}>
          {'  {'}
          {campos(t)}
          {'}'}
          {i < valor.tareas.length - 1 ? ',' : ''}
          {'\n'}
        </span>
      ))}
      {']}'}
    </>
  )
}

function Nodo({ titulo, mono, children, repo = false }) {
  return (
    <div className={`tk-nodo${repo ? ' tk-nodo--repo' : ''}`}>
      <b>{titulo}</b>
      <span className="tk-mono">{mono}</span>
      {children && <p>{children}</p>}
    </div>
  )
}

const Flecha = () => (
  <div className="tk-flecha" aria-hidden="true">
    <Icono nombre="flecha" tam={22} />
  </div>
)

export default function Tokens() {
  return (
    <>
      <section className="cf" aria-labelledby="t-tokens">
        <div className="cf-cabeza">
          <h1 id="t-tokens" className="cf-titular">
            {`Tu agente lee ${miles(CONSULTA.cli)} tokens, no ${miles(CONSULTA.nota)}.`}
          </h1>
          <p className="cf-bajada">
            Para saber qué falta, no necesita leer la nota entera del proyecto. Cotejo le responde solo eso.
          </p>
        </div>
      </section>

      <section className="seccion" aria-labelledby="t-versus">
        <h2 id="t-versus" className="sr-only">La nota entera contra la respuesta de Cotejo</h2>
        <div className="tk-versus">
          <div className="tk-panel">
            <div className="tk-cab">
              <b>La nota entera</b>
              <span className="tk-mono">{aprox(CONSULTA.nota)} tokens</span>
            </div>
            <div className="tk-nota" aria-hidden="true">
              <pre>{NOTA + '\n' + NOTA}</pre>
            </div>
          </div>
          <div className="tk-panel tk-respuesta">
            <div className="tk-cab">
              <b>Lo que pide el agente</b>
              <span className="tk-mono">{aprox(CONSULTA.cli)} tokens</span>
            </div>
            <pre>
              <span className="tk-k">$</span> cotejo tareas --proyecto web --estado pendiente{'\n'}
              <Json valor={RESPUESTA_DATOS} />
            </pre>
          </div>
        </div>
        <div
          className="tk-escala"
          role="img"
          aria-label={`Tokens por consulta: la nota entera, unos ${miles(CONSULTA.nota)}; cotejo tareas, unos ${miles(CONSULTA.cli)}`}
        >
          <div className="tk-escala__fila">
            <span className="tk-escala__nombre">La nota entera</span>
            <div className="tk-escala__barra" style={{ width: porcentaje(CONSULTA.nota) }} />
            <span className="tk-escala__cifra">{aprox(CONSULTA.nota)}</span>
          </div>
          <div className="tk-escala__fila">
            <span className="tk-escala__nombre">cotejo tareas</span>
            <div className="tk-escala__barra tk-escala__barra--cli" style={{ width: porcentaje(CONSULTA.cli) }} />
            <span className="tk-escala__cifra">{aprox(CONSULTA.cli)}</span>
          </div>
        </div>
      </section>

      <section className="seccion" aria-labelledby="t-medido">
        <div className="tk-medida">
          <div className="tk-cifra" aria-describedby="t-medido">{decimal(AHORRO.razon)}×</div>
          <div className="tk-medida__datos">
            <h2 id="t-medido" className="titulo-3">
              menos texto leído, medido con <code>cotejo ahorro</code> en la máquina del autor.
            </h2>
            <dl>
              <div><dt>Lecturas</dt><dd>{miles(AHORRO.lecturas)}</dd></div>
              <div><dt>Tokens ahorrados</dt><dd>~{miles(Math.round(AHORRO.tokensAhorrados / 1000) * 1000)}</dd></div>
              <div><dt>Caracteres leídos</dt><dd>{miles(AHORRO.leido)}</dd></div>
              <div><dt>Caracteres devueltos</dt><dd>{miles(AHORRO.devuelto)}</dd></div>
            </dl>
            <p className="nota-al-pie">
              Supuesto: sin Cotejo, el agente habría leído las notas enteras. Mídelo en tu proyecto con{' '}
              <code>cotejo ahorro</code>.
            </p>
          </div>
        </div>
      </section>

      <section className="seccion" aria-labelledby="t-cerebro">
        <div className="seccion__cabeza">
          <h2 id="t-cerebro" className="titulo-2">¿Tu proyecto vive en tu segundo cerebro?</h2>
          <p className="parrafo parrafo--tenue">Si lo llevas en Obsidian o en Notion, lo traes a tu repo de una vez.</p>
        </div>
        <div className="tk-flujo">
          <div className="tk-origenes">
            <Nodo titulo="Obsidian" mono="tu vault" />
            <Nodo titulo="Notion" mono="tu espacio" />
          </div>
          <Flecha />
          <Nodo titulo="Importar" mono="cotejo importar obsidian">
            Primero un ensayo: ves qué entra sin tocar nada.
          </Nodo>
          <Flecha />
          <Nodo titulo=".cotejo/ en tu repo" mono="un archivo por entrada" repo>
            Decisiones, arquitectura, tareas.
          </Nodo>
          <Flecha />
          <Nodo titulo="Tu agente" mono="cotejo contexto">
            Todo en menos de 1.000 tokens.
          </Nodo>
        </div>
        <p className="nota-al-pie">¿Otra app? Se conecta con un adaptador de cuatro métodos.</p>
      </section>

      <Cierre id="cierre-tokens" titulo="Mídelo en tu propio proyecto." />
    </>
  )
}
