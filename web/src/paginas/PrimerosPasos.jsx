import Frase from '../components/Frase.jsx'
import InstalarRapido from '../components/InstalarRapido.jsx'

// /primerospasos: el primer día (cuatro filas) y cada día (cuatro frases para el agente).
// Las preguntas de la entrevista son las de skills/cotejo/referencias/inicio.md.
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
          <p className="cf-bajada">Lo que haces el primer día, y lo que repites cada día.</p>
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
              Repetirlo actualiza. Si algo falla, <code>cotejo doctor</code> dice qué hacer.
            </p>
          </Fila>
          <Fila cuando="2 · en tu agente" titulo="Arranca el proyecto.">
            <p>Abre tu agente en la carpeta del proyecto y dile:</p>
            <Frase texto="empiezo un proyecto" />
          </Fila>
          <Fila cuando="3 · un mensaje" titulo="Responde cinco preguntas.">
            <div className="mensaje">
              <span className="mensaje__quien">tu agente</span>
              <ol>
                {PREGUNTAS.map(([q, def]) => (
                  <li key={q}>
                    {q}
                    {def && <> <span className="mensaje__def">· {def}</span></>}
                  </li>
                ))}
              </ol>
            </div>
            <p>Confirmas o corriges. Queda escrito el objetivo, el siguiente paso y entre 3 y 8 tareas.</p>
          </Fila>
          <Fila cuando="4 · en CotejoBoard" titulo="Acepta lo que importa.">
            <p>
              Las decisiones grandes, como la tecnología, llegan como propuestas. Ninguna vale hasta que la
              aceptas.
            </p>
          </Fila>
        </div>
      </section>

      <section className="seccion" aria-labelledby="t-cada">
        <div className="seccion__cabeza">
          <h2 id="t-cada" className="titulo-2">Cada día.</h2>
          <p className="parrafo">Cuatro frases para tu agente. Copia la que toque.</p>
        </div>
        <div className="dia">
          <Fila cuando="al empezar" titulo="Ponte al día.">
            <Frase texto="qué tengo pendiente en mi-app" />
            <p>Ves cada tarea con el modelo que le toca.</p>
          </Fila>
          <Fila cuando="para avanzar" titulo="Reparte.">
            <Frase texto="hazme dos tareas de mi-app" />
            <p>Cotejo mira cuántas caben en tu máquina antes de lanzarlas.</p>
          </Fila>
          <Fila cuando="al revisar" titulo="Comprueba.">
            <p>
              Abre CotejoBoard. En «Para comprobar» está cada entrega con su resumen. La apruebas o la
              devuelves con un motivo.
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
