import InstalarRapido from './InstalarRapido.jsx'
import Icono from './Icono.jsx'

// Las dos secciones por público (textos aprobados en web/textos-fase1.md, «Fase 1 A»): primero
// quien no programa, después quien programa. Sin animación de entrada: el HTML prerenderizado
// es lo que se ve, con o sin JavaScript.

function Pasos({ pasos, className = '' }) {
  return (
    <ol className={`pasos ${className}`}>
      {pasos.map(([titulo, cuerpo], i) => (
        <li key={i} className="paso">
          <span className="paso__numero" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
          <div className="paso__cuerpo">
            <h4 className="paso__titulo">{titulo}</h4>
            {cuerpo}
          </div>
        </li>
      ))}
    </ol>
  )
}

function Notas({ children }) {
  return (
    <div className="publico__notas">
      <h3 className="publico__notas-titulo">Notas</h3>
      <ul className="publico__notas-lista">{children}</ul>
    </div>
  )
}

function Llamada({ children }) {
  return (
    <a className="boton boton--claro publico__llamada" href="#instalar">
      {children} <Icono nombre="abajo" tam={16} />
    </a>
  )
}

function SiNoProgramas() {
  return (
    <section className="seccion publico" id="no-programo" aria-labelledby="no-programo-titulo">
      <div className="seccion__cabeza">
        <p className="publico__etiqueta">Si no programas</p>
        <h2 id="no-programo-titulo" className="titulo-2">Tu agente construye. Tú decides si está bien.</h2>
        <p className="parrafo publico__bajada">
          Cotejo no tiene una pantalla aparte para ti ni escribe el código. Trabajas con tu agente de
          siempre; Cotejo guarda el proyecto en orden y cada entrega llega con un resumen en lenguaje
          llano para que la revises.
        </p>
      </div>

      <div className="publico__bloque publico__bloque--doble">
        <h3 className="titulo-3">Qué necesitas</h3>
        <ul className="necesitas">
          <li>Un agente de terminal (Claude Code, Codex, Gemini CLI u opencode) o cualquier agente que hable MCP.</li>
          <li>Un ordenador con Linux o con Windows 10/11.</li>
          <li>Cotejo, que es gratis.</li>
          <li>Unos minutos para revisar lo que el agente te entregue. Esa parte es tuya y no se delega.</li>
        </ul>
      </div>

      <div className="publico__bloque">
        <h3 className="titulo-3">Cómo empiezas</h3>
        <Pasos
          pasos={[
            [
              'Instala Cotejo.',
              <>
                <p className="parrafo">
                  Instalar pide pegar un comando en una terminal. Si no te sientes cómodo, pídeselo a tu
                  agente: «instálame Cotejo» y pásale el comando de esta página.
                </p>
                <InstalarRapido titulo="Elige tu sistema" className="paso__instalar" />
              </>,
            ],
            [
              'Dile a tu agente que arranque el proyecto.',
              <p className="parrafo">
                Escribe «empiezo un proyecto» o «prepara este repo para trabajar con Cotejo». El agente
                prepara la carpeta, te hace cinco preguntas en un solo mensaje (cada una con una
                respuesta por defecto que solo confirmas o corriges) y deja escrito el objetivo, el
                siguiente paso y entre 3 y 8 tareas para la primera versión.
              </p>,
            ],
            [
              'Acepta lo que importa.',
              <p className="parrafo">
                Las decisiones que condicionan el proyecto (por ejemplo, qué tecnología usar) llegan
                como propuestas. Nada se da por vigente hasta que tú las aceptas en CotejoBoard.
              </p>,
            ],
          ]}
        />
      </div>

      <div className="publico__bloque">
        <h3 className="titulo-3">Tu día a día</h3>
        <Pasos
          className="pasos--rejilla"
          pasos={[
            [
              'Pídele trabajo.',
              <p className="parrafo">
                «Hazme dos tareas del proyecto.» El agente reparte cada tarea al modelo que le toca y te
                cuenta a quién y por qué.
              </p>,
            ],
            [
              'Espera a que entregue.',
              <p className="parrafo">
                Cada entrega aparece en la columna «Para comprobar» de CotejoBoard, con su evidencia.
              </p>,
            ],
            [
              'Lee el resumen.',
              <p className="parrafo">
                Dice qué cambió visto desde fuera y cómo probarlo tú mismo, sin nombres de archivos ni
                jerga.
              </p>,
            ],
            [
              'Pruébalo y decide.',
              <p className="parrafo">
                Si está bien, la apruebas. Si no, la devuelves con un motivo y el agente vuelve a ella.
              </p>,
            ],
          ]}
        />
        <p className="publico__cierre">
          Hecho es cuando alguien lo revisó. <span>Ese alguien eres tú.</span>
        </p>
      </div>

      <Notas>
        <li>Quien aprueba eres tú: el agente no puede marcar una tarea como hecha. No existe un verbo para eso, a propósito.</li>
        <li>Cotejo no escribe código por ti. Lo hace tu agente; Cotejo organiza y verifica.</li>
        <li>Hay tareas que no son de un modelo sino tuyas (comprar un dominio, firmar, abrir una cuenta). Salen marcadas como de una persona y no se despachan.</li>
        <li>CotejoBoard es el tablero donde revisas; no es un asistente para crear proyectos. El proyecto lo arranca tu agente.</li>
        <li>Cotejo 1.2 es beta: puede fallar. Si algo falla, <code>cotejo doctor</code> dice qué hacer, y puedes contarlo en un issue.</li>
      </Notas>

      <Llamada>Instala Cotejo</Llamada>
    </section>
  )
}

function SiProgramas() {
  const pasos = [
    [
      <code>cotejo init</code>,
      <p className="parrafo">
        Dentro del repo (o con <code>--repo &lt;carpeta&gt;</code>, que la crea y le hace{' '}
        <code>git init</code>). Deja <code>.cotejo/</code> con <code>tareas.md</code>,{' '}
        <code>proyecto.md</code> y una carpeta por tipo de conocimiento; la versión queda en 0.1.0. Es
        idempotente: repetirlo no pisa nada.
      </p>,
    ],
    [
      <code>cotejo plan</code>,
      <p className="parrafo">
        <code>cotejo plan --proyecto mi-app --solo-despachables</code> muestra por cada pendiente qué
        modelo la recibiría y por qué. No escribe nada. Si una tarea no tiene modelo asignado, se
        pregunta; <code>cotejo asignar &lt;id&gt; &lt;modelo&gt;</code> guarda la respuesta. Con un{' '}
        <code>plan.md</code> ya hecho, <code>cotejo importar plan</code> lo convierte en tareas (ensayo
        por defecto).
      </p>,
    ],
    [
      <code>cotejo despachar</code>,
      <p className="parrafo">
        <code>cotejo despachar &lt;id&gt;</code> toma la tarea y devuelve el encargo. Si la tarea está en
        un repo de git, crea un worktree con la rama <code>cotejo/&lt;id&gt;</code>: el agente trabaja y
        hace commit ahí. Puede ir como subagente (<code>--motor agente</code>) o como sesión aparte{' '}
        (<code>--motor sesion</code>). Las tareas de una persona (n0) no se despachan, sin excepción.{' '}
        <code>cotejo capacidad</code> dice cuántas caben a la vez en tu máquina.
      </p>,
    ],
    [
      <>
        <code>cotejo entregar</code>, con evidencia
      </>,
      <p className="parrafo">
        El agente entrega desde su carpeta con archivos, commit y <code>--prueba</code>, un comando
        suelto por prueba que Cotejo corre sin shell. Siempre con <code>--resumen</code>: qué cambió
        visto desde fuera y cómo probarlo, sin jerga. Si se atasca,{' '}
        <code>cotejo bloquear &lt;id&gt; --motivo "..."</code> la devuelve a Pendiente en vez de dejarla
        a medias.
      </p>,
    ],
    [
      <code>cotejo comprobar</code>,
      <p className="parrafo">
        <code>cotejo comprobar &lt;id&gt;</code> vuelve a correr las pruebas de la entrega y no escribe
        nada. En CotejoBoard revisas el diff y el resumen, y aprobar es cosa tuya.
      </p>,
    ],
    [
      <code>cotejo release</code>,
      <p className="parrafo">
        <code>cotejo release --proyecto mi-app --version 1.3.0</code> es un ensayo: enseña las notas que
        saldrían (tareas aprobadas, decisiones aceptadas, problemas resueltos) y se niega, nombrándolas,
        si queda alguna tarea de esa versión sin aprobar. Con <code>--aplicar</code> escribe{' '}
        <code>.cotejo/releases/v1.3.0.md</code>. Etiquetar y publicar lo haces tú.
      </p>,
    ],
  ]

  return (
    <section className="seccion publico" id="programo" aria-labelledby="programo-titulo">
      <div className="seccion__cabeza">
        <p className="publico__etiqueta">Si programas</p>
        <h2 id="programo-titulo" className="titulo-2">Del repo vacío a la versión etiquetada, con evidencia en cada paso.</h2>
        <p className="parrafo publico__bajada">
          El contexto, las decisiones y la arquitectura viven en <code>.cotejo/</code>, dentro de tu
          repo, un archivo por entrada. Tus agentes escriben el código; Cotejo reparte, recoge pruebas
          repetibles y deja la última palabra a una persona.
        </p>
      </div>

      <div className="publico__bloque">
        <h3 className="sr-only">Pasos</h3>
        <Pasos pasos={pasos} className="pasos--verbos" />
      </div>

      <Notas>
        <li>
          Un agente se entera barato: <code>cotejo contexto</code> devuelve objetivo, tareas, decisiones
          vigentes y temas en menos de mil tokens. <code>cotejo ahorro</code> enseña lo que costó
          enterarse y su supuesto (ver <a href="#ahorro">el medidor</a>).
        </li>
        <li>Una decisión propuesta por un agente (<code>proponer decision</code>) se acepta solo desde CotejoBoard.</li>
        <li>
          Si ya tienes el proyecto en Obsidian o Notion, <code>cotejo importar</code> lo trae entero a{' '}
          <code>.cotejo/</code> (ensayo primero, <code>--aplicar</code> después).
        </li>
        <li>Todos los verbos devuelven JSON y los errores dicen cuál es el siguiente paso.</li>
      </Notas>

      <Llamada>
        Instala Cotejo y corre <code>cotejo init</code>
      </Llamada>
    </section>
  )
}

export default function Publicos() {
  return (
    <>
      <nav className="publicos-selector seccion" aria-label="Por dónde empiezas">
        <a className="publicos-selector__opcion" href="#no-programo">No programo</a>
        <a className="publicos-selector__opcion" href="#programo">Programo</a>
      </nav>
      <SiNoProgramas />
      <SiProgramas />
    </>
  )
}
