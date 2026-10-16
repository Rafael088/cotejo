import { useState } from 'react'
import Icono from './Icono.jsx'
import { DURACION, PASOS } from '../comofunciona.js'

// /comofunciona · No programo: cuatro pasos y su escena. Avanzan solos (la barra de progreso de
// cada paso es una animación CSS y al acabar pasa al siguiente) hasta que quien mira toca un
// paso o decide; con movimiento reducido, o con su panel oculto (`activa`), no avanzan solos. Hasta montar (`montado`) no avanza ni
// enseña los botones de decidir, que sin JavaScript no harían nada.

function Resumen({ children }) {
  return (
    <div className="cf-resumen">
      <span className="cf-resumen__etq">
        <Icono nombre="check" tam={14} />
        Para comprobar
      </span>
      <p className="cf-resumen__t">Ya te puedes registrar con tu correo.</p>
      {children}
    </div>
  )
}

function Escena({ i, montado, decision, decidir }) {
  if (i === 0)
    return (
      <>
        <span className="cf-quien cf-quien--der">tú</span>
        <div className="cf-globo">Quiero que la gente pueda registrarse con su correo.</div>
        <span className="cf-quien">tu agente</span>
        <div className="cf-globo cf-globo--agente">Entendido. Lo preparo en tareas.</div>
      </>
    )
  if (i === 1)
    return (
      <>
        <span className="cf-quien">en el tablero · Pendiente</span>
        {[
          ['Formulario de registro', 'sonnet'],
          ['Guardar las cuentas', 'opus'],
          ['Elegir el proveedor de correo', 'persona'],
        ].map(([texto, quien]) => (
          <article key={texto} className="demo-carta">
            <p className="demo-carta__t">{texto}</p>
            <div className="demo-chips">
              <span className="demo-chip demo-chip--borde">{quien}</span>
            </div>
          </article>
        ))}
      </>
    )
  if (i === 2)
    return (
      <>
        <span className="cf-quien">te llega esta entrega</span>
        <Resumen>
          <p>Hay un botón «Crear cuenta» en la portada. Pruébalo: pon un correo y una contraseña, y deberías entrar.</p>
        </Resumen>
      </>
    )
  return (
    <>
      <Resumen>
        {montado && (
          <div className="demo-carta__acciones">
            <button className="demo-mini demo-mini--senal" type="button" onClick={() => decidir('si')}>
              Aprobar
            </button>
            <button className="demo-mini" type="button" onClick={() => decidir('no')}>
              Devolver
            </button>
          </div>
        )}
      </Resumen>
      {decision === 'si' ? (
        <p className="cf-resultado">
          <Icono nombre="check" tam={22} />
          Aprobada. Hecho es cuando tú lo revisas.
        </p>
      ) : decision === 'no' ? (
        <p className="cf-resultado cf-resultado--devuelta">Devuelta. Tu agente la retoma con tu motivo.</p>
      ) : (
        <p className="cf-resultado">Tú decides.</p>
      )}
    </>
  )
}

export default function CfHistoria({ montado, quieto, activa }) {
  const [actual, setActual] = useState(0)
  const [pausa, setPausa] = useState(false)
  const [decision, setDecision] = useState(null)
  const auto = montado && activa && !pausa && !quieto

  const ir = (i) => {
    setActual(i)
    setDecision(null)
  }

  return (
    <div className="cf-historia">
      <div className="cf-pasos" role="tablist" aria-label="Los cuatro pasos">
        {PASOS.map(([titulo, que], i) => (
          <button
            key={titulo}
            className="cf-paso"
            role="tab"
            type="button"
            aria-selected={i === actual}
            onClick={() => {
              setPausa(true)
              ir(i)
            }}
          >
            <span className="cf-paso__n">{i + 1}</span>
            <span className="cf-paso__t">{titulo}</span>
            <span className="cf-paso__d">{que}</span>
            {auto && i === actual && (
              <span
                className="cf-paso__progreso"
                style={{ animationDuration: `${DURACION[i]}ms` }}
                onAnimationEnd={() => ir((actual + 1) % PASOS.length)}
              />
            )}
          </button>
        ))}
      </div>
      <div className="cf-escena" aria-live="polite" key={actual}>
        <Escena
          i={actual}
          montado={montado}
          decision={decision}
          decidir={(d) => {
            setPausa(true)
            setDecision(d)
          }}
        />
      </div>
    </div>
  )
}
