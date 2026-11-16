import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'que-es',
    titulo: 'Una conversación dentro del board',
    hijos: (
      <>
        <p>
          Con un proyecto elegido en CotejoBoard, el maestro es una conversación. Le escribes en
          la barra del pie, en llano, y la conversación aparece en un panel flotante encima del
          tablero: lo que le dijiste, lo que va haciendo mientras contesta y su respuesta.
        </p>
        <p>
          El panel no empuja ni redimensiona las columnas. Se arrastra por su título, se minimiza o
          se cierra sin parar al maestro, y su respuesta llega igual. Nunca se abre una terminal.
        </p>
      </>
    ),
  },
  {
    id: 'que-hace',
    titulo: 'Qué puede hacer',
    hijos: (
      <>
        <p>Desde la 1.3.1, todo lo que harías tú en una terminal, menos aprobar:</p>
        <ul>
          <li>
            <strong>Añadir tareas.</strong> «Apunta que falta el login» las crea en el proyecto y
            salen en Pendiente al contestar.
          </li>
          <li>
            <strong>Preguntar por el proyecto.</strong> «¿Qué falta para la 0.1.0?», «¿cómo va?»:
            lo mira con la CLI y, si hace falta, lee el código.
          </li>
          <li>
            <strong>Hacer.</strong> Editar el código, correr comandos, hacer commits en ramas,
            editar y asignar tareas, despachar y lanzar agentes, entregar y bloquear.
          </li>
          <li>
            <strong>Repartir lo asignado.</strong> «Reparte lo asignado» propone las pendientes que
            una persona asignó a un modelo, y la respuesta trae un botón <strong>Repartir</strong>:
            las pasa a Haciéndola como si las arrastraras, cada una con su agente, su worktree y su
            ficha. La capacidad de la máquina manda. Lo que no esté asignado no sale en el botón.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'aprobar',
    titulo: 'Aprobar, nunca',
    hijos: (
      <>
        <p>
          Dar una tarea por hecha, meter la rama <code>cotejo/&lt;id&gt;</code> en la rama principal
          y aceptar una decisión propuesta siguen siendo tuyos, en el board.
        </p>
        <Aviso tipo="ojo">
          No basta con decírselo al maestro. Antes de cada turno, Cotejo apunta qué estaba aprobado
          y, al terminar (también si se corta o lo paras), deshace lo que haya aprobado: la tarea
          vuelve a su columna, la decisión a propuesta. Te lo dice al final de su respuesta y en la
          bitácora. Un merge no se deshace, porque sería destructivo: se avisa para que lo revises.
        </Aviso>
      </>
    ),
  },
  {
    id: 'agente',
    titulo: 'Con qué agente habla',
    hijos: (
      <>
        <p>
          <strong>Enviar</strong> (o Enter) usa el último agente elegido. La flecha del mismo botón
          despliega los que están listos —instalados, con sesión y con algún modelo disponible—
          entre Claude Code, OpenCode, Codex, Gemini CLI y Antigravity CLI; elegir uno solo lo
          elige. Si falta la sesión o el modelo, el board dice cómo arreglarlo.
        </p>
        <p>
          Con la barra vacía, el botón enseña u oculta la conversación de ese proyecto. «Empezar de
          nuevo» la borra. Cada mensaje es un turno del agente sin interfaz, en la carpeta del
          código y sin que nadie tenga que contestar permisos (los permisos de cada cliente están en{' '}
          <a href={enlace('/docs/agentes')}>Agentes y modelos</a>).
        </p>
      </>
    ),
  },
  {
    id: 'cli',
    titulo: 'Desde la terminal',
    hijos: (
      <>
        <p>La misma conversación, y la CLI espera la respuesta:</p>
        <Codigo
          texto={'cotejo maestro --proyecto Cotejo --pedido "¿qué falta?" [--cliente opencode] [--modelo …] [--olvidar] [--simular]\ncotejo maestro --clientes     # con cuáles puede hablar y qué les falta a los demás'}
        />
        <p>
          La conversación se guarda en la carpeta de estado (<code>maestro/&lt;proyecto&gt;.json</code>)
          y viaja recortada en cada turno. Si el proyecto no tiene carpeta conocida (ni en{' '}
          <code>enrutador.proyectos</code> ni en su fuente), el maestro lo dice en vez de buscar el
          código. Sus ajustes están en <a href={enlace('/docs/configuracion')}>Configuración</a>.
        </p>
      </>
    ),
  },
]

export default function Maestro() {
  return (
    <Doc
      ruta="/docs/maestro"
      titulo="El maestro."
      bajada="Le hablas en llano desde el pie del board. Hace casi todo lo que harías tú; aprobar no."
      secciones={secciones}
    />
  )
}
