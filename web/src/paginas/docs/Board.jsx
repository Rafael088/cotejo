import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'columnas',
    titulo: 'Las cuatro columnas',
    hijos: (
      <>
        <p>
          CotejoBoard es la ventana de seguimiento (GTK4 y libadwaita) y la cara de la persona que
          comprueba. Una tarea siempre está en una de estas cuatro columnas:
        </p>
        <Tabla
          etiqueta="Las columnas del board"
          cabeza={['Columna', 'En el Markdown', 'Quién la mueve']}
          filas={[
            ['Pendiente', <code key="a">- [ ]</code>, '—'],
            ['Haciéndola', <code key="b">#en-curso</code>, 'El agente'],
            ['Para comprobar', <code key="c">#por-validar</code>, 'El agente, cuando entrega'],
            ['Finalizada', <code key="d">- [x]</code>, <strong key="e">Solo tú</strong>],
          ]}
        />
        <Aviso tipo="ojo">
          No existe un verbo para finalizar una tarea, y esa ausencia es el diseño. Si el agente
          pudiera marcar hecha su propia tarea, «hecha» dejaría de significar «alguien la revisó».
        </Aviso>
        <p>
          Cada carta muestra el agente asignado y la dificultad. El menú <code>⋮</code> mueve la
          tarea de columna, asigna un modelo registrado (o <code>persona</code>) o abre la nota. La
          banda de proyectos elige cuál ver; «Todos los proyectos» los junta, agrupados por proyecto.
        </p>
      </>
    ),
  },
  {
    id: 'haciendo',
    titulo: 'Arrastrar a Haciéndola',
    hijos: (
      <>
        <p>
          Arrastrar una carta de Pendiente a Haciéndola lanza al agente con el modelo que le
          asignaste, en su propia copia del proyecto (un worktree con la rama <code>cotejo/&lt;id&gt;</code>).
          En su ficha ves lo que va haciendo, en vivo. Se puede mover una carta de tres maneras:
          arrastrándola, con <code>Ctrl+←</code> / <code>Ctrl+→</code> sobre la carta enfocada, o
          desde el menú <code>⋮</code>.
        </p>
        <p>
          Si la máquina no tiene memoria libre, la tarea espera. Cuántas caben a la vez lo dice{' '}
          <a href={enlace('/docs/enrutador')}>capacidad</a>.
        </p>
      </>
    ),
  },
  {
    id: 'pausar',
    titulo: 'Pausar y retomar',
    hijos: (
      <>
        <p>
          Devolver una carta a Pendiente para al agente sin perder lo hecho. Volver a moverla lanza
          uno nuevo que sigue desde ahí. Si el agente termina sin entregar, la tarea vuelve sola a
          Pendiente y te dice por qué.
        </p>
        <p>
          En Windows, parar detiene al agente entero, con todo lo que él abrió, y solo a él. Al
          cerrar el board con agentes trabajando, te pregunta si pararlos o dejarlos.
        </p>
      </>
    ),
  },
  {
    id: 'comprobar',
    titulo: 'Comprobar una entrega',
    hijos: (
      <>
        <p>
          Las cartas de «Para comprobar» traen la evidencia con la que el agente las entregó,
          recortada a tres líneas; el menú <code>⋮</code> la abre entera, para copiar un commit o un
          comando. Si la entrega trae evidencia de git, la carta suma tres acciones:
        </p>
        <Tabla
          etiqueta="Acciones de una entrega"
          cabeza={['Acción', 'Qué hace']}
          filas={[
            [
              <strong key="a">Comprobar</strong>,
              <>Vuelve a correr, en el worktree de la tarea, las pruebas que anotó la entrega (lo mismo que <code>cotejo comprobar &lt;id&gt;</code>) y dice si el resultado sigue igual. No toca el estado de la tarea.</>,
            ],
            [
              <strong key="b">Revisar</strong>,
              <>Abre el diff entre los dos commits que anotó esa entrega, partido por archivo y plegable. Para un cambio grande, «Abrir en herramienta» lanza <code>git difftool</code>.</>,
            ],
            [
              <strong key="c">Aprobar</strong>,
              <>Marca <code>[x]</code> y, si la tarea tenía worktree, ofrece integrar su rama (<code>merge --no-ff</code>, que se aborta entero si choca y nunca borra la rama). Decir que no deja la tarea igual de hecha, solo sin fusionar.</>,
            ],
          ]}
        />
        <p>
          En los proyectos creados desde el Inicio, aprobar la mete en tu app. Si choca con otro
          cambio, «Que lo resuelva un agente» crea la tarea de juntarlos.
        </p>
        <p>
          Una decisión que un agente propuso sale como su propia carta en «Para comprobar», con su
          texto y, si reemplaza otra, la vieja al lado. Su único botón es <strong>Aceptar</strong>,
          y es el único sitio donde una decisión pasa de propuesta a aceptada.
        </p>
      </>
    ),
  },
  {
    id: 'rechazar',
    titulo: 'Rechazar con motivo',
    hijos: (
      <>
        <p>
          Sacar una tarea de «Para comprobar» sin aprobarla abre un diálogo que no te deja seguir
          hasta que escribas qué falta. El motivo se queda con la tarea: se ve en su carta, en
          ámbar, hasta que se vuelva a entregar, y le llega al agente en el JSON de <code>tareas</code>{' '}
          y de <code>tomar</code>. Al rechazar, el board relanza al agente con lo que pediste cambiar.
        </p>
        <p>
          Una carta parada lleva su nota en ámbar: <strong>DEVUELTA</strong> si la paró quien iba a
          comprobarla, <strong>BLOQUEADA</strong> si la paró quien la estaba haciendo. Un rechazo
          mudo devolvería al agente al punto de partida, y entregaría lo mismo.
        </p>
      </>
    ),
  },
  {
    id: 'capacidad',
    titulo: 'Capacidad de la máquina',
    hijos: (
      <>
        <p>
          La máquina manda. Antes de lanzar varios agentes en paralelo, Cotejo mide la memoria
          disponible y no reparte de más: la tarea que no cabe espera su turno. Desde la
          terminal, <code>cotejo capacidad</code> dice cuántas caben ahora y qué lo limita (el
          detalle está en <a href={enlace('/docs/enrutador')}>el enrutador</a>).
        </p>
      </>
    ),
  },
  {
    id: 'teclado',
    titulo: 'Teclado',
    hijos: (
      <>
        <p>
          El board se recorre entero con el teclado. <code>Tab</code> salta de columna en columna,
          no de carta en carta: con 60 pendientes, tabular una a una no lleva a ningún lado.
        </p>
        <Tabla
          etiqueta="Atajos del board"
          cabeza={['Tecla', 'Qué hace']}
          filas={[
            [<code key="a">Tab</code>, 'Salta de columna en columna, en orden visual'],
            [<code key="b">↑</code> , 'Carta anterior dentro de la columna'],
            [<code key="c">↓</code>, 'Carta siguiente dentro de la columna'],
            [<code key="d">← →</code>, 'Cambia de columna'],
            [<code key="e">Ctrl+← / Ctrl+→</code>, 'Mueve la carta enfocada a otra columna'],
            [<code key="f">Enter</code>, 'Abre la nota de la tarea'],
            [<code key="g">Menú · Shift+F10</code>, <>Abre el <code>⋮</code> de la carta enfocada</>],
            [<code key="h">Ctrl+F</code>, 'Buscar'],
            [<code key="i">Ctrl+R · F5</code>, 'Recargar'],
            [<code key="j">Ctrl+1 · Ctrl+2</code>, 'El Inicio · el tablero'],
            [<code key="k">Esc · Ctrl+W</code>, 'Ocultar la ventana'],
            [<code key="l">Ctrl+Q</code>, 'Cerrar la app del todo'],
          ]}
        />
      </>
    ),
  },
]

export default function Board() {
  return (
    <Doc
      ruta="/docs/board"
      titulo="El board."
      bajada="Cuatro columnas, un agente por tarea y una sola persona que decide qué está hecho."
      secciones={secciones}
    />
  )
}
