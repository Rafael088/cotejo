import { AnimatePresence, motion } from 'motion/react'
import Icono from './Icono.jsx'

// El botón «Copiar» de una línea de terminal o de una frase, con su aviso para lectores de pantalla.
export default function BotonCopiar({ estado, onClick, texto, className }) {
  return (
    <>
      <button type="button" className={className} onClick={onClick} aria-label={`Copiar: ${texto}`}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={estado}
            className="comando__boton-cara"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }}
          >
            {estado === 'copiado' ? (
              <><Icono nombre="check" tam={16} /> Copiado</>
            ) : estado === 'error' ? (
              <>Selecciónalo a mano</>
            ) : (
              <><Icono nombre="copiar" tam={16} /> Copiar</>
            )}
          </motion.span>
        </AnimatePresence>
      </button>
      <span className="sr-only" aria-live="polite">
        {estado === 'copiado' ? 'Copiado' : estado === 'error' ? 'No se pudo copiar: texto seleccionado' : ''}
      </span>
    </>
  )
}
