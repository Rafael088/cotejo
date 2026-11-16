import Hero from '../components/Hero.jsx'
import Agentes from '../components/Agentes.jsx'
import Funciones from '../components/Funciones.jsx'
import CierrePortada from '../components/CierrePortada.jsx'

// La portada (/): el producto en marcha, con qué agentes funciona, cinco funciones demostradas
// y el comando otra vez. Lo de «cómo se usa» vive en /docs.
export default function Inicio() {
  return (
    <>
      <Hero />
      <Agentes />
      <Funciones />
      <CierrePortada />
    </>
  )
}
