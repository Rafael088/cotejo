import Frase from '../components/Frase.jsx'
import InstalarRapido from '../components/InstalarRapido.jsx'

// /primerospasos: el primer día (instalar y crear el proyecto desde el Inicio de la app) y cada
// día (lo que se repite en CotejoBoard y las frases para el agente). Las preguntas de la
// entrevista son las de skills/cotejo/referencias/inicio.md.
function Fila({ cuando, titulo, children }) {
  return (
    <div className="dia__fila">
      <div className="dia__cuando">
        <span className="dia__mono">{cuando}</span>
        <h3 className="titulo-3">{titulo}</h3>
      </div>
      <div className="dia__cuerpo">{children}</div>
    </div>
  )
}

const PREGUNTAS = [
  ['¿Qué es, en una frase?'],
  ['¿Para quién?', 'por defecto, para ti'],
  ['¿Qué tiene que hacer la 0.1.0?', 'tres cosas como mucho'],
  ['¿Qué queda fuera?'],
  ['¿Stack?', 'el que ya hay en la carpeta'],
]

export default function PrimerosPasos() {
  return (
    <>
      <section className="cf" aria-labelledby="t-pp">
        <div className="cf-cabeza">
          <h1 id="t-pp" className="cf-titular">
            Primeros pasos.
          </h1>
          <p className="cf-bajada">Lo que haces al instalarlo, y lo que repites cada día.</p>
        </div>
      </section>

      <section className="seccion seccion--dia" aria-labelledby="t-dia1">
        <div className="seccion__cabeza">
          <h2 id="t-dia1" className="titulo-2">El primer día.</h2>
        </div>
        <div className="dia">
          <Fila cuando="1 · 2 minutos" titulo="Instala.">
            <InstalarRapido />
            <p>
              Linux: el AppImage. Windows: el instalador <code>.exe</code>. Ninguno pide
              administrador ni abrir una terminal.
            </p>
          </Fila>
          <Fila cuando="2 · al abrir" titulo="Revisa tu equipo.">
            <p>
              Cotejo mira qué agentes tienes instalados. Si no hay ninguno, te lleva a instalarlo y
              a iniciar sesión; si ya tienes, sigues al Inicio.
            </p>
          </Fila>
          <Fila cuando="3 · «Nuevo proyecto»" titulo="Cuéntale el proyecto.">
            <p>
              Una entrevista de cinco preguntas, sin IA. Al terminar, Cotejo arma el encargo, lanza
              al agente por detrás y te enseña el progreso mientras prepara la carpeta.
            </p>
            <div className="mensaje">
              <span className="mensaje__quien">la entrevista</span>
              <ol>
                {PREGUNTAS.map(([q, def]) => (
                  <li key={q}>
                    {q}
                    {def && <> <span className="mensaje__def">· {def}</span></>}
                  </li>
                ))}
              </ol>
            </div>
          </Fila>
          <Fila cuando="4 · «Revisar el plan»" titulo="Acepta o cambia.">
            <p>
              Verás el objetivo, las decisiones y las tareas de la 0.1.0. Aceptar es tuyo. «Cambiar»
              devuelve esa decisión al agente con tu motivo para que proponga otra.
            </p>
          </Fila>
          <Fila cuando="5 · «Empezar la 0.1.0»" titulo="Mira el mapa.">
            <p>
              Cotejo reparte las tareas entre los modelos y abre el mapa del proyecto: qué ve la
              gente, qué hace, qué guarda y con qué se conecta.
            </p>
          </Fila>
        </div>
      </section>

      <section className="seccion" aria-labelledby="t-cada">
        <div className="seccion__cabeza">
          <h2 id="t-cada" className="titulo-2">Cada día.</h2>
          <p className="parrafo">Lo que haces en Cotejo y las frases que le puedes decir a tu agente.</p>
        </div>
        <div className="dia">
          <Fila cuando="al empezar" titulo="Ponte al día.">
            <p>
              Abre Cotejo: el Inicio te dice cómo va cada proyecto y cuántas entregas esperan tu
              comprobación.
            </p>
            <Frase texto="qué tengo pendiente en mi-app" />
          </Fila>
          <Fila cuando="para avanzar" titulo="Reparte.">
            <p>
              Pasa una tarea de Pendiente a Haciendo en el tablero. Cotejo lanza al agente con el
              modelo que tenga asignado, y lo que hace se ve en su ficha.
            </p>
          </Fila>
          <Fila cuando="al revisar" titulo="Comprueba.">
            <p>
              En «Para comprobar» está cada entrega con su resumen. La apruebas o la devuelves con
              un motivo. Si el proyecto salió del Inicio, aprobar la integra sola en tu app.
            </p>
          </Fila>
          <Fila cuando="al cerrar versión" titulo="Saca la versión.">
            <Frase texto="saca la 0.1.0 de mi-app" />
            <p>Salen las notas con lo aprobado. Etiquetar y publicar lo haces tú.</p>
          </Fila>
        </div>
      </section>
    </>
  )
}
