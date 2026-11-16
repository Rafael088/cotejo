import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'que-es',
    titulo: 'Qué es el almacén',
    hijos: (
      <>
        <p>
          Además de las tareas, un repo puede llevar en <code>.cotejo/</code> todo lo que no es
          código pero informa el desarrollo. Cada entrada es su propio archivo de Markdown, con un
          frontmatter mínimo y un <code>id</code> estable (<code>dec-x7k2</code>,{' '}
          <code>pro-9f3a</code>, <code>arq-4m1p</code>…) que no cambia aunque el archivo se
          renombre. <code>cotejo init</code> crea el esqueleto entero.
        </p>
        <Tabla
          etiqueta="Qué hay dentro de .cotejo/"
          cabeza={['Ruta', 'Qué guarda']}
          filas={[
            [<code key="a">tareas.md</code>, 'Las tareas del proyecto, una línea cada una'],
            [<code key="b">proyecto.md</code>, 'Objetivo, stack, enlaces, siguiente paso y la versión (0.1.0 en uno nuevo)'],
            [<code key="c">decisiones/</code>, 'Lo que se decidió y por qué. Su texto es fijo'],
            [<code key="d">arquitectura/</code>, 'Las piezas del proyecto, dibujables en el mapa'],
            [<code key="e">problemas/</code>, 'Lo que falló, abierto o resuelto con su solución'],
            [<code key="f">aprendizajes/</code>, 'Lo que se aprendió por el camino'],
            [<code key="g">bitacora/</code>, 'Un archivo por día; solo se agrega'],
            [<code key="h">referencias/</code>, 'Notas de apoyo'],
            [<code key="i">recursos/</code>, 'Adjuntos, cada uno con su ficha'],
          ]}
        />
        <p>
          Como son notas Markdown con frontmatter, la carpeta también se puede abrir como vault de
          Obsidian para recorrerla y ver su grafo. Es un visor opcional: Cotejo no lo necesita.
        </p>
      </>
    ),
  },
  {
    id: 'enterarse',
    titulo: 'Para enterarse, de menos a más',
    hijos: (
      <>
        <p>
          Hay tres tamaños para pedir; conviene usar el más chico que sirva. Los tres aceptan{' '}
          <code>--repo &lt;carpeta&gt;</code> (por defecto, la raíz git desde donde se llama).
        </p>
        <Tabla
          etiqueta="Verbos para leer el almacén"
          cabeza={['Verbo', 'Qué devuelve']}
          filas={[
            [<code key="a">cotejo contexto [--tope N]</code>, <>Objetivo, stack y siguiente paso; las tareas por estado; las decisiones y problemas vigentes más recientes (10 por defecto, con el total real); y los temas que existen. Pensado para costar menos de 1k tokens.</>],
            [<code key="b">cotejo buscar [--tipo] [--temas] [--estado] [--desde] [--texto] [--limite]</code>, 'Una línea por entrada (id, tipo, título, resumen): el camino barato para decidir qué vale la pena leer entero.'],
            [<code key="c">cotejo leer &lt;id&gt;</code>, 'La entrada completa, con su cuerpo y su version (hash). De un recurso, la ruta de su archivo, nunca el contenido.'],
          ]}
        />
        <Codigo
          texto={'cotejo contexto\ncotejo buscar --tipo decision --temas auth\ncotejo leer dec-x7k2'}
        />
      </>
    ),
  },
  {
    id: 'escribir',
    titulo: 'Para escribir',
    hijos: (
      <>
        <Tabla
          etiqueta="Verbos para escribir en el almacén"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [<code key="a">cotejo proponer decision --titulo --temas --texto [--reemplaza &lt;dec-id&gt;]</code>, 'Crea una decisión en propuesta. Con --reemplaza, deja la vieja en reemplazada.'],
            [<code key="b">cotejo anotar &lt;problema|aprendizaje|referencia|arquitectura&gt; --titulo --temas --texto</code>, 'Una entrada nueva de ese tipo, con su id.'],
            [<code key="c">cotejo anotar arquitectura --titulo --pieza "capa|nombre|frase|tecnología|tareas"</code>, <>La arquitectura dibujable: una pieza por <code>--pieza</code>, en las capas <code>ve</code>, <code>hace</code>, <code>guarda</code> o <code>conecta</code>.</>],
            [<code key="d">cotejo bitacora "texto"</code>, 'Añade al final del archivo del día; nunca reescribe.'],
            [<code key="e">cotejo editar &lt;id&gt; --version &lt;hash&gt; --texto</code>, 'Cambia una arquitectura, una referencia o proyecto.md. Se niega si --version ya no coincide.'],
            [<code key="f">cotejo resolver &lt;pro-id&gt; --solucion "…"</code>, 'Problema abierto a resuelto, con la solución que lo cerró.'],
          ]}
        />
        <p>
          Toda escritura devuelve la entrada que dejó (<code>id</code>, <code>ruta</code>,{' '}
          <code>version</code>), para no tener que releerla.
        </p>
        <Codigo
          texto={'cotejo proponer decision --titulo "..." --temas auth --texto "..."\ncotejo anotar problema --titulo "..." --temas ci --texto "..."\ncotejo bitacora "qué se hizo hoy"'}
        />
      </>
    ),
  },
  {
    id: 'decisiones',
    titulo: 'Las decisiones no se editan ni se aceptan por verbo',
    hijos: (
      <>
        <p>
          El texto de una decisión es fijo: una que ya no aplica se reemplaza con{' '}
          <code>proponer decision --reemplaza &lt;dec-id&gt;</code>, y <code>editar</code> sobre una
          decisión se niega y lo dice.
        </p>
        <Aviso tipo="ojo">
          Ningún verbo acepta una decisión. <code>proponer decision</code> la deja en{' '}
          <code>propuesta</code>; pasarla a <code>aceptada</code> es de la persona, y solo desde{' '}
          <a href={enlace('/docs/board')}>CotejoBoard</a>, donde sale como carta propia en «Para
          comprobar». Aprobar la tarea que la propuso y aceptar la decisión son dos firmas
          distintas.
        </Aviso>
      </>
    ),
  },
]

export default function Almacen() {
  return (
    <Doc
      ruta="/docs/almacen"
      titulo="El almacén."
      bajada="El conocimiento de cada proyecto vive en su repo, un archivo por entrada, y cualquier agente lo consulta barato."
      secciones={secciones}
    />
  )
}
