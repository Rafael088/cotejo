import InstalarRapido from './InstalarRapido.jsx'

// La entrada es CSS (.aparece en styles.css, con su retraso en --retraso), no motion: el HTML
// prerenderizado llega visible y la animación solo corre si index.html marcó <html class="js">
// antes de pintar. Así, sin JavaScript, nada arriba del pliegue arranca en opacity:0.

export default function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-titulo">
      <div className="hero__texto">
        <h1 id="hero-titulo" className="hero__titular aparece" style={{ '--retraso': '0s' }}>
          El tablero de control para tu vibe coding.
        </h1>
        <p className="hero__bajada aparece" style={{ '--retraso': '0.1s' }}>
          Tus agentes escriben el código. Cotejo ordena el proyecto, reparte las tareas y no da
          nada por hecho hasta que tú lo revisas.
        </p>
      </div>

      <InstalarRapido
        id="instalar"
        nota="Gratis · beta"
        pie="Linux y Windows. Sin terminal y sin administrador."
        className="aparece"
        style={{ '--retraso': '0.2s' }}
      />
    </section>
  )
}
