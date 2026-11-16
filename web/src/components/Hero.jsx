import Instalar from './Instalar.jsx'
import BoardVivo from './BoardVivo.jsx'

// La entrada del texto es CSS (.aparece en styles.css, con su retraso en --retraso), no motion:
// el HTML prerenderizado llega visible y la animación solo corre si index.html marcó
// <html class="js"> antes de pintar. Así, sin JavaScript, nada arriba del pliegue arranca oculto.

export default function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-titulo">
      <h1 id="hero-titulo" className="hero__titular aparece" style={{ '--retraso': '0s' }}>
        El tablero de control <span>para tu vibe coding.</span>
      </h1>
      <p className="hero__bajada aparece" style={{ '--retraso': '0.08s' }}>
        Tus agentes escriben el código. Tú decides qué está hecho.
      </p>
      <Instalar id="instalar" className="aparece" style={{ '--retraso': '0.16s' }} />
      <div className="hero__producto aparece" style={{ '--retraso': '0.26s' }}>
        <BoardVivo />
      </div>
    </section>
  )
}
