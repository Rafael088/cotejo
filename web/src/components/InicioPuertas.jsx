import Icono from './Icono.jsx'
import { enlace } from '../paginas.js'

// Portada · «Programes o no, el check es tuyo»: dos puertas a /comofunciona (con ?publico=no|si,
// que esa página lee para abrir su pestaña) y los agentes compatibles.
const PUERTAS = [
  ['no', 'No programo', 'Tu agente hace lo técnico. Tú lees un resumen en lenguaje llano y decides.', 'Ver cómo'],
  ['si', 'Programo', 'Contexto en tu repo, un worktree por tarea y pruebas que se repiten.', 'Ver el ciclo'],
]
const AGENTES = ['Claude Code', 'Codex', 'Gemini CLI', 'opencode', 'cualquier cliente MCP']

export default function InicioPuertas() {
  return (
    <section className="seccion" id="puertas" aria-labelledby="puertas-titulo">
      <div className="seccion__cabeza">
        <h2 id="puertas-titulo" className="titulo-2">Programes o no, el check es tuyo.</h2>
      </div>
      <div className="ini-puertas">
        {PUERTAS.map(([publico, titulo, texto, accion]) => (
          <a key={publico} className="ini-puerta" href={`${enlace('/comofunciona')}?publico=${publico}`}>
            <h3 className="titulo-3">{titulo}</h3>
            <p>{texto}</p>
            <span className="enlace-flecha">
              {accion} <Icono nombre="flecha" />
            </span>
          </a>
        ))}
      </div>
      <div className="ini-agentes">
        <span>Funciona con</span>
        {AGENTES.map((a) => (
          <span key={a} className="ini-agentes__chip">{a}</span>
        ))}
      </div>
    </section>
  )
}
