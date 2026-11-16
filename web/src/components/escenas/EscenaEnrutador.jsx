import Icono from '../Icono.jsx'
import { usePasos } from '../vivo.jsx'
import { TAREAS_MEDIDAS } from '../../config.js'

// «Cada tarea al modelo justo, y algunas a ti»: el enrutador recorre las pendientes y a cada una
// le pone su modelo; dos no son para ningún modelo. Debajo, la medida real: 24 de 65.

const TAREAS = [
  ['Corregir un typo del pie', 'haiku'],
  ['Login con correo', 'sonnet'],
  ['Migrar la base de datos', 'opus'],
  ['Comprar el dominio', 'persona'],
  ['Refactor del carrito', 'deepseek'],
  ['Que un abogado revise los textos', 'persona'],
]
// Lo que gira en el chip antes de quedarse en el modelo elegido.
const RUEDA = ['opus', 'sonnet', 'haiku', 'deepseek', 'kimi']

const DURACIONES = [900, ...TAREAS.map(() => 850), 4200]
const FOTO = DURACIONES.length - 1

export default function EscenaEnrutador() {
  const [ref, paso, vivo] = usePasos(DURACIONES, FOTO)
  const { total, persona } = TAREAS_MEDIDAS
  return (
    <div
      className="escena escena--enrutador"
      ref={ref}
      role="img"
      aria-label={`El enrutador asigna cada tarea a un modelo (haiku, sonnet, opus, deepseek) y deja dos para una persona. Medido: ${persona} de ${total} tareas reales eran de una persona.`}
    >
      <ul className="rutas" aria-hidden="true">
        {TAREAS.map(([texto, modelo], i) => {
          const decidida = paso > i
          return (
            <li key={texto} className={`rutas__fila${paso === i + 1 && vivo ? ' rutas__fila--ahora' : ''}${decidida && modelo === 'persona' ? ' rutas__fila--persona' : ''}`}>
              <span className="rutas__texto">{texto}</span>
              {decidida ? (
                modelo === 'persona' ? (
                  <span className="f-chip f-chip--tu">
                    <Icono nombre="persona" tam={11} />
                    tú
                  </span>
                ) : (
                  <span className="f-chip f-chip--borde rutas__chip">
                    <span className="rutas__rueda">
                      {RUEDA.filter((m) => m !== modelo).slice(0, 3).map((m) => (
                        <span key={m}>{m}</span>
                      ))}
                      <span>{modelo}</span>
                    </span>
                  </span>
                )
              ) : (
                <span className="f-chip rutas__pendiente">sin modelo</span>
              )}
            </li>
          )
        })}
      </ul>
      <div className="medida" aria-hidden="true">
        <div className="medida__puntos">
          {Array.from({ length: total }, (_, i) => (
            <i key={i} className={i < persona ? 'medida__punto medida__punto--persona' : 'medida__punto'} />
          ))}
        </div>
        <p className="medida__texto">
          <b>
            {persona} de {total}
          </b>{' '}
          tareas reales eran de una persona
        </p>
      </div>
    </div>
  )
}
