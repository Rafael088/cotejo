import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const v = (t) => <code>{t}</code>

const secciones = [
  {
    id: 'principios',
    titulo: 'Cómo habla la CLI',
    hijos: (
      <>
        <p>
          <code>cotejo</code> sin argumentos abre o cierra CotejoBoard. Con un verbo, es la cara sin
          interfaz, pensada para un agente: no carga GTK, y todo sale en JSON por la salida
          estándar. (<code>tareas-obsidian</code> y <code>foco</code> son el mismo programa con sus
          nombres de antes.)
        </p>
        <ul>
          <li>
            El <code>id</code> de una tarea sale de <code>tareas</code> y no se construye a mano:
            es la marca de bloque de su línea (<code>cotejo-a1b2</code>), y se acepta con{' '}
            <code>^</code> delante.
          </li>
          <li>
            Cada escritura devuelve la tarea como quedó, y trae <code>"cambio": false</code> cuando
            no hizo falta tocar nada: repetir una operación es seguro.
          </li>
          <li>
            Si una nota no se pudo leer, la respuesta trae <code>avisos</code> con cuál y por qué.
          </li>
        </ul>
        <p>Los errores traen <code>salida</code>, que dice qué hacer, y <code>reintentable</code>:</p>
        <Codigo
          copiar={false}
          texto={'{"error": "La nota Cotejo.md cambió desde que leíste la tarea",\n "salida": "Vuelve a pedir `tareas` y repite la operación con el id nuevo. No se escribió nada.",\n "reintentable": true}'}
        />
        <Aviso tipo="ojo">
          No hay verbo para finalizar una tarea ni para aceptar una decisión. Las dos cosas se hacen
          en CotejoBoard, con la mano.
        </Aviso>
      </>
    ),
  },
  {
    id: 'tareas',
    titulo: 'Tareas',
    hijos: (
      <>
        <Tabla
          etiqueta="Verbos de tareas"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [v('cotejo tareas [--proyecto] [--todas] [--estado]'), 'Cuáles faltan (por defecto excluye hechas).'],
            [v('cotejo crear "…" --proyecto P'), 'Anota trabajo nuevo, pendiente y sin dueño. Repetirlo no duplica.'],
            [v('cotejo tomar <id> --agente opus'), 'Pendiente a Haciéndola.'],
            [v('cotejo entregar <id> --evidencia "…" [--prueba "cmd"]… [--repo]'), 'Haciéndola a Para comprobar, con rama, commits, diff y pruebas.'],
            [v('cotejo comprobar <id>'), 'Vuelve a correr las pruebas de la última entrega. No escribe nada.'],
            [v('cotejo bloquear <id> --motivo "…"'), 'Haciéndola a Pendiente, sin dueño y con el motivo a la vista.'],
            [v('cotejo asignar <id> sonnet'), 'Cambia de dueño.'],
            [v('cotejo estado'), 'Los conteos de siempre (~80 tokens).'],
            [v('cotejo ahorro'), 'Qué costó enterarse por aquí, medido.'],
          ]}
        />
        <p>
          <code>entregar</code> guarda evidencia que se puede volver a comprobar: en un repo git, la
          rama, los commits y el resumen del diff; y cada <code>--prueba</code> la corre Cotejo
          mismo, sin shell y con tiempo límite. Una prueba en rojo no frena la entrega, pero se
          avisa y queda anotada. <code>bloquear</code> pide motivo por la misma razón que{' '}
          <code>entregar</code> pide evidencia.
        </p>
      </>
    ),
  },
  {
    id: 'enrutador',
    titulo: 'Enrutador',
    hijos: (
      <>
        <Tabla
          etiqueta="Verbos del enrutador"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [v('cotejo plan --proyecto P [--solo-despachables]'), 'Qué modelo recibiría cada pendiente.'],
            [v('cotejo decidir --tarea <id>'), 'A quién le toca esa, y por qué.'],
            [v('cotejo despachar <id> [--motor] [--sin-aislar]'), 'La toma a nombre de ese modelo, en su worktree.'],
            [v('cotejo modelos'), 'El catálogo de niveles y modelos registrados.'],
            [v('cotejo revisar [--dias N]'), 'Qué pasó con lo que se repartió.'],
            [v('cotejo capacidad --proyecto P'), 'Cuántas tareas caben ahora en la máquina.'],
            [v('cotejo worktrees [--limpiar]'), 'Dónde quedó cada worktree; retira los que sobran.'],
            [v('cotejo despachos'), 'El registro de reparto: a quién fue cada tarea y las que no se repartieron.'],
            [v('cotejo evaluar'), 'Mide las reglas contra tareas reales etiquetadas a mano.'],
            [v('cotejo maestro --proyecto P --pedido "…"'), 'Habla con el maestro del proyecto.'],
            [v('cotejo protocolo'), 'El trato entero, para leerlo.'],
          ]}
        />
        <p>
          El detalle está en <a href={enlace('/docs/enrutador')}>el enrutador</a> y en{' '}
          <a href={enlace('/docs/maestro')}>el maestro</a>.
        </p>
      </>
    ),
  },
  {
    id: 'contexto',
    titulo: 'Contexto',
    hijos: (
      <>
        <Tabla
          etiqueta="Verbos del almacén"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [v('cotejo contexto [--tope N]'), 'Objetivo, tareas, decisiones y problemas vigentes, temas. Menos de 1k tokens.'],
            [v('cotejo buscar [--tipo] [--temas] [--texto]'), 'Una línea por entrada; el camino barato.'],
            [v('cotejo leer <id>'), 'La entrada completa, con su version.'],
            [v('cotejo proponer decision --titulo --temas --texto'), 'Una decisión en propuesta; la acepta una persona.'],
            [v('cotejo anotar <tipo> --titulo --temas --texto'), 'Problema, aprendizaje, referencia o arquitectura.'],
            [v('cotejo bitacora "texto"'), 'Añade al archivo del día.'],
            [v('cotejo editar <id> --version <hash> --texto'), 'Cambia una arquitectura, una referencia o proyecto.md.'],
            [v('cotejo resolver <pro-id> --solucion "…"'), 'Cierra un problema con su solución.'],
          ]}
        />
        <p>
          Más en <a href={enlace('/docs/almacen')}>el almacén</a>.
        </p>
      </>
    ),
  },
  {
    id: 'proyecto',
    titulo: 'Proyecto, fuentes y configuración',
    hijos: (
      <>
        <Tabla
          etiqueta="Verbos de proyecto, fuentes y configuración"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [v('cotejo init [--repo <carpeta>]'), 'Crea el esqueleto .cotejo/ y registra el repo. Idempotente.'],
            [v('cotejo version --proyecto P'), 'En qué versión van y cuántas tareas quedan.'],
            [v('cotejo release --proyecto P --version V'), 'Ensayo de notas de la versión; se niega si queda algo sin aprobar.'],
            [v('cotejo doctor'), '¿Funciona?, y si no, qué hacer.'],
            [v('cotejo fuentes [info|probar|usar|agregar|quitar]'), 'Las fuentes de tareas y su conexión.'],
            [v('cotejo importar <plan|obsidian|notion>'), 'Trae un plan o un proyecto. Ensayo por defecto; --aplicar escribe.'],
            [v('cotejo config <init|validar>'), 'Crea o migra el archivo de configuración; dice qué tiene mal.'],
            [v('cotejo temas [nuevo|comprobar|usar]'), 'Los temas de color del board.'],
            [v('cotejo mcp [--perfil completo]'), 'Sirve los verbos como tools MCP.'],
          ]}
        />
        <p>
          Mira <a href={enlace('/docs/fuentes')}>Fuentes</a> y{' '}
          <a href={enlace('/docs/configuracion')}>Configuración</a>.
        </p>
      </>
    ),
  },
]

export default function Cli() {
  return (
    <Doc
      ruta="/docs/cli"
      titulo="La CLI."
      bajada="Todos los verbos de cotejo, una línea cada uno, en JSON y pensados para agentes."
      secciones={secciones}
    />
  )
}
