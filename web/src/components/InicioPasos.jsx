import Icono from './Icono.jsx'
import { enlace } from '../paginas.js'

// Portada · «De cero a tu primera entrega»: tres pasos, poco texto (diseño aprobado).
const PASOS = [
  ['curl … | sh', 'Instala Cotejo.', 'Un comando, o pídeselo a tu agente.'],
  ['«empiezo un proyecto»', 'Arranca el proyecto.', 'Tu agente te hace cinco preguntas y deja el plan escrito.'],
  ['CotejoBoard', 'Revisa y aprueba.', 'Cada entrega llega con pruebas y un resumen claro.'],
]

export default function InicioPasos() {
  return (
    <section className="seccion" id="pasos" aria-labelledby="pasos-titulo">
      <div className="seccion__cabeza">
        <h2 id="pasos-titulo" className="titulo-2">De cero a tu primera entrega.</h2>
      </div>
      <ol className="ini-pasos">
        {PASOS.map(([marca, titulo, texto]) => (
          <li key={titulo}>
            <span className="ini-pasos__marca">{marca}</span>
            <h3 className="titulo-3">{titulo}</h3>
            <p>{texto}</p>
          </li>
        ))}
      </ol>
      <p className="ini-enlace">
        <a className="enlace-flecha" href={enlace('/primerospasos')}>
          Primeros pasos <Icono nombre="flecha" />
        </a>
      </p>
    </section>
  )
}
