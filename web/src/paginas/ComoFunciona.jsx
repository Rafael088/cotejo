import { useEffect, useState } from 'react'
import CfHistoria from '../components/CfHistoria.jsx'
import CfCiclo from '../components/CfCiclo.jsx'
import Cierre from '../components/Cierre.jsx'

// /comofunciona: un selector No programo / Programo y, debajo, el panel de cada público.
// La portada enlaza aquí con ?publico=no|si y eso abre la pestaña; al cambiarla se reescribe
// el parámetro, para que el enlace que se copie abra la misma.
// El primer render (el del prerender y el de la hidratación) no sabe nada del navegador: abre
// «No programo». El panel de «Programo» va en el HTML con `hidden`, con todo su texto.
const PUBLICOS = [
  ['no', 'No programo'],
  ['si', 'Programo'],
]

export default function ComoFunciona() {
  const [montado, setMontado] = useState(false)
  const [quieto, setQuieto] = useState(false)
  const [publico, setPublico] = useState('no')

  useEffect(() => {
    setMontado(true)
    setQuieto(matchMedia('(prefers-reduced-motion: reduce)').matches)
    if (new URLSearchParams(location.search).get('publico') === 'si') setPublico('si')
  }, [])

  const elegir = (p) => {
    setPublico(p)
    const url = new URL(location.href)
    url.searchParams.set('publico', p)
    history.replaceState(null, '', url)
  }
  // Flechas entre las dos pestañas, como pide el patrón de tabs.
  const teclas = (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    const otro = publico === 'no' ? 'si' : 'no'
    elegir(otro)
    document.getElementById(`cf-tab-${otro}`)?.focus()
  }

  const panel = (p, contenido) => (
    <div
      id={`cf-panel-${p}`}
      className="cf-panel-publico"
      role="tabpanel"
      aria-labelledby={`cf-tab-${p}`}
      hidden={publico !== p}
    >
      {contenido}
    </div>
  )

  return (
    <>
      <section className="cf" aria-labelledby="t-cf">
        <div className="cf-cabeza">
          <h1 id="t-cf" className="cf-titular">
            Cómo funciona.
          </h1>
          <p className="cf-bajada">Tu agente trabaja. Cotejo lo ordena. Tú decides.</p>
          <div className="cf-selector" role="tablist" aria-label="Elige cómo trabajas" onKeyDown={teclas}>
            {PUBLICOS.map(([p, nombre]) => (
              <button
                key={p}
                id={`cf-tab-${p}`}
                role="tab"
                type="button"
                aria-selected={publico === p}
                aria-controls={`cf-panel-${p}`}
                tabIndex={publico === p ? 0 : -1}
                onClick={() => elegir(p)}
              >
                {nombre}
              </button>
            ))}
          </div>
        </div>

        {panel(
          'no',
          <>
            <CfHistoria montado={montado} quieto={quieto} activa={publico === 'no'} />
            <p className="cf-nota">
              Instalar pide pegar un comando en una terminal. Si prefieres no hacerlo, pídeselo a tu agente.
            </p>
          </>,
        )}
        {panel('si', <CfCiclo />)}
      </section>

      <Cierre id="empieza" titulo="Empieza con un comando." />
    </>
  )
}
