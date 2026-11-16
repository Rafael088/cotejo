import Icono from '../Icono.jsx'
import { Tecleada, usePasos } from '../vivo.jsx'

// «El maestro: le hablas en llano»: el panel de la conversación, como flota sobre el board.
// Apunta, contesta, propone repartir (el botón) y, cuando aprueba algo, Cotejo lo deshace.

const CHARLA = [
  ['tu', 'apunta que falta el login'],
  ['maestro', 'Apuntada en Pendiente: «Login con correo».'],
  ['tu', '¿qué falta para la 0.1.0?'],
  ['maestro', 'Tres pendientes y una para comprobar.'],
  ['tu', 'reparte lo asignado'],
  ['maestro', 'Dos tienen modelo: a1 → sonnet, b2 → haiku.', 'repartir'],
  ['tu', 'y aprueba la a1'],
  ['deshecho', 'El maestro aprobó a1. Cotejo lo deshizo: vuelve a Para comprobar.'],
]

// Un paso por mensaje; los tuyos llevan antes un paso en que se escriben en la barra.
const PASOS = CHARLA.flatMap(([quien, texto], i) =>
  quien === 'tu'
    ? [
        { visibles: i, teclea: texto, ms: texto.length * 38 + 500 },
        { visibles: i + 1, ms: 700 },
      ]
    : [{ visibles: i + 1, ms: i === CHARLA.length - 1 ? 4200 : 1500 }],
)
const DURACIONES = PASOS.map((p) => p.ms)

export default function EscenaMaestro() {
  const [ref, paso, vivo] = usePasos(DURACIONES, PASOS.length - 1)
  const { visibles, teclea } = PASOS[paso]
  return (
    <div
      className="escena escena--maestro"
      ref={ref}
      role="img"
      aria-label="Conversación con el maestro: «apunta que falta el login», «¿qué falta para la 0.1.0?», «reparte lo asignado», con un botón Repartir. Cuando el maestro aprueba una tarea, Cotejo lo deshace."
    >
      <div className="maestro" aria-hidden="true">
        <div className="maestro__cab">
          <span>Maestro · mi-app</span>
          <Icono nombre="menos" tam={14} />
          <Icono nombre="cerrar" tam={14} />
        </div>
        <div className="maestro__charla">
          {CHARLA.slice(0, visibles).map(([quien, texto, extra], i) => (
            <div key={i} className={`maestro__msj maestro__msj--${quien}${vivo ? ' maestro__msj--entra' : ''}`}>
              {quien === 'deshecho' && <Icono nombre="deshacer" tam={14} />}
              <p>{texto}</p>
              {extra === 'repartir' && <span className="maestro__repartir">Repartir</span>}
            </div>
          ))}
        </div>
        <div className="maestro__pie">
          <span className="maestro-barra">
            {teclea ? (
              <span className="maestro-barra__texto">
                <Tecleada key={paso} texto={teclea} ms={38} />
              </span>
            ) : (
              <span className="maestro-barra__hueco">Pídele algo al maestro</span>
            )}
          </span>
          <span className="maestro-enviar">Enviar</span>
        </div>
      </div>
    </div>
  )
}
