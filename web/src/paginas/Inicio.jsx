import Hero from '../components/Hero.jsx'
import Demo from '../components/Demo.jsx'
import Beneficios from '../components/Beneficios.jsx'
import Medidor from '../components/Medidor.jsx'
import Trato from '../components/Trato.jsx'
import Orbita from '../components/Orbita.jsx'
import Instalar from '../components/Instalar.jsx'
import Publicos from '../components/Publicos.jsx'
import ConCualquierAgente from '../components/ConCualquierAgente.jsx'

// La portada (/). El rediseño la rehace por partes: hero, demo y el resto de secciones.
export default function Inicio() {
  return (
    <>
      <Hero />
      <Demo />
      <Beneficios />
      <Medidor />
      <Publicos />
      <Trato />
      <Instalar />
      <Orbita />
      <ConCualquierAgente />
    </>
  )
}
