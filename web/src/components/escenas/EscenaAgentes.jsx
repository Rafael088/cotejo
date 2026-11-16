import { LayoutGroup } from 'motion/react'
import { Columna, Cursor, useCursor, usePasos } from '../vivo.jsx'

// «Arrastra y un agente se pone a trabajar»: la columna Haciéndola de cerca. Dos agentes ya
// trabajan; arrastras una tercera tarea y, como no hay memoria libre, espera. Cuando el primero
// entrega, le toca.

//                 0     1    2    3     4     5
const DURACIONES = [1500, 800, 900, 2400, 2000, 3600]
const FOTO = 3
const CURSOR = { 1: '[data-ficha="x3"]', 2: '[data-ficha="x3"]' }

const X1 = {
  id: 'x1',
  texto: 'Página de precios',
  modelo: 'sonnet',
  rama: 'cotejo/x1',
  lineas: ['Read src/precios/planes.ts', 'Edit src/precios/Tabla.tsx', 'Bash npm test', '9 pruebas ok'],
}
const X2 = {
  id: 'x2',
  texto: 'Arreglar el pie en móvil',
  modelo: 'haiku',
  rama: 'cotejo/x2',
  lineas: ['Read src/Pie.tsx', 'Edit src/pie.css', 'Bash npm run build', 'Read src/Pie.tsx', 'Edit src/Pie.tsx'],
}
const X3 = {
  id: 'x3',
  texto: 'Exportar a CSV',
  modelo: 'deepseek',
  lineas: ['worktree cotejo/x3', 'Read src/informes/tabla.ts', 'Write src/informes/csv.ts'],
}

function columnas(paso) {
  const x1 = paso >= 4 ? { ...X1, rama: undefined, lineas: undefined, estado: 'entregada', ev: 'commit 7be20d · 9 pruebas ok' } : { ...X1, estado: 'viva' }
  const x3 = paso >= 5 ? { ...X3, rama: 'cotejo/x3', estado: 'viva' } : paso >= 2 ? { ...X3, estado: 'cola' } : X3
  return [
    ['pendiente', 'Pendiente', [{ id: 'x0', texto: 'Probar en Windows', modelo: 'persona' }, ...(paso < 2 ? [x3] : [])]],
    ['haciendola', 'Haciéndola', [...(paso < 4 ? [x1] : []), { ...X2, estado: 'viva' }, ...(paso >= 2 ? [x3] : [])]],
    ['comprobar', 'Para comprobar', paso >= 4 ? [x1] : []],
  ]
}

export default function EscenaAgentes() {
  const [ref, paso, vivo] = usePasos(DURACIONES, FOTO)
  const pos = useCursor(ref, paso, vivo, CURSOR)
  const cols = columnas(paso)
  const enCola = paso >= 2 && paso < 5
  return (
    <div
      className="escena escena--tablero"
      role="img"
      aria-label="Dos agentes trabajan en paralelo en Haciéndola, cada uno en su worktree. Una tercera tarea arrastrada espera en cola hasta que hay memoria libre."
    >
      <div className="escena__tablero escena__tablero--agentes" ref={ref} aria-hidden="true">
        <LayoutGroup id="agentes">
          {cols.map(([clave, nombre, fichas]) => (
            <Columna
              key={clave}
              clave={clave}
              nombre={nombre}
              fichas={fichas}
              vivo={vivo}
              agarrada={paso === 2 ? 'x3' : null}
              pie={
                clave === 'haciendola' && (
                  <p className="col__capacidad">
                    <span className="col__huecos">
                      <i />
                      <i />
                    </span>
                    Caben 2 a la vez{enCola ? ' · 1 en cola' : ''}
                  </p>
                )
              }
            />
          ))}
        </LayoutGroup>
        <Cursor pos={pos} agarra={paso === 2} />
      </div>
    </div>
  )
}
