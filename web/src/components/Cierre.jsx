import InstalarRapido from './InstalarRapido.jsx'

// El cierre de una página: un titular y el mismo bloque de instalación del hero (sin repetir su
// ancla «instalar»). La portada y /comofunciona lo usan con su propio titular.
export default function Cierre({ id, titulo, nota, pie }) {
  return (
    <section className="seccion" id={id} aria-labelledby={`${id}-titulo`}>
      <div className="ini-cierre">
        <h2 id={`${id}-titulo`} className="titulo-2">
          {titulo}
        </h2>
        <InstalarRapido nota={nota} pie={pie} />
      </div>
    </section>
  )
}
