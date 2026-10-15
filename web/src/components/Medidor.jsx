import { useEffect, useRef } from 'react'
import { animate, motion, useInView, useMotionValue, useScroll, useTransform } from 'motion/react'
import { NOTA, RESPUESTA } from '../nota-ejemplo.js'
import { AHORRO, CONSULTA } from '../config.js'

const miles = (n) => Math.round(n).toLocaleString('de-DE')

function Cifra({ hasta, formato = miles, duracion = 1.6 }) {
  const ref = useRef(null)
  const visto = useInView(ref, { once: true, margin: '-15% 0px' })
  const valor = useMotionValue(0)
  const texto = useTransform(valor, formato)
  useEffect(() => {
    if (!visto) return
    const control = animate(valor, hasta, { duration: duracion, ease: [0.16, 1, 0.3, 1] })
    return () => control.stop()
  }, [visto, hasta, duracion, valor])
  return (
    <motion.span ref={ref} className="cifra">
      {texto}
    </motion.span>
  )
}

// Un cuadro = 100 tokens. Dos filas a la misma escala: así se ve la diferencia sin adjetivos.
function Escala() {
  const ref = useRef(null)
  const visto = useInView(ref, { once: true, margin: '-20% 0px' })
  const fila = (total, clase) => {
    const llenos = Math.floor(total / 100)
    const resto = (total % 100) / 100
    const cuadros = Array.from({ length: Math.ceil(total / 100) }, (_, i) => (i < llenos ? 1 : resto))
    return cuadros.map((lleno, i) => (
      <motion.span
        key={i}
        className={`escala__cuadro ${clase}`}
        style={{ '--lleno': lleno }}
        initial={{ opacity: 0, scale: 0.4 }}
        animate={visto ? { opacity: 1, scale: 1 } : {}}
        transition={{ delay: i * 0.018, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      />
    ))
  }
  return (
    <figure className="escala" ref={ref}>
      <div className="escala__fila">
        <span className="escala__nombre">Leer la nota</span>
        <div className="escala__cuadros">{fila(CONSULTA.nota, 'escala__cuadro--nota')}</div>
        <span className="escala__total">~{miles(CONSULTA.nota)}</span>
      </div>
      <div className="escala__fila">
        <span className="escala__nombre">cotejo tareas</span>
        <div className="escala__cuadros">{fila(CONSULTA.cli, 'escala__cuadro--cli')}</div>
        <span className="escala__total">~{miles(CONSULTA.cli)}</span>
      </div>
      <figcaption className="escala__pie">Cada cuadro, 100 tokens.</figcaption>
    </figure>
  )
}

export default function Medidor() {
  const panel = useRef(null)
  const { scrollYProgress } = useScroll({ target: panel, offset: ['start end', 'end start'] })
  const desplazar = useTransform(scrollYProgress, [0.1, 0.9], ['0%', '-62%'])

  const lineas = [
    ['esquema', 1],
    ['lecturas', AHORRO.lecturas],
    ['devuelto', AHORRO.devuelto],
    ['leido', AHORRO.leido],
  ]

  return (
    <section className="seccion medidor" id="ahorro" aria-labelledby="medidor-titulo">
      <div className="seccion__cabeza">
        <h2 id="medidor-titulo" className="titulo-2">
          Tu agente lee <span className="mono-cifra">480</span> tokens, no <span className="mono-cifra">4.700</span>.
        </h2>
        <p className="parrafo">
          Para saber qué falta en un proyecto, un agente sin Cotejo abre la nota entera: decisiones,
          reuniones, enlaces y, en algún sitio, las tareas. Con Cotejo pregunta y recibe solo las
          pendientes, en JSON.
        </p>
      </div>

      <div className="comparar" ref={panel}>
        <div className="comparar__panel comparar__panel--nota">
          <div className="comparar__barra">
            <span>Web de Cotejo.md</span>
            <span className="comparar__etiqueta">la nota entera</span>
          </div>
          <div className="comparar__nota" aria-hidden="true">
            <motion.pre style={{ y: desplazar }}>{NOTA}</motion.pre>
          </div>
          <div className="comparar__pie">
            <span><Cifra hasta={CONSULTA.nota} /> tokens</span>
          </div>
        </div>

        <div className="comparar__panel comparar__panel--cli">
          <div className="comparar__barra">
            <span>terminal</span>
            <span className="comparar__etiqueta">lo que devuelve Cotejo</span>
          </div>
          <div className="comparar__terminal">
            <code className="comparar__orden">
              <span className="comparar__prompt">$</span> cotejo tareas --proyecto "Web de Cotejo" --estado pendiente
            </code>
            <pre className="comparar__json">{RESPUESTA}</pre>
          </div>
          <p className="comparar__escala">Esto es todo. La nota de al lado sigue mucho más abajo.</p>
          <div className="comparar__pie">
            <span><Cifra hasta={CONSULTA.cli} /> tokens</span>
          </div>
        </div>
      </div>
      <p className="nota-al-pie">
        La nota y las tareas son de ejemplo. Las cifras son las que documenta Cotejo para un proyecto real.
      </p>

      <Escala />

      <div className="medido">
        <div className="medido__texto">
          <h3 className="titulo-3">Eso es una estimación. Esto está medido.</h3>
          <p className="parrafo">
            <code>cotejo ahorro</code> cuenta lo que la CLI devolvió de verdad contra lo que la
            fuente tuvo que leer para contestar. En cuatro lecturas en la máquina del autor:{' '}
            <strong>{miles(AHORRO.devuelto)}</strong> caracteres devueltos donde habría que haber leído{' '}
            <strong>{miles(AHORRO.leido)}</strong>.
          </p>
          <p className="parrafo parrafo--tenue">
            Lo único que no se mide es el supuesto de en medio: que sin Cotejo el agente habría leído
            esas notas enteras. Por eso viaja dentro del dato. Un ahorro que esconde su supuesto
            detrás de un total redondo es una medalla, no una medida.
          </p>
        </div>

        <div className="salida" role="img" aria-label={`Salida de cotejo ahorro: razón ${String(AHORRO.razon).replace('.', ',')}, ${miles(AHORRO.tokensAhorrados)} tokens ahorrados`}>
          <code className="salida__orden"><span className="comparar__prompt">$</span> cotejo ahorro</code>
          <div className="salida__json" aria-hidden="true">
            <span className="salida__llave">{'{'}</span>
            {lineas.map(([k, v]) => (
              <span key={k} className="salida__linea">
                <span className="salida__k">"{k}"</span>: <span className="salida__v">{v}</span>,
              </span>
            ))}
            <span className="salida__linea salida__linea--razon">
              <span className="salida__k">"razon":</span>
              <span className="salida__razon">
                <Cifra hasta={AHORRO.razon} formato={(n) => n.toFixed(1)} duracion={2} />
              </span>
              <span>,</span>
            </span>
            <span className="salida__linea">
              <span className="salida__k">"tokens_ahorrados"</span>: <span className="salida__v">{AHORRO.tokensAhorrados}</span>,
            </span>
            <span className="salida__linea">
              <span className="salida__k">"caracteres_por_token"</span>: <span className="salida__v">{AHORRO.caracteresPorToken}</span>,
            </span>
            <span className="salida__linea salida__linea--supuesto">
              <span className="salida__k">"supuesto"</span>: <span className="salida__s">"Lo medido son los caracteres que devolvió la CLI…"</span>
            </span>
            <span className="salida__llave">{'}'}</span>
          </div>
          <p className="salida__lectura">
            19,7× menos de lo que habría leído.{' '}
            <span>~{miles(AHORRO.tokensAhorrados)} tokens que no entraron al contexto.</span>
          </p>
        </div>
      </div>
    </section>
  )
}
