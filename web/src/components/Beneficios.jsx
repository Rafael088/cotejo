// Bloque de beneficios (textos aprobados en web/textos-fase1.md, «Fase 1 B · Beneficios»).
// Va justo debajo del hero y antes del medidor: primero el porqué en tres frases, después la
// cifra que lo mide. Sin animación de entrada: el HTML prerenderizado es lo que se ve, con o sin
// JavaScript. Sin iconos ni verde (DESIGN.md): tres paneles planos con su «Se apoya en» en mono.

// En la línea de apoyo un verbo u opción no se parte por su guion («--aplicar»): cada palabra va
// entera y el salto de línea solo cae entre palabras.
function Cli({ children }) {
  const palabras = children.split(' ')
  return (
    <code>
      {palabras.map((p, i) => [
        i > 0 ? ' ' : null,
        <span key={i} className="beneficio__palabra">{p}</span>,
      ])}
    </code>
  )
}

const BENEFICIOS = [
  {
    nombre: 'Estructura desde el primer día',
    titulo: 'Empieza con un plan, no con un chat suelto.',
    texto: (
      <>
        Tu agente prepara el repo y te hace cinco preguntas en un solo mensaje. Queda escrito el
        objetivo, el siguiente paso y las tareas de la 0.1.0, y todo vive en <code>.cotejo/</code>,
        dentro de tu repo, un archivo por entrada: viaja con el código y cualquier agente nuevo se
        entera en menos de mil tokens.
      </>
    ),
    apoyo: (
      <>
        <Cli>cotejo init</Cli> · la entrevista de inicio (<Cli>cotejo protocolo</Cli>) ·{' '}
        <Cli>.cotejo/proyecto.md</Cli> · <Cli>cotejo contexto</Cli>
      </>
    ),
  },
  {
    nombre: 'Gestiona el proyecto en un tablero',
    titulo: 'Sabes qué falta y en qué versión va.',
    texto: (
      <>
        Cada tarea pasa por cuatro columnas en CotejoBoard: Pendiente, Haciéndola, Para comprobar y
        Finalizada. Las tareas se agrupan por versión, y las notas de release salen solo cuando todas
        las de esa versión están aprobadas.
      </>
    ),
    apoyo: (
      <>
        CotejoBoard · <Cli>cotejo version</Cli> · <Cli>cotejo crear --version</Cli> ·{' '}
        <Cli>cotejo release</Cli> (ensayo; <Cli>--aplicar</Cli> escribe{' '}
        <Cli>.cotejo/releases/vX.Y.Z.md</Cli>)
      </>
    ),
  },
  {
    nombre: 'Nada se da por hecho sin pruebas',
    titulo: 'Hecho es cuando alguien lo revisó.',
    texto: (
      <>
        Cada entrega llega con evidencia (archivos, commit y pruebas que se pueden repetir) y un
        resumen en lenguaje llano. Tú la apruebas o la devuelves con un motivo: ningún agente puede
        darla por hecha.
      </>
    ),
    apoyo: (
      <>
        <Cli>cotejo entregar --evidencia --prueba --resumen</Cli> · <Cli>cotejo comprobar</Cli> ·
        columna «Para comprobar» de CotejoBoard
      </>
    ),
  },
]

export default function Beneficios() {
  return (
    <section className="seccion beneficios" id="por-que" aria-labelledby="beneficios-titulo">
      <div className="seccion__cabeza">
        <p className="publico__etiqueta">Por qué Cotejo</p>
        <h2 id="beneficios-titulo" className="titulo-2">Proyectos hechos con IA que pueden crecer.</h2>
        <p className="parrafo publico__bajada">
          Gestiona tus proyectos de vibe coding de forma profesional: un plan escrito desde el primer
          día, un tablero con versiones y nada dado por hecho sin evidencia y sin tu revisión.
        </p>
      </div>

      <ol className="beneficios__lista">
        {BENEFICIOS.map((b, i) => (
          <li key={b.nombre} className="beneficio">
            <p className="beneficio__nombre">
              <span className="beneficio__numero" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
              {b.nombre}
            </p>
            <h3 className="beneficio__titulo">{b.titulo}</h3>
            <p className="parrafo beneficio__texto">{b.texto}</p>
            <p className="beneficio__apoyo">
              <span className="beneficio__apoyo-rotulo">Se apoya en</span> {b.apoyo}
            </p>
          </li>
        ))}
      </ol>
    </section>
  )
}
