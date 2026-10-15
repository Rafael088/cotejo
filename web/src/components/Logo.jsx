import { useId } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { LOGO_VIEWBOX, C_PATH, C_ARCO, CHECK_POINTS, OTEJO_PATH, OTEJO_TRANSFORM } from '../marca.js'

// Los mismos tiempos que la animación de arranque del board (tareas/marca.py): la C se dibuja
// desde su punta de abajo y el check entra a cerrarla cuando la C está terminando.
const SALIR_SUAVE = [0.33, 1, 0.68, 1]
const C_ANIMADA = { delay: 0.1, duration: 0.4, ease: SALIR_SUAVE }
const CHECK_ANIMADO = { delay: 0.39, duration: 0.36, ease: SALIR_SUAVE }

// El logo: la C la trae el agente, el check lo pone la persona. Con `animado`, la C se dibuja y
// el check entra a cerrarla, que es la animación de arranque de la marca (la misma del board).
// Con movimiento reducido se ve entero desde el principio.
export function Logo({ alto = 64, animado = false, className = '' }) {
  const [x, y, w, h] = LOGO_VIEWBOX.split(' ').map(Number)
  const reducido = useReducedMotion()
  const anima = animado && !reducido
  const mascara = `c-${useId().replace(/:/g, '')}`
  return (
    <svg
      className={className}
      viewBox={LOGO_VIEWBOX}
      height={alto}
      width={(alto * w) / h}
      role="img"
      aria-label="Cotejo"
    >
      {anima && (
        <mask id={mascara} maskUnits="userSpaceOnUse" x={x} y={y} width={w} height={h}>
          <motion.path
            d={C_ARCO}
            fill="none"
            stroke="#fff"
            strokeWidth="220"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={C_ANIMADA}
          />
        </mask>
      )}
      <path d={C_PATH} fill="var(--texto)" mask={anima ? `url(#${mascara})` : undefined} />
      <path transform={OTEJO_TRANSFORM} d={OTEJO_PATH} fill="var(--texto)" />
      <motion.polyline
        points={CHECK_POINTS}
        fill="none"
        stroke="var(--senal)"
        strokeWidth="140"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={anima ? { pathLength: 0 } : false}
        animate={{ pathLength: 1 }}
        transition={CHECK_ANIMADO}
      />
    </svg>
  )
}

// La C sola, para el centro de la órbita y la cabecera.
export function Marca({ tam = 40, className = '' }) {
  return (
    <svg className={className} viewBox="0 0 100 100" width={tam} height={tam} role="img" aria-label="Cotejo">
      <g transform="translate(-0.14 91.76) scale(0.09634)">
        <path d={C_PATH} fill="var(--texto)" />
        <polyline
          points={CHECK_POINTS}
          fill="none"
          stroke="var(--senal)"
          strokeWidth="140"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </svg>
  )
}
