import Hero from '../components/Hero.jsx'
import Demo from '../components/Demo.jsx'
import InicioPasos from '../components/InicioPasos.jsx'
import InicioAhorro from '../components/InicioAhorro.jsx'
import InicioPuertas from '../components/InicioPuertas.jsx'
import InicioCierre from '../components/InicioCierre.jsx'

// La portada (/): hero, demo y cuatro secciones cortas. Los componentes viejos de la portada
// (Beneficios, Medidor, Publicos, Trato, Instalar, Orbita, ConCualquierAgente) ya no se pintan;
// su limpieza es de otra tarea.
export default function Inicio() {
  return (
    <>
      <Hero />
      <Demo />
      <InicioPasos />
      <InicioAhorro />
      <InicioPuertas />
      <InicioCierre />
    </>
  )
}
