import { Logo } from './Logo.jsx'
import Tablero from './Tablero.jsx'
import InstalarRapido from './InstalarRapido.jsx'
import Icono from './Icono.jsx'

// La entrada es CSS (.aparece en styles.css, con su retraso en --retraso), no motion: el HTML
// prerenderizado llega visible y la animación solo corre si index.html marcó <html class="js">
// antes de pintar. Así, sin JavaScript, nada arriba del pliegue arranca en opacity:0.

export default function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-titulo">
      <div className="hero__fondo" aria-hidden="true">
        <Tablero />
      </div>
      <div className="hero__velo" aria-hidden="true" />

      <div className="hero__centro">
        <div className="aparece" style={{ '--retraso': '0s' }}>
          <Logo alto={72} animado className="hero__logo" />
        </div>
        <h1 id="hero-titulo" className="hero__titulo aparece" style={{ '--retraso': '0.12s' }}>
          Tus agentes entregan. <span className="hero__titulo-tu">Tú compruebas.</span>
        </h1>
        <p className="hero__bajada aparece" style={{ '--retraso': '0.22s' }}>
          Cotejo es el tablero de control para hacer vibe coding profesional. Tus agentes escriben
          el código; Cotejo organiza el proyecto y verifica lo que entregan. El check lo pones tú.
        </p>

        <InstalarRapido
          titulo="Instálalo: pega un comando en una terminal"
          coletilla="Gratis, versión beta. ¿No usas la terminal? Pídele a tu agente que lo instale."
          className="aparece"
          style={{ '--retraso': '0.34s' }}
        />

        <a href="#ahorro" className="hero__seguir aparece" style={{ '--retraso': '0.5s' }}>
          Mira cuánto ahorra <Icono nombre="abajo" tam={16} />
        </a>
      </div>
    </section>
  )
}
