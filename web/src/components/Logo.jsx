import { LOGO_VIEWBOX, C_PATH, CHECK_POINTS, OTEJO_PATH, OTEJO_TRANSFORM } from '../marca.js'

// El logo: la C la trae el agente, el check lo pone la persona.
export function Logo({ alto = 64, className = '' }) {
  const [, , w, h] = LOGO_VIEWBOX.split(' ').map(Number)
  return (
    <svg className={className || undefined} viewBox={LOGO_VIEWBOX} height={alto} width={(alto * w) / h} role="img" aria-label="Cotejo">
      <path d={C_PATH} fill="var(--texto)" />
      <path transform={OTEJO_TRANSFORM} d={OTEJO_PATH} fill="var(--texto)" />
      <polyline
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
