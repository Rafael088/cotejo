import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'compatibles',
    titulo: 'Con qué agentes funciona',
    hijos: (
      <>
        <p>
          Cotejo no trae un modelo propio: se apoya en el agente de terminal que ya uses. Estos son
          los que sabe lanzar, y cómo los lanza el motor <code>headless</code> según el catálogo:
        </p>
        <Tabla
          etiqueta="Agentes compatibles"
          cabeza={['Agente', 'Cómo se lanza sin interfaz']}
          filas={[
            ['Claude Code', <code key="a">claude -p</code>],
            ['Codex', <code key="b">codex exec</code>],
            ['OpenCode', <code key="c">opencode run -m opencode-go/kimi-k2.7-code</code>],
            ['Gemini CLI', <code key="d">gemini -p</code>],
            ['Antigravity CLI', <code key="e">agy -p</code>],
          ]}
        />
        <p>
          La primera vez, Cotejo revisa cuáles tienes. Un agente cuenta como listo si está
          instalado, con sesión iniciada y con algún modelo disponible; el Inicio, Ajustes y el
          maestro hacen la misma comprobación y, si falta algo, dicen cómo arreglarlo. «Asignar a»
          agrupa los modelos de cada agente que tengas listo, con el modelo exacto, y «Añadir
          modelo…» registra uno nuevo.
        </p>
      </>
    ),
  },
  {
    id: 'mcp',
    titulo: 'MCP',
    hijos: (
      <>
        <p>
          <code>cotejo mcp</code> sirve los mismos verbos de la CLI como tools del Model Context
          Protocol, por stdio y sin dependencias. Para Claude Code, Codex, Gemini CLI y OpenCode, el
          instalador lo configura solo. Para otro cliente MCP:
        </p>
        <Codigo texto={'{"mcpServers": {"cotejo": {"command": "cotejo", "args": ["mcp"]}}}'} titulo="Claude Code (.mcp.json) y Cursor (.cursor/mcp.json)" />
        <Codigo texto={'{"mcp": {"cotejo": {"type": "local", "command": ["cotejo", "mcp"]}}}'} titulo="OpenCode (opencode.json)" />
        <p>
          En Claude Code también sirve <code>claude mcp add cotejo -- cotejo mcp</code>. Por defecto
          se sirve el núcleo de verbos (<code>contexto</code>, <code>tareas</code>, <code>buscar</code>,{' '}
          <code>leer</code>, <code>crear</code>, <code>tomar</code>, <code>entregar</code>,{' '}
          <code>bloquear</code>, <code>anotar_*</code> y <code>bitacora</code>); con{' '}
          <code>"args": ["mcp", "--perfil", "completo"]</code>, todos. Un verbo con acciones da una
          tool por acción (<code>proponer_decision</code>, <code>importar_obsidian</code>…), y un
          error del verbo vuelve como resultado con <code>isError</code>.
        </p>
        <Aviso>
          La ausencia también se hereda: no hay tool para finalizar una tarea ni para aceptar una
          decisión.
        </Aviso>
      </>
    ),
  },
  {
    id: 'permisos',
    titulo: 'Permisos del modo sin interfaz',
    hijos: (
      <>
        <p>
          Cada mensaje al maestro es un turno del agente sin interfaz y sin que nadie conteste
          permisos. Estos son los modos que Cotejo le pone a cada cliente en ese caso:
        </p>
        <Tabla
          etiqueta="Permisos del maestro por cliente"
          cabeza={['Cliente', 'Permisos']}
          filas={[
            ['Claude Code', <code key="a">--permission-mode bypassPermissions</code>],
            ['Codex', <code key="b">--dangerously-bypass-approvals-and-sandbox</code>],
            ['OpenCode', <><code>edit</code>, <code>bash</code> y <code>webfetch</code> en <code>allow</code></>],
            ['Gemini CLI', <code key="d">--approval-mode yolo</code>],
            ['Antigravity CLI', <code key="e">--dangerously-skip-permissions</code>],
          ]}
        />
        <p>
          Van sin los servidores MCP ni los ajustes del proyecto y, en Windows, sin abrir ninguna
          consola. En cambio, para un modelo que despachas con <code>--motor headless</code>, Cotejo
          no pone permisos por su cuenta: qué puede tocar un modelo sin que lo mires lo decides tú,
          con <code>motores.headless.argumentos_extra</code> (Claude) y{' '}
          <code>motores.headless.clientes.&lt;cliente&gt;.argumentos_extra</code> (los demás).
        </p>
        <Codigo texto={'["--permission-mode", "acceptEdits", "--allowedTools", "Bash(cotejo:*)"]'} titulo="Ejemplo de argumentos_extra para Claude" />
        <p>
          El agente que lanza el board trabaja encerrado: solo escribe en su copia del proyecto, no
          puede empujar a la rama principal ni usar <code>sudo</code>, no toca la configuración de
          Cotejo y no carga los ajustes, plugins ni servidores MCP que traiga el repo.
        </p>
        <Aviso tipo="ojo">
          En Windows el agente no queda encerrado dentro de la carpeta del proyecto: puede abrir y
          cambiar otros archivos de tu cuenta, igual que tú. Cotejo le pone algunos frenos, como
          negarle los comandos más peligrosos, pero eso no es un encierro. El board lo avisa la
          primera vez que lanza un agente.
        </Aviso>
      </>
    ),
  },
  {
    id: 'modelos',
    titulo: 'Catálogo de modelos',
    hijos: (
      <>
        <p>
          El enrutador asigna tareas a modelos de ese catálogo. Los de fábrica son los niveles de{' '}
          <a href={enlace('/docs/enrutador')}>el enrutador</a>; los que añades tú viven en{' '}
          <code>enrutador.modelos</code> de la config, cada uno con <code>clave</code>,{' '}
          <code>modelo_id</code>, <code>cliente</code> y <code>nivel</code>.
        </p>
        <Codigo
          texto={'cotejo modelos                     # el catálogo de niveles y modelos registrados\ncotejo modelos agregar …           # registra un modelo de un cliente\ncotejo modelos quitar …            # lo quita'}
        />
        <p>
          Una tarea se asigna con <code>cotejo asignar &lt;id&gt; sonnet</code>, con el menú{' '}
          <code>⋮</code> del board o con un tag <code>#agente/opus</code> en su línea. Con el
          instalador llegan también las skills <code>cotejo</code> y <code>cotejo-fuentes</code>,
          que le enseñan al agente el trato sin cargar el protocolo entero.
        </p>
      </>
    ),
  },
]

export default function Agentes() {
  return (
    <Doc
      ruta="/docs/agentes"
      titulo="Agentes y modelos."
      bajada="Cotejo trabaja con el agente de terminal que ya usas, o con cualquiera que hable MCP."
      secciones={secciones}
    />
  )
}
