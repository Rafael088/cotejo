import Cabecera from './components/Cabecera.jsx'
import Hero from './components/Hero.jsx'
import Medidor from './components/Medidor.jsx'
import Trato from './components/Trato.jsx'
import Orbita from './components/Orbita.jsx'
import Instalar from './components/Instalar.jsx'
import Publicos from './components/Publicos.jsx'
import ConCualquierAgente from './components/ConCualquierAgente.jsx'
import Pie from './components/Pie.jsx'

export default function App() {
  return (
    <>
      <a className="saltar" href="#contenido">Saltar al contenido</a>
      <Cabecera />
      <main id="contenido">
        <Hero />
        <Medidor />
        <Publicos />
        <Trato />
        <Instalar />
        <Orbita />
        <ConCualquierAgente />
      </main>
      <Pie />
    </>
  )
}
