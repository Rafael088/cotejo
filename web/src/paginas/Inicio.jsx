import Hero from '../components/Hero.jsx'
import Demo from '../components/Demo.jsx'
import InicioPasos from '../components/InicioPasos.jsx'
import InicioAhorro from '../components/InicioAhorro.jsx'
import InicioPuertas from '../components/InicioPuertas.jsx'
import Cierre from '../components/Cierre.jsx'

// La portada (/): hero, demo y cuatro secciones cortas.
export default function Inicio() {
  return (
    <>
      <Hero />
      <Demo />
      <InicioPasos />
      <InicioAhorro />
      <InicioPuertas />
      <Cierre
        id="cierre"
        titulo="Instálalo y pregúntale a tu agente qué falta."
        nota="Linux y Windows 10/11"
        pie="Después, abre tu agente y pregúntale qué falta."
      />
    </>
  )
}
