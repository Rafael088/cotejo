import EscenaAgentes from './escenas/EscenaAgentes.jsx'
import EscenaMaestro from './escenas/EscenaMaestro.jsx'
import EscenaEnrutador from './escenas/EscenaEnrutador.jsx'
import EscenaComprobar from './escenas/EscenaComprobar.jsx'
import EscenaTokens from './escenas/EscenaTokens.jsx'
import { AHORRO, CONSULTA } from '../config.js'

// La rejilla de la portada: cinco funciones, cada una demostrada por su escena (una pieza del
// board en marcha) con un titular y una línea. Las cifras salen de config.js con su supuesto.
const miles = (n) => Math.round(n).toLocaleString('de-DE')
const razon = AHORRO.razon.toLocaleString('de-DE')

function Funcion({ forma, titulo, children, escena }) {
  return (
    <article className={`funcion funcion--${forma}`}>
      <div className="funcion__escena">{escena}</div>
      <div className="funcion__texto">
        <h3 className="funcion__titulo">{titulo}</h3>
        <p className="funcion__linea">{children}</p>
      </div>
    </article>
  )
}

export default function Funciones() {
  return (
    <section className="funciones" id="funciones" aria-labelledby="funciones-titulo">
      <h2 id="funciones-titulo" className="funciones__titulo">
        Diriges tú. <span>Trabajan ellos.</span>
      </h2>
      <div className="funciones__rejilla">
        <Funcion forma="ancha" titulo="Arrastra y un agente se pone a trabajar." escena={<EscenaAgentes />}>
          Cada tarea corre con su modelo, en su propia copia del proyecto. Varias a la vez; si no hay
          memoria libre, espera.
        </Funcion>
        <Funcion forma="angosta" titulo="El maestro: le hablas en llano." escena={<EscenaMaestro />}>
          Hace lo que harías en una terminal, menos aprobar. Si aprueba algo, Cotejo lo deshace solo.
        </Funcion>
        <Funcion forma="angosta" titulo="Cada tarea al modelo justo, y algunas a ti." escena={<EscenaEnrutador />}>
          Elige entre tus modelos y sabe cuándo una tarea no es para ninguno. Ante la duda escala,
          nunca abarata.
        </Funcion>
        <Funcion forma="ancha" titulo="Hecho es cuando tú lo revisas." escena={<EscenaComprobar />}>
          El agente entrega con evidencia. Tú apruebas o rechazas con un motivo. No existe un comando
          para finalizar.
        </Funcion>
        <Funcion
          forma="entera"
          titulo={`Tu agente lee ${miles(CONSULTA.cli)} tokens, no ${miles(CONSULTA.nota)}.`}
          escena={<EscenaTokens />}
        >
          El contexto, las decisiones y la arquitectura viven en <code>.cotejo/</code>, dentro de tu
          repo, y la CLI contesta JSON corto. Medido: {razon}× menos lectura, si sin Cotejo el agente
          hubiera leído las notas enteras.
        </Funcion>
      </div>
    </section>
  )
}
