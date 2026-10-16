import { StrictMode } from 'react'
import { MotionConfig } from 'motion/react'
import App from './App.jsx'

// El mismo árbol para el prerender (entrada-servidor.jsx) y para hidratar (main.jsx): si
// difieren, React descuadra la hidratación y los useId del logo no coinciden.
export default function Raiz({ ruta }) {
  return (
    <StrictMode>
      <MotionConfig reducedMotion="user">
        <App ruta={ruta} />
      </MotionConfig>
    </StrictMode>
  )
}
