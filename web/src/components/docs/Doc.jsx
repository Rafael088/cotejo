import { useEffect, useState } from 'react'
import Icono from '../Icono.jsx'
import { GRUPOS, PAGINAS_DOCS, vecinas } from '../../docs.js'
import { enlace } from '../../enlace.js'

// El índice de /docs: los grupos con sus páginas. La página actual lleva aria-current.
function Indice({ ruta }) {
  return (
    <>
      {GRUPOS.map((g) => (
        <div className="docs-grupo" key={g.nombre}>
          <p className="docs-grupo__nombre">{g.nombre}</p>
          <ul>
            {g.paginas.map((p) => (
              <li key={p.ruta}>
                <a href={enlace(p.ruta)} aria-current={p.ruta === ruta ? 'page' : undefined}>
                  {p.titulo}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  )
}

// «En esta página»: los h2. Con JavaScript marca el que se está leyendo; sin él, es una lista de
// enlaces y ya.
function EnEstaPagina({ secciones }) {
  const [activa, setActiva] = useState(null)
  useEffect(() => {
    const titulos = secciones.map((s) => document.getElementById(s.id)).filter(Boolean)
    if (!titulos.length || !('IntersectionObserver' in window)) return
    const visibles = new Set()
    const obs = new IntersectionObserver(
      (entradas) => {
        for (const e of entradas) (e.isIntersecting ? visibles.add(e.target.id) : visibles.delete(e.target.id))
        const primero = secciones.find((s) => visibles.has(s.id))
        if (primero) setActiva(primero.id)
      },
      { rootMargin: '-72px 0px -65% 0px' },
    )
    titulos.forEach((t) => obs.observe(t))
    return () => obs.disconnect()
  }, [secciones])

  return (
    <nav className="docs-toc" aria-label="En esta página">
      <p className="docs-toc__titulo">En esta página</p>
      <ul>
        {secciones.map((s) => (
          <li key={s.id}>
            <a href={`#${s.id}`} aria-current={activa === s.id ? 'location' : undefined}>
              {s.titulo}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function Vecinas({ ruta }) {
  const { anterior, siguiente } = vecinas(ruta)
  return (
    <nav className="docs-vecinas" aria-label="Anterior y siguiente">
      {anterior ? (
        <a className="docs-vecina docs-vecina--antes" href={enlace(anterior.ruta)} rel="prev">
          <span className="docs-vecina__quien">Anterior</span>
          <span className="docs-vecina__titulo">{anterior.titulo}</span>
        </a>
      ) : (
        <span />
      )}
      {siguiente && (
        <a className="docs-vecina docs-vecina--despues" href={enlace(siguiente.ruta)} rel="next">
          <span className="docs-vecina__quien">Siguiente</span>
          <span className="docs-vecina__titulo">{siguiente.titulo}</span>
        </a>
      )}
    </nav>
  )
}

// La plantilla de toda página de /docs: barra lateral a la izquierda (un desplegable en móvil),
// el texto al centro con ancho de lectura y «En esta página» a la derecha. `secciones`: arreglos
// {id, titulo, hijos}; el h2 de cada una lleva su id y aria-labelledby apunta a él.
export default function Doc({ ruta, titulo, bajada, secciones }) {
  const actual = PAGINAS_DOCS.find((p) => p.ruta === ruta)
  return (
    <div className="docs">
      <details className="docs-movil">
        <summary>
          <span className="docs-movil__donde">
            <span className="docs-movil__docs">Docs</span>
            <span className="docs-movil__pagina">{actual?.titulo}</span>
          </span>
          <Icono nombre="abajo" tam={18} />
        </summary>
        <nav className="docs-movil__indice" aria-label="Docs">
          <Indice ruta={ruta} />
        </nav>
      </details>

      <nav className="docs-lateral" aria-label="Docs">
        <Indice ruta={ruta} />
      </nav>

      <article className="docs-cuerpo">
        <header className="docs-cabeza">
          <h1>{titulo}</h1>
          {bajada && <p className="docs-bajada">{bajada}</p>}
        </header>
        {secciones.map((s) => (
          <section key={s.id} className="docs-seccion" aria-labelledby={s.id}>
            <h2 id={s.id}>{s.titulo}</h2>
            {s.hijos}
          </section>
        ))}
        <Vecinas ruta={ruta} />
      </article>

      <EnEstaPagina secciones={secciones} />
    </div>
  )
}
