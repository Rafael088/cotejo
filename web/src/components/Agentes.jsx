import { AGENTES } from '../config.js'

// «Funciona con tu agente»: los nombres en tipografía, sin logos de nadie.
export default function Agentes() {
  return (
    <section className="agentes" id="agentes" aria-labelledby="agentes-titulo">
      <div>
        <h2 id="agentes-titulo" className="agentes__titulo">
          Funciona con tu agente.
        </h2>
        <p className="agentes__mcp">O con cualquier agente que hable MCP.</p>
      </div>
      <ul className="agentes__lista">
        {AGENTES.map((nombre) => (
          <li key={nombre}>{nombre}</li>
        ))}
      </ul>
    </section>
  )
}
