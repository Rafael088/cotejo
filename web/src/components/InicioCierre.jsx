import InstalarRapido from './InstalarRapido.jsx'

// Portada · cierre: el mismo bloque de instalación del hero (sin repetir su ancla «instalar»).
export default function InicioCierre() {
  return (
    <section className="seccion" id="cierre" aria-labelledby="cierre-titulo">
      <div className="ini-cierre">
        <h2 id="cierre-titulo" className="titulo-2">Instálalo y pregúntale a tu agente qué falta.</h2>
        <InstalarRapido nota="Linux y Windows 10/11" pie="Después, abre tu agente y pregúntale qué falta." />
      </div>
    </section>
  )
}
