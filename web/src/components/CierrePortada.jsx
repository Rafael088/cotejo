import Instalar from './Instalar.jsx'

// El cierre de la portada: el comando otra vez, sin repetir el ancla «instalar» del hero.
export default function CierrePortada() {
  return (
    <section className="cierre" id="cierre" aria-labelledby="cierre-titulo">
      <h2 id="cierre-titulo" className="cierre__titulo">
        Instálalo y arrastra tu primera tarea.
      </h2>
      <Instalar />
    </section>
  )
}
