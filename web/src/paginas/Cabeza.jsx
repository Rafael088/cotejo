// El arranque de las páginas interiores: su <h1> y la bajada, en una <section> con título para
// que el prerender lo encuentre (scripts/comprobar-prerender.mjs).
export default function Cabeza({ id, titulo, bajada, children }) {
  return (
    <section className="seccion" aria-labelledby={id}>
      <div className="seccion__cabeza">
        <h1 id={id} className="titulo-2">{titulo}</h1>
        <p className="parrafo">{bajada}</p>
      </div>
      {children}
    </section>
  )
}
