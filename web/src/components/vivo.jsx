import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import Icono from './Icono.jsx'

// Lo que comparten las escenas vivas de la portada (el board del hero y las de la rejilla): un
// guion por pasos que solo corre en pantalla, el cursor que arrastra y la ficha del board.
//
// Regla común: el HTML prerenderizado y el primer render son la «foto» (un paso elegido que se
// lee solo). Con JavaScript y sin prefers-reduced-motion, al entrar en pantalla la escena
// vuelve al paso 0 y corre en bucle; fuera de pantalla se detiene.

export const MUELLE = { duration: 0.7, ease: [0.16, 1, 0.3, 1] }

// [ref, paso, vivo]: `duraciones[i]` es lo que dura el paso i en ms; `foto`, el paso quieto.
export function usePasos(duraciones, foto) {
  const ref = useRef(null)
  const [paso, setPaso] = useState(foto)
  const [vivo, setVivo] = useState(false)
  const [enVista, setEnVista] = useState(false)

  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const ojo = new IntersectionObserver(([e]) => setEnVista(e.isIntersecting), { threshold: 0.25 })
    ojo.observe(ref.current)
    return () => ojo.disconnect()
  }, [])

  useEffect(() => {
    if (!enVista || vivo) return
    setVivo(true)
    setPaso(0)
  }, [enVista, vivo])

  useEffect(() => {
    if (!vivo || !enVista) return
    const t = setTimeout(() => setPaso((p) => (p + 1) % duraciones.length), duraciones[paso])
    return () => clearTimeout(t)
  }, [vivo, enVista, paso, duraciones])

  return [ref, paso, vivo]
}

// Posición de `el` dentro de `raiz` por offsets: no la alteran las transformaciones con que
// Motion anima el cambio de columna, así que da el sitio final de la ficha, no el intermedio.
function desde(el, raiz) {
  let x = 0
  let y = 0
  while (el && el !== raiz) {
    x += el.offsetLeft
    y += el.offsetTop
    el = el.offsetParent
  }
  return { x, y }
}

// Dónde está el cursor en cada paso: `mapa[paso]` es un selector dentro de `raiz` (una ficha se
// agarra por arriba; un botón, por el centro) o nada, y entonces el cursor se esconde.
export function useCursor(raiz, paso, vivo, mapa) {
  const [pos, setPos] = useState(null)
  useLayoutEffect(() => {
    if (!vivo || !raiz.current) return
    const el = mapa[paso] && raiz.current.querySelector(mapa[paso])
    if (!el) {
      setPos((p) => p && { ...p, oculto: true })
      return
    }
    const { x, y } = desde(el, raiz.current)
    const boton = el.offsetHeight < 44
    setPos({
      x: x + (boton ? el.offsetWidth / 2 : Math.min(el.offsetWidth * 0.62, el.offsetWidth - 18)),
      y: y + (boton ? el.offsetHeight / 2 : 26),
      oculto: false,
    })
  }, [raiz, paso, vivo, mapa])
  return pos
}

export function Cursor({ pos, agarra }) {
  if (!pos) return null
  return (
    <span
      className="cursor"
      data-oculto={pos.oculto || undefined}
      data-agarra={agarra || undefined}
      style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 3.5l13.5 8.2-6 1.3-3 5.6z" fill="#fff" stroke="#101114" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    </span>
  )
}

// Texto que se escribe solo. Se monta de nuevo (key) para volver a empezar.
export function Tecleada({ texto, ms = 34 }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (n >= texto.length) return
    const t = setTimeout(() => setN(n + 1), ms)
    return () => clearTimeout(t)
  }, [n, texto, ms])
  return (
    <>
      {texto.slice(0, n)}
      <span className="caret" aria-hidden="true" />
    </>
  )
}

// Lo que el agente va haciendo, en la ficha: la línea de ahora y la anterior.
function Actividad({ lineas, vivo }) {
  const [n, setN] = useState(vivo ? 0 : lineas.length - 1)
  useEffect(() => {
    if (!vivo || n >= lineas.length - 1) return
    const t = setTimeout(() => setN(n + 1), 900)
    return () => clearTimeout(t)
  }, [n, vivo, lineas])
  return (
    <div className="ficha__act">
      <span className="ficha__act-antes">{lineas[n - 1] ?? ' '}</span>
      <span className="ficha__act-ahora" key={n}>
        <i className="pulso" />
        {lineas[n]}
      </span>
    </div>
  )
}

// Una ficha del board. `estado`: normal | viva (un agente trabajando) | cola | entregada |
// devuelta | hecha. Cambia de columna animada por su layoutId (dentro de un LayoutGroup con id).
export function Ficha({ c, vivo, agarrada, children }) {
  const { id, texto, modelo, dif, rama, estado = 'normal', lineas, ev, motivo } = c
  return (
    <motion.article
      layoutId={id}
      layout="position"
      transition={MUELLE}
      data-ficha={id}
      className={`ficha ficha--${estado}${agarrada ? ' ficha--agarrada' : ''}${c.nueva ? ' ficha--nueva' : ''}`}
    >
      <div className="ficha__cab">
        <p className="ficha__t">{texto}</p>
        {estado === 'hecha' && <Icono nombre="check" tam={15} className="ficha__check" />}
      </div>
      {(modelo || dif || rama) && (
        <div className="ficha__chips">
          {modelo && (
            <span className={`f-chip f-chip--borde${modelo === 'persona' ? ' f-chip--persona' : ''}`}>
              <Icono nombre={modelo === 'persona' ? 'persona' : 'agente'} tam={11} />
              {modelo}
            </span>
          )}
          {rama && <span className="f-chip">{rama}</span>}
          {dif && <span className="f-chip">{dif}</span>}
        </div>
      )}
      {(estado === 'viva' || estado === 'devuelta') && lineas && <Actividad lineas={lineas} vivo={vivo} />}
      {estado === 'cola' && <p className="ficha__cola">En cola · espera memoria libre</p>}
      {ev && <div className="ficha__ev">{ev}</div>}
      {motivo && (
        <p className="ficha__motivo">
          <span>Devuelta</span> {motivo}
        </p>
      )}
      {children}
    </motion.article>
  )
}

// Una columna del board con sus fichas.
export function Columna({ clave, nombre, fichas, vivo, agarrada, pie, render }) {
  return (
    <div className={`col col--${clave}`} data-col={clave}>
      <div className="col__cab">
        <span className="col__nombre">{nombre}</span>
        <span className="col__n">{fichas.length}</span>
      </div>
      <div className="col__fichas">
        {fichas.map((c) => (
          <Ficha key={c.id} c={c} vivo={vivo} agarrada={agarrada === c.id}>
            {render?.(c)}
          </Ficha>
        ))}
      </div>
      {pie}
    </div>
  )
}
