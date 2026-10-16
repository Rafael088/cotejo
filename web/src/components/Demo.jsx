import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { LayoutGroup, motion } from 'motion/react'
import Icono from './Icono.jsx'
import { COLUMNAS, FOTO, GUION, TECLA, aplicar, tras_devolver } from '../demo.js'

// La demo de la portada: la terminal del agente junto a CotejoBoard. El agente reparte y entrega
// solo; el check lo pone quien mira, con Aprobar o Devolver. La lógica es src/demo.js.
//
// El HTML prerenderizado (y el primer render del cliente, para que la hidratación cuadre) es
// FOTO: el guion ya aplicado, así que sin JavaScript se lee la historia entera. Con JavaScript,
// los botones aparecen y la demo vuelve a empezar cuando entra en pantalla; con
// prefers-reduced-motion se queda en la foto, sin animar, y los botones funcionan igual.

// Una línea que se escribe tecla a tecla, con el cursor al final mientras dura.
function Tecleada({ texto }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (n >= texto.length) return
    const t = setTimeout(() => setN(n + 1), TECLA)
    return () => clearTimeout(t)
  }, [n, texto])
  return (
    <>
      {texto.slice(0, n)}
      {n < texto.length && <span className="demo-cursor" aria-hidden="true" />}
    </>
  )
}

function Carta({ carta, interactiva, onAprobar, onDevolver }) {
  const { id, texto, modelo, estado, ev, motivo } = carta
  return (
    <motion.article
      layoutId={id}
      layout="position"
      transition={{ duration: 0.62, ease: [0.16, 1, 0.3, 1] }}
      className={`demo-carta demo-carta--${estado}${estado === 'entregada' && interactiva ? ' demo-carta--tuturno' : ''}`}
    >
      {estado === 'hecha' && (
        <span className="demo-carta__check">
          <Icono nombre="check" tam={16} />
          <span className="sr-only">Hecha</span>
        </span>
      )}
      <p className="demo-carta__t">{texto}</p>
      <div className="demo-chips">
        <span className="demo-chip">{id}</span>
        <span className="demo-chip demo-chip--borde">{modelo}</span>
      </div>
      {ev && <div className="demo-carta__ev">{ev}</div>}
      {motivo && <span className="demo-carta__motivo">devuelta · {motivo}</span>}
      {estado === 'entregada' && interactiva && (
        <div className="demo-carta__acciones">
          <button className="demo-mini demo-mini--senal" type="button" onClick={() => onAprobar(id)}>
            Aprobar
          </button>
          <button className="demo-mini" type="button" onClick={() => onDevolver(id)}>
            Devolver
          </button>
        </div>
      )}
    </motion.article>
  )
}

export default function Demo() {
  const [estado, despachar] = useReducer(aplicar, FOTO)
  const [interactiva, setInteractiva] = useState(false)
  const quieto = useRef(false)
  const temporizadores = useRef([])
  const raiz = useRef(null)
  const tablero = useRef(null)

  const limpiar = () => {
    temporizadores.current.forEach(clearTimeout)
    temporizadores.current = []
  }
  // Corre [ms, acciones] desde ahora; con movimiento reducido, todo de golpe.
  const programar = useCallback((pasos) => {
    for (const [ms, acciones] of pasos) {
      const hacer = () => acciones.forEach((a) => despachar({ ...a, animar: !quieto.current }))
      if (quieto.current) hacer()
      else temporizadores.current.push(setTimeout(hacer, ms))
    }
  }, [])
  const correr = useCallback(() => {
    limpiar()
    despachar({ t: 'reiniciar' })
    programar(GUION)
  }, [programar])

  useEffect(() => {
    setInteractiva(true)
    quieto.current = matchMedia('(prefers-reduced-motion: reduce)').matches
    if (quieto.current) return limpiar
    // Empieza cuando se ve: si arrancara al cargar, quien baja despacio llegaría al final.
    const ojo = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return
        ojo.disconnect()
        correr()
      },
      { threshold: 0.35 },
    )
    ojo.observe(raiz.current)
    return () => {
      ojo.disconnect()
      limpiar()
    }
  }, [correr])

  // En un teléfono el tablero no cabe y se desplaza de lado: que enseñe la columna donde está
  // el turno de quien mira (Para comprobar) y, al acabar, Finalizada. Solo mueve el tablero.
  const enComprobar = estado.cartas.filter((c) => c.col === 'comprobar').length
  useEffect(() => {
    const t = tablero.current
    if (!interactiva || !t || t.scrollWidth <= t.clientWidth) return
    const col = t.querySelector(estado.fin ? '.demo-col--finalizada' : enComprobar ? '.demo-col--comprobar' : '.demo-col--pendiente')
    t.scrollTo({ left: col.offsetLeft - 14, behavior: quieto.current ? 'auto' : 'smooth' })
  }, [interactiva, enComprobar, estado.fin])

  const aprobar = (id) => despachar({ t: 'aprobar', id })
  const devolver = (id) => {
    despachar({ t: 'devolver', id, animar: !quieto.current })
    programar(tras_devolver(id))
  }

  return (
    <div className="demo-marco">
      <div className="demo" ref={raiz} role="group" aria-label="Demostración: un día con Cotejo">
        <div className="demo__barra">
          <span className="demo__lado">tu agente · terminal</span>
          {interactiva && estado.fin && (
            <button className="demo__repetir" type="button" onClick={correr}>
              <Icono nombre="repetir" tam={14} />
              Otra vez
            </button>
          )}
          <span className="demo__lado demo__lado--der">CotejoBoard · mi-app</span>
        </div>
        <div className="demo__cuerpo">
          <div className="demo-term" aria-live="off">
            {estado.lineas.map((l) => (
              <motion.div
                key={l.n}
                className={`demo-term__l demo-term__l--${l.clase}`}
                initial={l.animar ? { opacity: 0, y: 4 } : false}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
              >
                {l.animar && l.clase === 'yo' ? <Tecleada texto={l.texto} /> : l.texto}
              </motion.div>
            ))}
          </div>
          <div className="demo-board" ref={tablero} tabIndex={0} aria-label="Tablero de mi-app">
            <LayoutGroup>
              {COLUMNAS.map(([col, nombre]) => {
                const cartas = estado.cartas.filter((c) => c.col === col)
                return (
                  <div key={col} className={`demo-col demo-col--${col}`}>
                    <div className="demo-col__cab">
                      <span className="demo-col__nombre">{nombre}</span>
                      <span className="demo-col__n">{cartas.length}</span>
                    </div>
                    <div className="demo-col__cartas">
                      {cartas.map((c) => (
                        <Carta key={c.id} carta={c} interactiva={interactiva} onAprobar={aprobar} onDevolver={devolver} />
                      ))}
                    </div>
                  </div>
                )
              })}
            </LayoutGroup>
          </div>
        </div>
        <div className="demo__pie">
          <span className="demo__paso">{estado.paso}/4</span>
          <p aria-live="polite">{estado.leyenda}</p>
        </div>
      </div>
    </div>
  )
}
