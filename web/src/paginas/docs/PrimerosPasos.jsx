import Doc from '../../components/docs/Doc.jsx'
import Frase from '../../components/Frase.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const PREGUNTAS = [
  '¿Qué quieres construir? (en una frase)',
  '¿Quién la va a usar?',
  '¿Qué tiene que hacer la primera versión? (tres cosas como mucho)',
  '¿Dónde la van a usar?',
  '¿Qué más necesita?',
  '¿Qué dejamos para después? (opcional)',
]

const secciones = [
  {
    id: 'desde-la-app',
    titulo: 'Desde la app, sin terminal',
    hijos: (
      <>
        <p>
          Si no programas, o prefieres no abrir una terminal, se empieza en la propia app.
        </p>
        <ol>
          <li>
            <strong>Abre Cotejo.</strong> La primera vez revisa qué agentes tienes (Claude Code,
            Codex, OpenCode, Gemini CLI, Antigravity CLI) y git. Si falta Claude Code, Codex,
            OpenCode o Antigravity CLI, lo instala con su instalador oficial y te lleva a iniciar
            sesión.
          </li>
          <li>
            <strong>En el Inicio, «Nuevo proyecto».</strong> Seis preguntas en llano, en tres
            bloques: la idea, cómo se usa, y dónde y con quién. Después Cotejo lanza al agente por
            detrás y te enseña el progreso mientras prepara la carpeta. Si se cuelga, puedes
            reintentar o abrirlo en una terminal que se ve.
          </li>
          <li>
            <strong>Revisa el plan.</strong> Ves el objetivo, las decisiones que propone el agente
            y las tareas de la 0.1.0 con quién haría cada una. Aceptar las decisiones es tuyo;
            «Cambiar» devuelve una al agente con tu motivo.
          </li>
          <li>
            <strong>«Empezar la 0.1.0».</strong> Reparte las tareas y abre el mapa del proyecto:
            las piezas de tu app en cuatro capas (lo que ve la gente, lo que hace, lo que guarda y
            con qué se conecta). «Ver mi app» la abre en el navegador; «Parar la app» la apaga.
          </li>
        </ol>
        <p>Las seis preguntas de «Nuevo proyecto»:</p>
        <ol>
          {PREGUNTAS.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ol>
      </>
    ),
  },
  {
    id: 'en-un-repo',
    titulo: 'En un repo, con cotejo init',
    hijos: (
      <>
        <p>Si programas, son cuatro pasos, de la instalación a la primera tarea comprobada.</p>
        <h3>1. Instala Cotejo</h3>
        <p>
          Está en <a href={enlace('/docs')}>la introducción</a>.
        </p>
        <h3>2. Corre cotejo init en la carpeta del proyecto</h3>
        <Codigo
          texto={'cd /ruta/al/proyecto\ncotejo init                    # dentro de un repo git\ncotejo init --repo ~/mi-app    # también sirve para una carpeta nueva o sin git'}
        />
        <p>
          Crea el <code>.cotejo/</code> del repo —<code>tareas.md</code>, <code>proyecto.md</code>{' '}
          y una carpeta por cada tipo de conocimiento—, deja el proyecto en la 0.1.0 y lo registra
          en la fuente <code>repo</code>. Es idempotente: repetirlo no pisa nada. Sobre una carpeta
          nueva o sin git, le hace <code>git init</code>.
        </p>
        <h3>3. Pídele a tu agente que arranque el proyecto</h3>
        <Frase texto="empiezo un proyecto" />
        <p style={{ marginTop: 12 }}>
          O «prepara este repo para trabajar con Cotejo». La skill <code>cotejo</code>, que se
          instala con Cotejo, lo entrevista en un solo mensaje con valores por defecto y deja
          escrito el objetivo, el stack y el siguiente paso en <code>proyecto.md</code>; las
          decisiones que condicionan lo demás, como propuestas; una arquitectura inicial; y entre 3
          y 8 tareas para la 0.1.0.
        </p>
        <h3>4. Trabaja las tareas y compruébalas en el board</h3>
        <p>
          El agente reparte la 0.1.0, toma cada tarea, la hace y la entrega con evidencia. En{' '}
          <a href={enlace('/docs/board')}>CotejoBoard</a> aceptas las decisiones propuestas,
          compruebas lo entregado y apruebas.
        </p>
        <Codigo
          texto={'cotejo plan --proyecto mi-app       # qué modelo recibiría cada pendiente\ncotejo version --proyecto mi-app    # en qué versión van y cuántas tareas quedan\ncotejo                              # abre o cierra CotejoBoard'}
        />
        <Aviso>
          Una decisión propuesta se acepta solo desde el board; ningún verbo de la CLI la acepta.
          Si el proyecto ya vive en Obsidian o Notion, mira{' '}
          <a href={enlace('/docs/fuentes')}>Fuentes</a>.
        </Aviso>
      </>
    ),
  },
  {
    id: 'cada-dia',
    titulo: 'Cada día',
    hijos: (
      <>
        <Tabla
          etiqueta="Lo que repites cada día"
          cabeza={['Cuándo', 'Qué haces']}
          filas={[
            [
              'Al empezar',
              'Abre Cotejo: el Inicio te dice cómo va cada proyecto y cuántas entregas esperan que las compruebes.',
            ],
            [
              'Para avanzar',
              'Arrastra una tarea de Pendiente a Haciéndola. Cotejo lanza al agente con el modelo que tenga asignado, y lo que hace se ve en su ficha.',
            ],
            [
              'Al revisar',
              'En «Para comprobar» está cada entrega con su evidencia. La apruebas o la devuelves con un motivo.',
            ],
            [
              'Al cerrar versión',
              'Pídele a tu agente que saque la versión: salen las notas con lo aprobado. Etiquetar y publicar lo haces tú.',
            ],
          ]}
        />
        <p>Dos frases que puedes copiarle a tu agente:</p>
        <Frase texto="qué tengo pendiente en mi-app" />
        <div style={{ height: 10 }} />
        <Frase texto="saca la 0.1.0 de mi-app" />
        <p style={{ marginTop: 16 }}>
          Si algo no funciona, <code>cotejo doctor</code> dice qué y cómo arreglarlo.
        </p>
      </>
    ),
  },
]

export default function PrimerosPasos() {
  return (
    <Doc
      ruta="/docs/primeros-pasos"
      titulo="Primeros pasos."
      bajada="Tu primer proyecto, de la instalación a la primera tarea comprobada, y lo que repites cada día."
      secciones={secciones}
    />
  )
}
