import { useEffect } from 'react'
import { LayoutGroup } from 'motion/react'
import Icono from './Icono.jsx'
import { Columna, Cursor, Tecleada, useCursor, usePasos } from './vivo.jsx'

// La recreación de CotejoBoard del hero (sin video: el dueño decidió que el producto se enseña
// con el board en marcha): le pides tareas al maestro en la barra del pie, aparecen en Pendiente,
// las arrastras a Haciéndola y los agentes arrancan en paralelo; la primera entrega queda
// esperando que la compruebes. Nadie aprueba aquí: eso es tuyo.

const PEDIDO = 'apunta: login con correo y correo de bienvenida'

//                 0     1                          2     3    4    5    6    7     8     9
const DURACIONES = [900, PEDIDO.length * 34 + 600, 1500, 800, 900, 800, 900, 3200, 2600, 3600]
const FOTO = 8
const CURSOR = { 3: '[data-ficha="a1"]', 4: '[data-ficha="a1"]', 5: '[data-ficha="b2"]', 6: '[data-ficha="b2"]' }
const AGARRADA = { 4: 'a1', 6: 'b2' }

const A1 = {
  id: 'a1',
  texto: 'Login con correo',
  modelo: 'sonnet',
  dif: 'medio',
  lineas: ['worktree cotejo/a1', 'Read src/auth/sesion.ts', 'Edit src/auth/login.tsx', 'Bash npm test', '12 pruebas ok'],
}
const B2 = {
  id: 'b2',
  texto: 'Correo de bienvenida',
  modelo: 'haiku',
  dif: 'fácil',
  lineas: ['worktree cotejo/b2', 'Read correo/plantillas.ts', 'Write correo/bienvenida.tsx', 'Bash npm test'],
}
const FIJAS = {
  pendiente: [{ id: 'c3', texto: 'Comprar el dominio', modelo: 'persona', dif: 'fácil' }],
  finalizada: [
    { id: 'd4', texto: 'Página de inicio', estado: 'hecha' },
    { id: 'e5', texto: 'Esquema de la base de datos', estado: 'hecha' },
  ],
}

// Dónde está cada ficha en cada paso.
function columnas(paso) {
  const a1 = paso >= 8 ? 'comprobar' : paso >= 4 ? 'haciendola' : paso >= 2 ? 'pendiente' : null
  const b2 = paso >= 9 ? 'comprobar' : paso >= 6 ? 'haciendola' : paso >= 2 ? 'pendiente' : null
  const vestir = (c, col) =>
    col === 'haciendola'
      ? { ...c, estado: 'viva', rama: `cotejo/${c.id}` }
      : col === 'comprobar'
        ? { ...c, estado: 'entregada', ev: c.id === 'a1' ? '3f2c1a · 12 pruebas ok' : '1a4b9c · 4 pruebas ok' }
        : { ...c, nueva: true }
  const en = (col) => [
    ...(a1 === col ? [vestir(A1, col)] : []),
    ...(b2 === col ? [vestir(B2, col)] : []),
  ]
  return [
    ['pendiente', 'Pendiente', [...FIJAS.pendiente, ...en('pendiente')]],
    ['haciendola', 'Haciéndola', en('haciendola')],
    ['comprobar', 'Para comprobar', en('comprobar')],
    ['finalizada', 'Finalizada', FIJAS.finalizada],
  ]
}

const PROYECTOS = [
  ['mi-app', 3, true],
  ['Tienda', 7, false],
  ['Blog', 2, false],
]

export default function BoardVivo() {
  const [ref, paso, vivo] = usePasos(DURACIONES, FOTO)
  const cols = columnas(paso)
  const esperando = cols[2][2].length
  const trabajando = cols[1][2].length
  const pos = useCursor(ref, paso, vivo, CURSOR)

  // En un teléfono el tablero no cabe y se desplaza de lado: sigue a la acción. Solo mueve el
  // tablero, nunca la página.
  useEffect(() => {
    const t = ref.current
    if (!vivo || !t || t.scrollWidth <= t.clientWidth) return
    const col = t.querySelector(paso >= 8 ? '[data-col="haciendola"]' : '[data-col="pendiente"]')
    t.scrollTo({ left: col.offsetLeft - 14, behavior: 'smooth' })
  }, [ref, vivo, paso])

  return (
    <div
      className="ventana"
      role="img"
      aria-label="CotejoBoard en marcha: le pides dos tareas al maestro, aparecen en Pendiente, las arrastras a Haciéndola, dos agentes trabajan en paralelo y la primera entrega queda esperando que la compruebes."
    >
      <div className="ventana__cab" aria-hidden="true">
        <div className="ventana__titulo">
          <span className="ventana__nombre">CotejoBoard</span>
          <span className={`ventana__estado${esperando ? ' ventana__estado--espera' : ''}`}>
            {esperando
              ? `${esperando} esperando que la${esperando > 1 ? 's' : ''} compruebes · mi-app`
              : trabajando
                ? `${trabajando} agente${trabajando > 1 ? 's' : ''} trabajando · mi-app`
                : 'mi-app'}
          </span>
        </div>
        <span className="ventana__buscar">
          <Icono nombre="buscar" tam={14} /> Buscar tareas <kbd>Ctrl F</kbd>
        </span>
        <span className="ventana__icono">
          <Icono nombre="mas" tam={16} />
        </span>
      </div>

      <div className="ventana__cuerpo" aria-hidden="true">
        <div className="ventana__lateral">
          <span className="ventana__rotulo">Proyectos</span>
          {PROYECTOS.map(([nombre, n, actual]) => (
            <span key={nombre} className={`ventana__proyecto${actual ? ' ventana__proyecto--actual' : ''}`}>
              <span>{nombre}</span>
              {actual && esperando > 0 && <b>{esperando}</b>}
              <i>{n}</i>
            </span>
          ))}
        </div>

        <div className="ventana__centro">
          <div className={`tablero${paso === 0 && vivo ? ' tablero--reinicia' : ''}`} ref={ref}>
            <LayoutGroup id="hero">
              {cols.map(([clave, nombre, fichas]) => (
                <Columna key={clave} clave={clave} nombre={nombre} fichas={fichas} vivo={vivo} agarrada={AGARRADA[paso]} />
              ))}
            </LayoutGroup>
            <Cursor pos={pos} agarra={!!AGARRADA[paso]} />
          </div>

          {vivo && paso >= 2 && paso <= 4 && (
            <div className="maestro-flota">
              <span className="maestro-flota__cab">Maestro · mi-app</span>
              <p>Apuntadas en Pendiente. Login → sonnet, bienvenida → haiku.</p>
            </div>
          )}

          <div className="ventana__pie">
            <span className="maestro-barra">
              {vivo && paso === 1 ? (
                <span className="maestro-barra__texto">
                  <Tecleada texto={PEDIDO} />
                </span>
              ) : (
                <span className="maestro-barra__hueco">Pídele algo al maestro de mi-app</span>
              )}
            </span>
            <span className={`maestro-enviar${vivo && paso === 2 ? ' maestro-enviar--pulsado' : ''}`}>
              Enviar <Icono nombre="abajo" tam={13} />
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
