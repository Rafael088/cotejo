import { LayoutGroup } from 'motion/react'
import { Columna, Cursor, Tecleada, useCursor, usePasos } from '../vivo.jsx'

// «Hecho es cuando tú lo revisas»: la entrega llega con evidencia y con la captura de tu app.
// La rechazas con un motivo, el agente vuelve a intentarlo con eso y la segunda sí la apruebas.

const MOTIVO = 'falta el mensaje de error'
//                 0     1    2                          3     4     5    6
const DURACIONES = [2400, 800, MOTIVO.length * 40 + 900, 2600, 2400, 800, 3200]
const FOTO = 4
const CURSOR = { 1: '[data-boton="rechazar"]', 2: '.ficha__campo', 5: '[data-boton="aprobar"]', 6: null }

const BASE = { id: 'c1', texto: 'Login con correo', modelo: 'sonnet' }

function ficha(paso) {
  if (paso === 3) return { ...BASE, estado: 'devuelta', motivo: MOTIVO, lineas: ['lee el motivo', 'Edit src/auth/login.tsx', 'Bash npm test'] }
  if (paso === 6) return { ...BASE, estado: 'hecha' }
  return { ...BASE, estado: 'entregada', ev: paso >= 4 ? 'commit 8d41e0 · 14 pruebas ok' : 'commit 3f2c1a · 12 pruebas ok' }
}

// La captura que acompaña la entrega: tu app, dibujada pequeña. En la segunda ya está el error.
function Captura({ conError }) {
  return (
    <div className="captura">
      <span className="captura__barra" />
      <div className="captura__form">
        <span className="captura__campo" />
        <span className="captura__campo" />
        {conError && <span className="captura__error">Correo o clave incorrectos</span>}
        <span className="captura__boton" />
      </div>
      <span className="captura__pie">captura · login.png</span>
    </div>
  )
}

export default function EscenaComprobar() {
  const [ref, paso, vivo] = usePasos(DURACIONES, FOTO)
  const pos = useCursor(ref, paso, vivo, CURSOR)
  const c = ficha(paso)
  const en = paso === 3 ? 'haciendola' : paso === 6 ? 'finalizada' : 'comprobar'
  const cols = [
    ['haciendola', 'Haciéndola', [{ id: 'c0', texto: 'Correo de bienvenida', modelo: 'haiku', estado: 'viva', lineas: ['Read correo/plantillas.ts', 'Write correo/bienvenida.tsx'] }]],
    ['comprobar', 'Para comprobar', []],
    ['finalizada', 'Finalizada', [{ id: 'c9', texto: 'Página de inicio', estado: 'hecha' }]],
  ].map(([clave, nombre, fichas]) => [clave, nombre, clave === en ? [...fichas, c] : fichas])

  const extras = (f) =>
    f.id === 'c1' &&
    f.estado === 'entregada' && (
      <>
        <Captura conError={paso >= 4} />
        {paso === 2 ? (
          <span className="ficha__campo">
            <Tecleada texto={MOTIVO} ms={40} />
          </span>
        ) : (
          <div className="ficha__acciones">
            <span className="mini mini--senal" data-boton="aprobar" data-pulsa={paso === 5 || undefined}>
              Aprobar
            </span>
            <span className="mini" data-boton="rechazar" data-pulsa={paso === 1 || undefined}>
              Rechazar
            </span>
          </div>
        )}
      </>
    )

  return (
    <div
      className="escena escena--tablero"
      role="img"
      aria-label="Una entrega en Para comprobar, con su evidencia y una captura de la app. La rechazas con el motivo «falta el mensaje de error», el agente la rehace y la segunda entrega la apruebas tú."
    >
      <div className="escena__tablero escena__tablero--comprobar" ref={ref} aria-hidden="true">
        <LayoutGroup id="comprobar">
          {cols.map(([clave, nombre, fichas]) => (
            <Columna key={clave} clave={clave} nombre={nombre} fichas={fichas} vivo={vivo} render={extras} />
          ))}
        </LayoutGroup>
        <Cursor pos={pos} agarra={paso === 1 || paso === 5} />
      </div>
    </div>
  )
}
