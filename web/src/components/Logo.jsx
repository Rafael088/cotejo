import { useId } from 'react'
import { LOGO_VIEWBOX, C_PATH, C_ARCO, CHECK_POINTS, OTEJO_PATH, OTEJO_TRANSFORM } from '../marca.js'

// Los tiempos de la animación (en styles.css, .logo-anima) son los de arranque del board
// (tareas/marca.py): la C se dibuja desde su punta de abajo y el check entra a cerrarla cuando
// la C está terminando.

// El logo: la C la trae el agente, el check lo pone la persona. Con `animado`, la C se dibuja y
// el check entra a cerrarla, que es la animación de arranque de la marca (la misma del board).
// La animación es CSS (.logo-anima en styles.css) y parte del logo entero: el prerender lo deja
// visible sin JavaScript, el marcado es el mismo en el servidor y al hidratar, y con movimiento
// reducido se ve entero desde el principio.
export function Logo({ alto = 64, animado = false, className = '' }) {
  const [x, y, w, h] = LOGO_VIEWBOX.split(' ').map(Number)
  const mascara = `c-${useId().replace(/:/g, '')}`
  return (
    <svg
      className={`${className} ${animado ? 'logo-anima' : ''}`.trim()}
      viewBox={LOGO_VIEWBOX}
      height={alto}
      width={(alto * w) / h}
      role="img"
      aria-label="Cotejo"
    >
      {animado && (
        <mask id={mascara} maskUnits="userSpaceOnUse" x={x} y={y} width={w} height={h}>
          <path className="logo-anima__c" pathLength="1" d={C_ARCO} fill="none" stroke="#fff" strokeWidth="220" />
        </mask>
      )}
      <path d={C_PATH} fill="var(--texto)" mask={animado ? `url(#${mascara})` : undefined} />
      <path transform={OTEJO_TRANSFORM} d={OTEJO_PATH} fill="var(--texto)" />
      <polyline
        className={animado ? 'logo-anima__check' : undefined}
        pathLength={animado ? '1' : undefined}
        points={CHECK_POINTS}
        fill="none"
        stroke="var(--senal)"
        strokeWidth="140"
        strokeLinecap="round"
        strokeLinejoin="round"
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
