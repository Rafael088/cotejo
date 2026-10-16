import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useReducedMotion } from 'motion/react'
import Icono from './Icono.jsx'

// Una tarea recorre las cuatro columnas. Las tres primeras las mueve el agente con un verbo;
// la última solo se mueve con la mano de quien visita, porque Cotejo no tiene verbo para eso.
const COLUMNAS = ['Pendiente', 'Haciéndola', 'Para comprobar', 'Finalizada']

const PASOS = [
  {
    orden: 'cotejo tareas --estado pendiente',
    respuesta: '{"total": 1, "tareas": [{"id": "web-c3d4", …}]}',
    texto: 'El agente pregunta qué falta y recibe la tarea con un id estable.',
  },
  {
    orden: 'cotejo tomar web-c3d4 --agente opus',
    respuesta: '{"cambio": true, "tarea": {"estado": "haciendola", "agente": "opus"}}',
    texto: 'La toma a su nombre. Si alguien cambió la nota mientras tanto, no escribe nada.',
  },
  {
    orden: 'cotejo entregar web-c3d4 --evidencia "commit 9b1e4f2, install.sh responde 200"',
    respuesta: '{"cambio": true, "tarea": {"estado": "por-validar"}}',
    texto: 'La entrega con evidencia. Sin evidencia, Cotejo no la acepta.',
  },
]

export default function Trato() {
  const ref = useRef(null)
  const visto = useInView(ref, { once: false, margin: '-30% 0px' })
  const reducido = useReducedMotion()
  const [paso, setPaso] = useState(0) // 0..2 los mueve el agente, 3 = comprobada por ti
  const [devuelta, setDevuelta] = useState(false)
  const columna = paso === 0 ? 0 : paso === 1 ? 1 : paso === 2 ? 2 : 3

  useEffect(() => {
    if (!visto || paso >= 2) return
    const t = setTimeout(() => setPaso((p) => p + 1), reducido ? 400 : 1900)
    return () => clearTimeout(t)
  }, [visto, paso, reducido])

  const historial = PASOS.slice(0, Math.min(paso, 2) + 1)
  // Una devuelta vuelve a Pendiente con su motivo, y el agente lo lee antes de rehacerla.
  const motivo = devuelta && paso < 2

  return (
    <section className="seccion trato" id="trato" aria-labelledby="trato-titulo" ref={ref}>
      <div className="seccion__cabeza">
        <h2 id="trato-titulo" className="titulo-2">Una tarea, de Pendiente a Finalizada.</h2>
        <p className="parrafo">
          Lo de arriba, en marcha. Las tres primeras columnas las mueve el agente con un verbo y
          deja su evidencia; la última la mueves tú, aquí mismo.
        </p>
      </div>

      <div className="trato__escena">
        <div className="trato__columnas" role="list" aria-label="Columnas del board">
          {COLUMNAS.map((nombre, i) => (
            <div key={nombre} role="listitem" className={`trato__col ${i === 2 ? 'trato__col--espera' : ''} ${i === columna ? 'es-actual' : ''}`}>
              <span className="trato__col-nombre">{nombre}</span>
              <div className="trato__hueco">
                {i === columna && (
                  <motion.div
                    layoutId="trato-carta"
                    className={`trato__carta ${columna === 2 ? 'trato__carta--espera' : ''} ${columna === 3 ? 'trato__carta--hecha' : ''} ${motivo ? 'trato__carta--devuelta' : ''}`}
                    transition={{ type: 'spring', bounce: 0.18, duration: 0.7 }}
                  >
                    <span className="trato__carta-texto">Servir install.sh e install.ps1 desde el dominio</span>
                    <span className="trato__carta-chips">
                      {columna >= 1 && <span className="t-chip t-chip--borde">opus</span>}
                      <span className="t-chip">#medio</span>
                    </span>
                    {motivo && <span className="trato__devuelta">DEVUELTA · falta probar install.ps1 en Windows</span>}
                    {columna === 2 && (
                      <span className="trato__evidencia">
                        {devuelta ? 'commit a07c3d9, los dos scripts responden 200' : 'commit 9b1e4f2, install.sh responde 200'}
                      </span>
                    )}
                    {columna === 3 && (
                      <span className="trato__sello"><Icono nombre="check" tam={14} /> Comprobada por ti</span>
                    )}
                  </motion.div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="trato__consola">
          <div className="trato__log" aria-live="polite">
            <AnimatePresence initial={false}>
              {historial.map((p) => (
                <motion.div
                  key={p.orden}
                  className="trato__entrada"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                >
                  <code className="trato__orden"><span className="comparar__prompt">$</span> {p.orden}</code>
                  <code className="trato__respuesta">{p.respuesta}</code>
                  <p className="trato__explica">{p.texto}</p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div className="trato__mano">
            {paso < 3 ? (
              <>
                <code className="trato__orden trato__orden--falta">
                  # cotejo finalizar no existe: el check lo pones tú
                </code>
                <div className="trato__botones">
                  <button
                    type="button"
                    className="boton boton--senal"
                    disabled={paso < 2}
                    onClick={() => setPaso(3)}
                  >
                    <Icono nombre="check" tam={18} />
                    {paso < 2 ? 'Espera la entrega…' : 'Marcar como hecha'}
                  </button>
                  {paso === 2 && !devuelta && (
                    <button
                      type="button"
                      className="boton boton--fantasma"
                      onClick={() => {
                        setDevuelta(true)
                        setPaso(0)
                      }}
                    >
                      Devolver con motivo
                    </button>
                  )}
                </div>
                {motivo && (
                  <p className="trato__explica">
                    Devuelta: «falta probar install.ps1 en Windows». El motivo le llega al agente con la tarea.
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="trato__cierre">Eso. El agente trabajó; tú decidiste que estaba hecho.</p>
                <button type="button" className="boton boton--fantasma" onClick={() => { setDevuelta(false); setPaso(0) }}>
                  <Icono nombre="repetir" tam={16} /> Otra vez
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
