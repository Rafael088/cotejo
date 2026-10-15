import Comando from './Comando.jsx'

export default function ConCualquierAgente() {
  const json = '{"mcpServers": {"cotejo": {"command": "cotejo", "args": ["mcp"]}}}'

  return (
    <section className="seccion con-cualquier-agente" id="con-cualquier-agente" aria-labelledby="con-cualquier-agente-titulo">
      <div className="seccion__cabeza">
        <h2 id="con-cualquier-agente-titulo" className="titulo-2">Con cualquier cliente MCP.</h2>
        <p className="parrafo">
          El instalador configura Claude Code, Codex, Gemini CLI y opencode. Si usas otro cliente
          que hable MCP, copia esta configuración: Cotejo sirve los mismos verbos como tools,
          sin dependencias. Gratis.
        </p>
      </div>

      <div className="con-cualquier-agente__contenido">
        <Comando texto={json} grande={true} />
      </div>
    </section>
  )
}
