import { useEffect, useRef } from 'react'
import Instalar from './Instalar.jsx'
import BoardVivo from './BoardVivo.jsx'
import { VIDEO_HERO } from '../config.js'

// La entrada del texto es CSS (.aparece en styles.css, con su retraso en --retraso), no motion:
// el HTML prerenderizado llega visible y la animación solo corre si index.html marcó
// <html class="js"> antes de pintar. Así, sin JavaScript, nada arriba del pliegue arranca oculto.

// El video real de CotejoBoard (config.js, VIDEO_HERO). Con prefers-reduced-motion no arranca
// solo: se queda en el póster, con controles para quien quiera verlo.
function VideoHero({ video }) {
  const ref = useRef(null)
  const base = import.meta.env.BASE_URL
  useEffect(() => {
    const v = ref.current
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) return
    v.pause()
    v.controls = true
  }, [])
  return (
    <div className="ventana ventana--video">
      <video
        ref={ref}
        className="hero__video"
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        poster={`${base}${video.poster}`}
        width={video.ancho}
        height={video.alto}
        aria-label="CotejoBoard en marcha: le pides tareas al maestro, aparecen en Pendiente, las arrastras a Haciéndola y los agentes arrancan."
      >
        {video.webm && <source src={`${base}${video.webm}`} type="video/webm" />}
        <source src={`${base}${video.mp4}`} type="video/mp4" />
      </video>
    </div>
  )
}

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
        {VIDEO_HERO ? <VideoHero video={VIDEO_HERO} /> : <BoardVivo />}
      </div>
    </section>
  )
}
